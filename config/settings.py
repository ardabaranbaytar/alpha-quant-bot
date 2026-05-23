import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASS: str = os.getenv("DB_PASS", "")
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "financial_analysis")

    @property
    def DATABASE_URL(self) -> str:
        if not self.DB_PASS:
            raise RuntimeError("DB_PASS is not set. Add it to your .env file.")
        return f"postgresql://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    WINDOW: int = int(os.getenv("WINDOW", "300"))
    Z_ENTRY: float = float(os.getenv("Z_ENTRY", "1.5"))
    Z_STOP: float = float(os.getenv("Z_STOP", "3.5"))

    COMMISSION_RATE: float = 0.001
    SLIPPAGE_RATE: float = 0.0005

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    APP_USERNAME: str = os.getenv("APP_USERNAME", "admin")
    APP_PASSWORD: str = os.getenv("APP_PASSWORD", "")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "")

    ALLOWED_ORIGINS: list = [
        o.strip()
        for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:8000").split(",")
        if o.strip()
    ]

settings = Settings()