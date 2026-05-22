# data_pipeline/scheduler.py

import logging
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from .yfinance_fetcher import fetcher

logger = logging.getLogger(__name__)

def saatlik_fiyat_gorevi():
    ### Seans açıkken (TSİ 16:30 - 23:00 arası veya genel takip için) saat başı tetiklenir
    logger.info("Hourly bar update triggered at %s", datetime.datetime.now())
    # Son 3 günlük barları çekmesi anlık güncelleme için yeterlidir (Performans kalkanı)
    fetcher.saatlik_bar_enjekte_et(period="3d")

def gece_yarisi_derin_tarama():
    ### Senin özel emrin: Her gece tam 23:40'ta tüm 2 yıllık geçmişi ve evreni check-up yapar
    logger.info("Midnight deep sync started (23:40).")
    fetcher.saatlik_bar_enjekte_et(period="2y")

def zamanlayiciyi_ateşle():
    scheduler = BlockingScheduler()
    
    # 1. Görev: Her saat başı fiyatları tazele (Pazartesi - Cuma arası)
    scheduler.add_job(
        saatlik_fiyat_gorevi, 
        'cron', 
        day_of_week='mon-fri', 
        hour='16-23', 
        minute='5' # Seans içi barlar kapandıktan 5 dakika sonra
    )
    
    # 2. Görev: Senin talimatın üzere her gece tam 23:40'ta derin tarama yap
    scheduler.add_job(
        gece_yarisi_derin_tarama, 
        'cron', 
        hour='23', 
        minute='40'
    )
    
    logger.info("Data pipeline scheduler started.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler shut down.")

if __name__ == "__main__":
    zamanlayiciyi_ateşle()