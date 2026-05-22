# data_pipeline/yfinance_fetcher.py

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

    def nasdaq100_listesini_guncelle(self) -> list:
        """Wikipedia üzerinden güncel listeyi otonom kazır."""
        logger.info("Fetching NASDAQ-100 list from Wikipedia.")
        url = "https://en.wikipedia.org/wiki/Nasdaq-100"
        try:
            res = requests.get(url, headers=self.headers, timeout=15)
            res.raise_for_status()
            tablolar = pd.read_html(res.text)
            for df in tablolar:
                if 'Ticker' in df.columns: return [s.replace('.', '-') for s in df['Ticker'].tolist()]
                if 'Symbol' in df.columns: return [s.replace('.', '-') for s in df['Symbol'].tolist()]
        except Exception as e:
            logger.warning("Could not scrape NASDAQ-100 list, using fallback: %s", e)
        return ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD", "NFLX", "INTC", "QCOM", "AVGO"]

    def saatlik_bar_enjekte_et(self, period="2y"):
        """Tüm evrenin verilerini çekip UPSERT mantığıyla SQL ambarına yazar."""
        hisseler = self.nasdaq100_listesini_guncelle()
        logger.info("Starting hourly bar injection for %d symbols.", len(hisseler))
        
        insert_query = text("""
            INSERT INTO hisse_fiyatlari (tarih, sembol, fiyat) 
            VALUES (:tarih, :sembol, :fiyat)
            ON CONFLICT (sembol, tarih) DO NOTHING;
        """)
        
        # Database manager üzerinden motoru al ve transaction başlat
        with db.engine.begin() as connection:
            for idx, sembol in enumerate(hisseler, 1):
                try:
                    time.sleep(0.3) # Hız sınırı koruması
                    veri = yf.download(sembol, period=period, interval="1h", progress=False)
                    if veri.empty: continue
                    
                    tarihler = veri.index.tz_localize(None)
                    fiyatlar = veri['Close'].values.flatten()
                    
                    eklenen = 0
                    for t, f in zip(tarihler, fiyatlar):
                        res = connection.execute(insert_query, {"tarih": t, "sembol": sembol, "fiyat": float(f)})
                        if res.rowcount > 0: eklenen += 1
                        
                    if eklenen > 0:
                        logger.debug("[%d/%d] %s: %d new bars inserted.", idx, len(hisseler), sembol, eklenen)
                except Exception as e:
                    logger.error("Failed to download %s: %s", sembol, e)
                    
        logger.info("Bar injection cycle completed.")

fetcher = DataFetcher()