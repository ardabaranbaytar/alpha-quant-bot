# execution/execution_engine.py

import logging
import pandas as pd
from sqlalchemy import text
import datetime
from config.database import db
from config.risk_config import RiskConfig
from core.signal_generator import signals_hub

logger = logging.getLogger(__name__)

class ExecutionEngine:
    def __init__(self):
        pass

    def _get_acik_pozisyonlar(self) -> dict:
        """SQL'den şu an açık olan tüm pozisyonları sözlük olarak çeker."""
        query = "SELECT parite, id, fiyat_A_giris, fiyat_B_giris, aksiyon FROM pozisyonlar WHERE durum = 'ACIK';"
        with db.engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchall()
        return {r['parite']: r for r in result}

    def _risk_izni_var_mi(self, conn, parite, hisse_A, hisse_B) -> tuple[bool, str]:
        """Yeni işlem açılmadan önce ham SQL ile portföy risk filtrelerini çalıştırır."""
        
        # 1. Günlük Zarar Kes (Daily Drawdown) Kontrolü
        query_drawdown = text("""
            SELECT COALESCE(SUM(pnl), 0) FROM pozisyonlar 
            WHERE durum = 'KAPALI' AND cikis_tarihi >= CURRENT_DATE;
        """)
        gunluk_pnl = conn.execute(query_drawdown).scalar() or 0.0
        if gunluk_pnl <= RiskConfig.DAILY_DRAWDOWN_LIMIT:
            return False, f"Daily Drawdown Limit Hit (${gunluk_pnl:.2f})"

        # 2. Maksimum Açık Pozisyon Sayısı Kontrolü
        query_count = text("SELECT COUNT(*) FROM pozisyonlar WHERE durum = 'ACIK';")
        acik_sayisi = conn.execute(query_count).scalar() or 0
        if acik_sayisi >= RiskConfig.MAX_OPEN_POSITIONS:
            return False, f"Max Open Positions Reached ({acik_sayisi})"

        # 3. Tek Hisse Maruziyeti (Exposure) Kontrolü
        query_exposure = text("SELECT parite FROM pozisyonlar WHERE durum = 'ACIK';")
        acik_pariteler = conn.execute(query_exposure).scalars().all()
        
        aktif_hisseler = []
        for p in acik_pariteler:
            aktif_hisseler.extend(p.split(" / "))
            
        if aktif_hisseler.count(hisse_A) >= RiskConfig.MAX_STOCK_EXPOSURE:
            return False, f"Max Exposure Limit Hit for {hisse_A}"
        if aktif_hisseler.count(hisse_B) >= RiskConfig.MAX_STOCK_EXPOSURE:
            return False, f"Max Exposure Limit Hit for {hisse_B}"

        # 4. Sakinleşme Süresi (Cooldown) Kontrolü
        query_cooldown = text("""
            SELECT MAX(cikis_tarihi) FROM pozisyonlar 
            WHERE durum = 'KAPALI' AND parite = :parite;
        """)
        son_kapanma = conn.execute(query_cooldown, {"parite": parite}).scalar()
        if son_kapanma:
            gecen_sure = datetime.datetime.now() - son_kapanma
            limit_sure = datetime.timedelta(hours=RiskConfig.COOLDOWN_HOURS)
            if gecen_sure < limit_sure:
                kalan_dakika = int((limit_sure - gecen_sure).total_seconds() / 60)
                return False, f"Pair in Cooldown ({kalan_dakika} min left)"

        return True, "Risk Approved"

    def emir_ve_pozisyon_yonet(self):
        """Sinyal radarı ile veritabanı defterini senkronize eden ana döngü."""
        logger.info("Execution cycle triggered at %s", datetime.datetime.now().strftime('%H:%M:%S'))
        
        # Anlık üretilen sinyalleri ve şu an açık olan pozisyonları çek
        anlik_firsatlar = signals_hub.anlik_firsatlari_tara()
        acik_pozisyonlar = self._get_acik_pozisyonlar()
        df_matris = signals_hub._fiyat_matrisini_kur()
        
        sinyal_veren_pariteler = [f['parite'] for f in anlik_firsatlar]
        
        # 🏛️ ADIM C: ANLIK STOP-LOSS KONTROLÜ (Risk Koruma Kalkanı)
        for parite, p_data in list(acik_pozisyonlar.items()):
            hisse_A, hisse_B = parite.split(" / ")
            if hisse_A in df_matris.columns and hisse_B in df_matris.columns:
                fiyat_A_guncel = float(df_matris[hisse_A].iloc[-1])
                fiyat_B_guncel = float(df_matris[hisse_B].iloc[-1])
                
                getiri_A = (fiyat_A_guncel - float(p_data['fiyat_A_giris'])) / float(p_data['fiyat_A_giris'])
                getiri_B = (fiyat_B_guncel - float(p_data['fiyat_B_giris'])) / float(p_data['fiyat_B_giris'])
                
                if p_data['aksiyon'].startswith("BUY"):
                    brut_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * getiri_A) - (RiskConfig.POSITION_SIZE_PER_LEG * getiri_B)
                else:
                    brut_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * getiri_B) - (RiskConfig.POSITION_SIZE_PER_LEG * getiri_A)
                    
                maliyet = (RiskConfig.POSITION_SIZE_PER_LEG * 2) * RiskConfig.TRANSACTION_COST_RATE
                anlik_net_pnl = brut_pnl - maliyet
                
                # Eğer anlık zarar stop limitini aşmışsa acil kapatma tetikle
                if anlik_net_pnl <= RiskConfig.TRADE_STOP_LOSS_USD:
                    logger.warning("STOP-LOSS triggered for %s. Net PnL: $%.2f", parite, anlik_net_pnl)
                    query_stop = text("""
                        UPDATE pozisyonlar 
                        SET durum = 'KAPALI', cikis_tarihi = CURRENT_TIMESTAMP,
                            fiyat_A_cikis = :fA, fiyat_B_cikis = :fB, pnl = :pnl
                        WHERE id = :id;
                    """)
                    with db.engine.begin() as conn:
                        conn.execute(query_stop, {"fA": fiyat_A_guncel, "fB": fiyat_B_guncel, "pnl": round(anlik_net_pnl, 2), "id": p_data['id']})
                    # Diğer döngülerde tekrar işleme girmemesi için aktif listeden düşüyoruz
                    acik_pozisyonlar.pop(parite)

        # 🏛️ ADIM A: YENİ POZİSYON AÇMA DÖNGÜSÜ
        for f in anlik_firsatlar:
            parite = f['parite']
            if parite not in acik_pozisyonlar:
                hisse_A, hisse_B = parite.split(" / ")
                
                # Bağlantıyı açıp risk onay mekanizmasını tetikliyoruz
                with db.engine.connect() as conn:
                    izin_var, sebep = self._risk_izni_var_mi(conn, parite, hisse_A, hisse_B)
                
                if not izin_var:
                    logger.info("Signal for %s blocked by risk engine: %s", parite, sebep)
                    continue
                
                # Risk onayından geçtiyse içeri dal!
                logger.info("Opening position for %s. Action: %s", parite, f['aksiyon'])
                
                query_insert = text("""
                    INSERT INTO pozisyonlar (parite, giris_z_score, fiyat_A_giris, fiyat_B_giris, durum, aksiyon)
                    VALUES (:parite, :z, :fA, :fB, 'ACIK', :aksiyon);
                """)
                with db.engine.begin() as conn:
                    conn.execute(query_insert, {
                        "parite": parite, "z": f['z_score'], 
                        "fA": f['fiyat_A'], "fB": f['fiyat_B'], "aksiyon": f['aksiyon']
                    })
                logger.info("Position opened and recorded: %s", parite)

        # 🏛️ ADIM B: MEVCUT POZİSYONLARI KAPATMA DÖNGÜSÜ (Mean Reversion / Kar Al)
        for parite, p_data in acik_pozisyonlar.items():
            if parite not in sinyal_veren_pariteler:
                logger.info("Closing position for %s: ratio reverted to mean.", parite)
                
                hisse_A, hisse_B = parite.split(" / ")
                fiyat_A_cikis = float(df_matris[hisse_A].iloc[-1])
                fiyat_B_cikis = float(df_matris[hisse_B].iloc[-1])
                
                getiri_A = (fiyat_A_cikis - float(p_data['fiyat_A_giris'])) / float(p_data['fiyat_A_giris'])
                getiri_B = (fiyat_B_cikis - float(p_data['fiyat_B_giris'])) / float(p_data['fiyat_B_giris'])
                
                if p_data['aksiyon'].startswith("BUY"): 
                    brut_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * getiri_A) - (RiskConfig.POSITION_SIZE_PER_LEG * getiri_B)
                else:
                    brut_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * getiri_B) - (RiskConfig.POSITION_SIZE_PER_LEG * getiri_A)
                    
                maliyet = (RiskConfig.POSITION_SIZE_PER_LEG * 2) * RiskConfig.TRANSACTION_COST_RATE
                net_pnl = brut_pnl - maliyet
                
                query_update = text("""
                    UPDATE pozisyonlar 
                    SET durum = 'KAPALI', cikis_tarihi = CURRENT_TIMESTAMP,
                        fiyat_A_cikis = :fA, fiyat_B_cikis = :fB, pnl = :pnl
                    WHERE id = :id;
                """)
                with db.engine.begin() as conn:
                    conn.execute(query_update, {"fA": fiyat_A_cikis, "fB": fiyat_B_cikis, "pnl": round(net_pnl, 2), "id": p_data['id']})
                logger.info("Position closed: %s. Net PnL: $%.2f", parite, net_pnl)

execution_engine = ExecutionEngine()