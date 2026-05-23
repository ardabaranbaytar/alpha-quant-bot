import secrets
import os
import datetime
import logging
import threading
import time

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from sqlalchemy import text
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config.database import db
from config.settings import settings
from core.signal_generator import signals_hub
from execution.execution_engine import execution_engine
from core.analytics import analytics_manager

logger    = logging.getLogger(__name__)
_COOKIE   = "aq_session"
_MAX_AGE  = 8 * 3600  

# ── Session helpers ───────────────────────────────────────────────────────────
def _serializer() -> URLSafeTimedSerializer:
    if not settings.SESSION_SECRET:
        raise RuntimeError("SESSION_SECRET is not set in .env")
    return URLSafeTimedSerializer(settings.SESSION_SECRET)

def _create_session(username: str) -> str:
    return _serializer().dumps(username)

def _verify_session(token: str) -> str | None:
    try:
        return _serializer().loads(token, max_age=_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="Alpha Quant")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

static_path = os.path.join(BASE_DIR, "static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


# ── Auth middleware — runs on every request ───────────────────────────────────
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # Auth disabled when APP_PASSWORD is not set (demo/portfolio mode)
    if not settings.APP_PASSWORD:
        return await call_next(request)

    public = {"/login", "/favicon.ico"}
    if request.url.path in public or request.url.path.startswith("/static/"):
        return await call_next(request)

    token    = request.cookies.get(_COOKIE)
    username = _verify_session(token) if token else None
    if not username:
        return RedirectResponse(url="/login", status_code=302)

    return await call_next(request)


# ── Global exception middleware ───────────────────────────────────────────────
@app.middleware("http")
async def exception_middleware(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as exc:
        logger.error("Unhandled exception: %s", exc, exc_info=(settings.LOG_LEVEL == "DEBUG"))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": "An unexpected error occurred."},
        )


# ── Startup: background worker ────────────────────────────────────────────────
def _background_worker():
    logger.info("Background worker started.")
    while True:
        try:
            execution_engine.manage_orders_and_positions()
        except Exception as e:
            logger.error("Worker error: %s", e)
        time.sleep(60)

@app.on_event("startup")
def start_background_worker():
    threading.Thread(target=_background_worker, daemon=True).start()


# ── Login / Logout ────────────────────────────────────────────────────────────
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html", context={})

@app.post("/login")
async def login_submit(request: Request):
    form     = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))

    valid_user = secrets.compare_digest(username.encode(), settings.APP_USERNAME.encode())
    valid_pass = secrets.compare_digest(password.encode(), settings.APP_PASSWORD.encode())

    if not (valid_user and valid_pass):
        logger.warning("Failed login attempt for username: %s", username)
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"error": "Invalid username or password."},
            status_code=401,
        )

    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie(
        key=_COOKIE,
        value=_create_session(username),
        httponly=True,
        secure=False,   # set True in production behind HTTPS
        samesite="strict",
        max_age=_MAX_AGE,
    )
    logger.info("User '%s' logged in.", username)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(_COOKIE)
    return response


# ── Dashboard ─────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
@limiter.limit("20/minute")
def dashboard(request: Request):
    try:
        opportunities = signals_hub.scan_instant_opportunities()
        metrics = analytics_manager.generate_report(save_csv=False)
    except Exception as e:
        logger.error("Dashboard data fetch failed: %s", e)
        opportunities = []
        metrics = {"Total PnL": "$0.00", "Win Rate": "0.00%",
                     "Profit Factor": "0.00", "Max Drawdown": "$0.00"}

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"opportunities": opportunities, "total_opportunities": len(opportunities), "metrics": metrics},
    )


# ── Positions ─────────────────────────────────────────────────────────────────
@app.get("/positions", response_class=HTMLResponse)
@limiter.limit("20/minute")
def positions(request: Request):
    trades     = []
    total_pnl  = 0.0
    try:
        with db.engine.connect() as conn:
            trades = conn.execute(
                text("SELECT * FROM positions ORDER BY entry_time DESC;")
            ).mappings().fetchall()
        total_pnl = sum(float(r["pnl"]) for r in trades if r["pnl"] is not None)
    except Exception as e:
        logger.error("Positions query failed: %s", e)

    return templates.TemplateResponse(
        request=request,
        name="positions.html",
        context={"trades": trades, "total_pnl": round(total_pnl, 2)},
    )


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/health")
@limiter.limit("30/minute")
async def health(request: Request):
    try:
        with db.engine.connect() as conn:
            conn.execute(text("SELECT 1;"))
        db_status = "CONNECTED"
    except Exception:
        db_status = "DISCONNECTED"
    return {
        "status":    "OPERATIONAL" if db_status == "CONNECTED" else "DEGRADED",
        "database":  db_status,
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── API: raw signals ──────────────────────────────────────────────────────────
@app.get("/api/signals")
@limiter.limit("10/minute")
async def api_signals(request: Request):
    return signals_hub.scan_instant_opportunities()