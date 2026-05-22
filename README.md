# Alpha Quant — Statistical Pairs Trading Bot

A quantitative trading research system built for learning and experimentation. Detects statistical arbitrage opportunities between correlated stock pairs using cointegration analysis and Z-score thresholds, manages simulated positions with a rule-based risk engine, and presents everything through a real-time web dashboard.

> **Disclaimer:** This project is developed for educational purposes only. It does not constitute financial or investment advice. All positions are simulated — no real money is involved.

---

## How It Works

1. **Data Pipeline** — Fetches hourly OHLCV data for NASDAQ-100 stocks from Yahoo Finance and stores it in PostgreSQL. Runs on a schedule via APScheduler.

2. **Signal Engine** — Tests all stock pair combinations for cointegration (Engle-Granger). Pairs that pass the statistical threshold are monitored continuously. When the Z-score of the price ratio breaches the entry threshold, a signal is generated.

3. **Execution Engine** — Runs in a background thread. Evaluates signals against risk filters (daily drawdown limit, max open positions, exposure limits, cooldown period) before recording a simulated position.

4. **Dashboard** — FastAPI web app displaying live signals, open/closed positions, and performance metrics (PnL, win rate, profit factor, max drawdown).

---

## Features

- Cointegration-based pair screening with configurable p-value threshold
- Rolling Z-score calculation with configurable window
- Fundamental health scoring as a secondary filter
- Risk management: stop-loss, daily drawdown cap, position limits, cooldown timer
- Performance analytics: win rate, profit factor, max drawdown, average holding time
- Session-based authentication with signed cookies
- Rate limiting on all API endpoints
- Structured logging with configurable log level

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy |
| Database | PostgreSQL |
| Data | yfinance, pandas, statsmodels |
| Scheduler | APScheduler |
| Frontend | Jinja2, Tailwind CSS, Three.js (WebGL) |
| Auth | itsdangerous (signed session cookies) |
| Server | Uvicorn, Gunicorn |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ardabaranbaytar/alpha-quant-bot.git
cd alpha-quant-bot
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
DB_USER=postgres
DB_PASS=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=finansal_analiz

APP_USERNAME=admin
APP_PASSWORD=your_strong_password
SESSION_SECRET=your_random_secret_key

ALLOWED_ORIGINS=http://localhost:8000
LOG_LEVEL=INFO
```

### 4. Set up PostgreSQL

Create the database and required tables. The system expects the following tables:
- `hisse_fiyatlari` — hourly price data
- `sirket_bilancolari` — fundamental balance sheet data
- `pozisyonlar` — simulated position ledger

### 5. Run

```bash
python run_bot.py
```

Open `http://localhost:8000` in your browser.

---

## Project Structure

```
alpha-quant-bot/
├── config/
│   ├── settings.py          # Environment-based configuration
│   ├── database.py          # SQLAlchemy engine setup
│   ├── risk_config.py       # Risk management parameters
│   └── logging_config.py   # Centralized logging setup
├── core/
│   ├── signal_generator.py  # Cointegration scanning & Z-score engine
│   ├── health_score.py      # Fundamental scoring filter
│   └── analytics.py        # Performance metrics calculator
├── data_pipeline/
│   ├── yfinance_fetcher.py  # Data ingestion from Yahoo Finance
│   └── scheduler.py        # APScheduler job definitions
├── execution/
│   └── execution_engine.py  # Risk checks & position management
├── web_app/
│   ├── app.py              # FastAPI routes, auth, middleware
│   └── templates/          # Jinja2 HTML templates
├── .env.example            # Environment variable template
├── requirements.txt
└── run_bot.py              # Entry point
```

---

## Roadmap

- [ ] Replace Yahoo Finance with a professional data provider
- [ ] Backtesting framework with walk-forward validation
- [ ] C++ execution layer for real broker connectivity
- [ ] Extended universe beyond NASDAQ-100
- [ ] Multi-factor signal weighting

---

## License

MIT
