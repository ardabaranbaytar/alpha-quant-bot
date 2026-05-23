import logging
import pandas as pd
from sqlalchemy import text
from config.database import db

logger = logging.getLogger(__name__)

class FundamentalScorer:
    def __init__(self):
        self.scores = {}

    def score_companies(self):
        """Fetches the latest balance sheets from the SQL data warehouse and generates a corporate health score."""
        query = """
            WITH latest_balance_sheets AS (
                SELECT symbol, net_income_billion, operating_profit_billion, cash_billion, total_debt_billion,
                       ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY period_end DESC) as row_num
                FROM company_balance_sheets
            )
            SELECT symbol, net_income_billion, operating_profit_billion, cash_billion, total_debt_billion
            FROM latest_balance_sheets WHERE row_num = 1;
        """
        try:
            with db.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            for r in df.itertuples():
                score = 50
                if r.operating_profit_billion > 0: score += 15
                if r.net_income_billion > 0: score += 10
                
                cash_debt_ratio = r.cash_billion / abs(r.total_debt_billion) if r.total_debt_billion != 0 else 1
                if cash_debt_ratio > 0.5: score += 15
                elif cash_debt_ratio < 0.1: score -= 20
                
                op_quality = r.operating_profit_billion / abs(r.net_income_billion) if r.net_income_billion != 0 else 1
                if op_quality >= 0.9: score += 10
                
                self.scores[r.symbol] = max(0, min(100, score))
                
            logger.info("Fundamental scoring complete: %d companies scored.", len(self.scores))
        except Exception as e:
            logger.error("Fundamental scoring failed: %s", e)

    def get_score(self, symbol: str) -> int:
        """Returns the company score; assumes neutral (50) if no balance sheet is found."""
        return self.scores.get(symbol, 50)

scorer = FundamentalScorer()