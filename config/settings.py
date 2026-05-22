# config/settings.py

import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Database — values come from .env, never hardcoded
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "finansal_analiz")

    @property
    def DATABASE_URL(self) -> str:
        if not self.DB_PASS:
            raise RuntimeError("DB_PASS is not set. Add it to your .env file.")
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # Trading strategy parameters — overridable via .env
    PENCERE:  int   = int(os.getenv("PENCERE", "300"))
    Z_GIRIS:  float = float(os.getenv("Z_GIRIS", "1.5"))
    Z_STOP:   float = float(os.getenv("Z_STOP", "3.5"))

    # Transaction costs
    KOMISYON_ORAN: float = 0.001
    SLIPPAGE_ORAN: float = 0.0005

    # Logging level
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Dashboard authentication
    APP_USERNAME:   str = os.getenv("APP_USERNAME", "admin")
    APP_PASSWORD:   str = os.getenv("APP_PASSWORD", "")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "")

    # CORS — comma-separated origins parsed into a list
    ALLOWED_ORIGINS: list = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
        if o.strip()
    ]

    # Future broker API keys (Alpaca / IBKR)
    # AP_API_KEY    = os.getenv("ALPACA_API_KEY")
    # AP_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

settings = Settings()