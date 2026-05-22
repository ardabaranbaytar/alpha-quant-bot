# core/health_score.py

import logging
import pandas as pd
from sqlalchemy import text
from config.database import db

logger = logging.getLogger(__name__)

class FundamentalScorer:
    def __init__(self):
        self.scores = {}

    def sirketleri_skorla(self):
        """SQL ambarındaki en güncel bilançoları çekip kurumsal sağlık puanı üretir."""
        query = """
            WITH son_bilancolar AS (
                SELECT sembol, net_kar_milyar, faaliyet_kari_milyar, nakit_milyar, toplam_borc_milyar,
                       ROW_NUMBER() OVER (PARTITION BY sembol ORDER BY donem_sonu DESC) as sira
                FROM sirket_bilancolari
            )
            SELECT sembol, net_kar_milyar, faaliyet_kari_milyar, nakit_milyar, toplam_borc_milyar
            FROM son_bilancolar WHERE sira = 1;
        """
        try:
            with db.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            for r in df.itertuples():
                skor = 50
                if r.faaliyet_kari_milyar > 0: skor += 15
                if r.net_kar_milyar > 0: skor += 10
                
                nakit_borc = r.nakit_milyar / abs(r.toplam_borc_milyar) if r.toplam_borc_milyar != 0 else 1
                if nakit_borc > 0.5: skor += 15
                elif nakit_borc < 0.1: skor -= 20
                
                op_kalite = r.faaliyet_kari_milyar / abs(r.net_kar_milyar) if r.net_kar_milyar != 0 else 1
                if op_kalite >= 0.9: skor += 10
                
                self.scores[r.sembol] = max(0, min(100, skor))
                
            logger.info("Fundamental scoring complete: %d companies scored.", len(self.scores))
        except Exception as e:
            logger.error("Fundamental scoring failed: %s", e)

    def get_score(self, sembol: str) -> int:
        """Şirket puanını döner, eğer bilançosu yoksa nötr (50) kabul eder."""
        return self.scores.get(sembol, 50)

scorer = FundamentalScorer()