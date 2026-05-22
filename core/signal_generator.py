# core/signal_generator.py

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
        # İzlenecek kurumsal lider kadro (Sınırları zorlamamak ve RAM'i korumak için)
        self.aday_havuz = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMZN', 'GOOGL', 'META', 'AMD', 'NFLX', 'INTC', 'QCOM', 'AVGO']

    def _fiyat_matrisini_kur(self) -> pd.DataFrame:
        """Zaman uyumsuzluklarını ezerek temiz bir fiyat matrisi kurar."""
        with db.engine.connect() as conn:
            mevcut_hisseler = [r[0] for r in conn.execute(text("SELECT DISTINCT sembol FROM hisse_fiyatlari;")).fetchall()]
            
        izlenecekler = [h for h in mevcut_hisseler if h in self.aday_havuz]
        veri_sozlugu = {}
        
        for hisse in izlenecekler:
            df = pd.read_sql(
                text("SELECT tarih, fiyat FROM hisse_fiyatlari WHERE sembol = :sembol ORDER BY tarih"),
                db.engine,
                params={"sembol": hisse}
            )
            if not df.empty:
                df['tarih'] = pd.to_datetime(df['tarih']).dt.round('h')
                df = df.drop_duplicates(subset=['tarih'])
                veri_sozlugu[hisse] = df.set_index('tarih')['fiyat']
                
        return pd.DataFrame(veri_sozlugu).sort_index().ffill().bfill()

    def anlik_firsatlari_tara(self) -> list:
        """Tüm evreni tarayıp anlık emir durumunda olan pariteleri döner."""
        # 1. Temel skorları arkada güncelle
        scorer.sirketleri_skorla()
        
        # 2. Fiyat matrisini yükle
        df_matris = self._fiyat_matrisini_kur()
        if df_matris.empty:
            logger.warning("Price matrix is empty, scan aborted.")
            return []
            
        ciftler = list(itertools.combinations(df_matris.columns, 2))
        firsatlar = []
        
        logger.info("Scanning %d pairs for signals.", len(ciftler))
        
        for hisse_A, hisse_B in ciftler:
            puan_A = scorer.get_score(hisse_A)
            puan_B = scorer.get_score(hisse_B)
            
            # Temel analiz kalkanı
            if abs(puan_A - puan_B) > 30: continue
            
            # İstatistiksel kointegrasyon kalkanı
            _, p_value, _ = coint(df_matris[hisse_A], df_matris[hisse_B])
            if p_value > 0.02: continue # Süper kararlı bağ arayışı
            
            # Z-Score Hesaplama Matematik Bloğu
            rasyo = df_matris[hisse_A] / df_matris[hisse_B]
            ortalama = rasyo.rolling(settings.PENCERE).mean()
            std = rasyo.rolling(settings.PENCERE).std()
            z_skorlari = (rasyo - ortalama) / std
            
            if z_skorlari.empty or z_skorlari.isna().all(): continue
            
            anlik_z = z_skorlari.iloc[-1]
            fiyat_A = df_matris[hisse_A].iloc[-1]
            fiyat_B = df_matris[hisse_B].iloc[-1]
            
            aksiyon = "BEKLE"
            if settings.Z_GIRIS < anlik_z < settings.Z_STOP and puan_B >= puan_A - 10:
                aksiyon = f"SELL {hisse_A} / BUY {hisse_B}"
            elif -settings.Z_STOP < anlik_z < -settings.Z_GIRIS and puan_A >= puan_B - 10:
                aksiyon = f"BUY {hisse_A} / SELL {hisse_B}"
                
            if aksiyon != "BEKLE":
                firsatlar.append({
                    "parite": f"{hisse_A} / {hisse_B}",
                    "z_score": round(anlik_z, 3),
                    "fiyat_A": round(fiyat_A, 2),
                    "fiyat_B": round(fiyat_B, 2),
                    "p_value": round(p_value, 4),
                    "aksiyon": aksiyon
                })
                
        return firsatlar

signals_hub = SignalGenerator()