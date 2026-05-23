import logging
import pandas as pd
import numpy as np
import itertools
from sqlalchemy import text
from statsmodels.tsa.stattools import coint
from config.database import db
from config.settings import settings
from .health_score import scorer

logger = logging.getLogger(__name__)

class SignalGenerator:
    def __init__(self):
        self.candidate_pool = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'GOOGL', 'META', 'AMD', 'NFLX', 'INTC', 'QCOM', 'AVGO']

    def _build_price_matrix(self) -> pd.DataFrame:
        """Builds a clean price matrix by flattening time mismatches."""
        with db.engine.connect() as conn:
            available_stocks = [r[0] for r in conn.execute(text("SELECT DISTINCT symbol FROM stock_prices;")).fetchall()]
            
        to_watch = [s for s in available_stocks if s in self.candidate_pool]
        data_dict = {}
        
        for stock in to_watch:
            df = pd.read_sql(
                text("SELECT date, price FROM stock_prices WHERE symbol = :symbol ORDER BY date"),
                db.engine,
                params={"symbol": stock}
            )
            if not df.empty:
                df['date'] = pd.to_datetime(df['date']).dt.round('h')
                df = df.drop_duplicates(subset=['date'])
                data_dict[stock] = df.set_index('date')['price']
                
        return pd.DataFrame(data_dict).sort_index().ffill().bfill()

    def scan_instant_opportunities(self) -> list:
        """Scans the entire universe and returns pairs that are currently in an order state."""
        scorer.score_companies()
        
        df_matrix = self._build_price_matrix()
        if df_matrix.empty:
            logger.warning("Price matrix is empty, scan aborted.")
            return []
            
        pairs = list(itertools.combinations(df_matrix.columns, 2))
        opportunities = []
        
        logger.info("Scanning %d pairs for signals.", len(pairs))
        
        for stock_A, stock_B in pairs:
            score_A = scorer.get_score(stock_A)
            score_B = scorer.get_score(stock_B)
            
            if abs(score_A - score_B) > 30: continue
            
            _, p_value, _ = coint(df_matrix[stock_A], df_matrix[stock_B])
            if p_value > 0.02: continue # Search for super stable cointegration
            
            ratio = df_matrix[stock_A] / df_matrix[stock_B]
            mean = ratio.rolling(settings.WINDOW).mean()
            std = ratio.rolling(settings.WINDOW).std()
            z_scores = (ratio - mean) / std
            
            if z_scores.empty or z_scores.isna().all(): continue
            
            current_z = z_scores.iloc[-1]
            price_A = df_matrix[stock_A].iloc[-1]
            price_B = df_matrix[stock_B].iloc[-1]
            
            action = "WAIT"
            if settings.Z_ENTRY < current_z < settings.Z_STOP and score_B >= score_A - 10:
                action = f"SELL {stock_A} / BUY {stock_B}"
            elif -settings.Z_STOP < current_z < -settings.Z_ENTRY and score_A >= score_B - 10:
                action = f"BUY {stock_A} / SELL {stock_B}"
                
            if action != "WAIT":
                opportunities.append({
                    "pair": f"{stock_A} / {stock_B}",
                    "z_score": round(current_z, 3),
                    "price_A": round(price_A, 2),
                    "price_B": round(price_B, 2),
                    "p_value": round(p_value, 4),
                    "action": action
                })
                
        return opportunities

signals_hub = SignalGenerator()