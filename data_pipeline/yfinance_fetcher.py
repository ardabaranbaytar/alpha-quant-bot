import logging
import pandas as pd
import yfinance as yf
import requests
from sqlalchemy import text
import time
from config.database import db

logger = logging.getLogger(__name__)

class DataFetcher:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def update_nasdaq100_list(self) -> list:
        """Autonomously scrapes the updated list from Wikipedia."""
        logger.info("Fetching NASDAQ-100 list from Wikipedia.")
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        try:
            res = requests.get(url, headers=self.headers, timeout=15)
            res.raise_for_status()
            tables = pd.read_html(res.text)
            for df in tables:
                if 'Ticker' in df.columns: return [s.replace('.', '-') for s in df['Ticker'].tolist()]
                if 'Symbol' in df.columns: return [s.replace('.', '-') for s in df['Symbol'].tolist()]
        except Exception as e:
            logger.warning("Could not scrape NASDAQ-100 list, using fallback: %s", e)
        return ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "NFLX", "INTC", "QCOM", "AVGO"]

    def inject_hourly_bars(self, period="2y"):
        """Fetches data for the entire universe and writes it to the SQL warehouse using UPSERT logic."""
        symbols = self.update_nasdaq100_list()
        logger.info("Starting hourly bar injection for %d symbols.", len(symbols))
        
        insert_query = text("""
            INSERT INTO stock_prices (date, symbol, price) 
            VALUES (:date, :symbol, :price)
            ON CONFLICT (symbol, date) DO NOTHING;
        """)
        
        with db.engine.begin() as connection:
            for idx, symbol in enumerate(symbols, 1):
                try:
                    time.sleep(0.3) 
                    data = yf.download(symbol, period=period, interval="1h", progress=False)
                    if data.empty: continue
                    
                    dates = data.index.tz_localize(None)
                    prices = data['Close'].values.flatten()
                    
                    added = 0
                    for t, p in zip(dates, prices):
                        res = connection.execute(insert_query, {"date": t, "symbol": symbol, "price": float(p)})
                        if res.rowcount > 0: added += 1
                        
                    if added > 0:
                        logger.debug("[%d/%d] %s: %d new bars inserted.", idx, len(symbols), symbol, added)
                except Exception as e:
                    logger.error("Failed to download %s: %s", symbol, e)
                    
        logger.info("Bar injection cycle completed.")

fetcher = DataFetcher()