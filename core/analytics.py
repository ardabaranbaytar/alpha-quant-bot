# core/analytics.py

import logging
import pandas as pd
import numpy as np
from sqlalchemy import text
from config.database import db

logger = logging.getLogger(__name__)

class PerformanceAnalytics:
    def __init__(self):
        pass

    def _get_kapali_pozisyonlar(self) -> pd.DataFrame:
        """Veritabanından kapanmış tüm pozisyonları kronolojik sıra ile DataFrame'e çeker."""
        # 💡 DÜZELTME: net_pnl yerine senin şemandaki orijinal 'pnl' kolonu çağrıldı
        query = """
            SELECT parite, durum, pnl, giris_tarihi, cikis_tarihi 
            FROM pozisyonlar 
            WHERE durum = 'KAPALI' 
            ORDER BY cikis_tarihi ASC;
        """
        try:
            with db.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            if not df.empty:
                df['giris_tarihi'] = pd.to_datetime(df['giris_tarihi'])
                df['cikis_tarihi'] = pd.to_datetime(df['cikis_tarihi'])
            return df
        except Exception as e:
            logger.error("Failed to read position history: %s", e)
            return pd.DataFrame()

    def rapor_uret(self, csv_kaydet: bool = True) -> dict:
        """Tüm quant metriklerini hesaplar ve özet bir rapor sözlüğü döner."""
        df = self._get_kapali_pozisyonlar()
        
        if df.empty:
            logger.info("No closed positions found. Returning empty report.")
            return {
                "Total PnL": "$0.00", 
                "Win Rate": "%0.00", 
                "Profit Factor": "0.00", 
                "Max Drawdown": "$0.00"
            }

        # --- Temel Metrikler ---
        toplam_islem = len(df)
        toplam_net_pnl = df['pnl'].sum()  # 💡 DÜZELTME: 'pnl' olarak güncellendi
        
        kazananlar = df[df['pnl'] > 0]
        kaybedenler = df[df['pnl'] <= 0]
        
        kazanan_sayisi = len(kazananlar)
        win_rate = (kazanan_sayisi / toplam_islem) * 100 if toplam_islem > 0 else 0
        
        avg_win = kazananlar['pnl'].mean() if not kazananlar.empty else 0.0
        avg_loss = kaybedenler['pnl'].mean() if not kaybedenler.empty else 0.0
        
        toplam_kazanc = kazananlar['pnl'].sum()
        toplam_zarar = abs(kaybedenler['pnl'].sum())
        profit_factor = toplam_kazanc / toplam_zarar if toplam_zarar > 0 else toplam_kazanc

        # --- Gelişmiş Metrikler ---
        df['holding_time'] = df['cikis_tarihi'] - df['giris_tarihi']
        avg_holding_time = df['holding_time'].mean()
        
        parite_gruplari = df.groupby('parite')['pnl'].sum()
        en_iyi_parite = parite_gruplari.idxmax() if not parite_gruplari.empty else "N/A"
        en_kotu_parite = parite_gruplari.idxmin() if not parite_gruplari.empty else "N/A"

        # 📉 Maksimum Düşüş (Max Drawdown) Hesaplama
        bakiye_egrisi = 100000 + df['pnl'].cumsum()
        kumulatif_zirve = bakiye_egrisi.cummax()
        dususler = bakiye_egrisi - kumulatif_zirve
        max_drawdown = dususler.min() if not dususler.empty else 0.0

        rapor = {
            "Durum": "OPERATIONAL",
            "Total PnL": f"${toplam_net_pnl:,.2f}",
            "Win Rate": f"%{win_rate:.2f}",
            "Profit Factor": f"{profit_factor:.2f}",
            "Max Drawdown": f"${max_drawdown:,.2f}",
            "Average Win": f"${avg_win:,.2f}",
            "Average Loss": f"${avg_loss:,.2f}",
            "Number of Trades": toplam_islem,
            "Avg Holding Time": str(avg_holding_time).split('.')[0],
            "Best Pair": en_iyi_parite,
            "Worst Pair": en_kotu_parite,
            "Timestamp": pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        if csv_kaydet:
            try:
                rapor_df = pd.DataFrame(list(rapor.items()), columns=['Metrik', 'Değer'])
                rapor_df.to_csv("logs/performance_report.csv", index=False, encoding='utf-8')
                logger.info("Performance report saved to logs/performance_report.csv")
            except Exception as e:
                logger.warning("Could not save CSV report: %s", e)

        return rapor

analytics_manager = PerformanceAnalytics()