import logging
import datetime
from apscheduler.schedulers.blocking import BlockingScheduler
from .yfinance_fetcher import fetcher

logger = logging.getLogger(__name__)

def hourly_price_task():
    logger.info("Hourly bar update triggered at %s", datetime.datetime.now())
    fetcher.inject_hourly_bars(period="3d")

def midnight_deep_scan():
    logger.info("Midnight deep sync started (23:40).")
    fetcher.inject_hourly_bars(period="2y")

def start_scheduler():
    scheduler = BlockingScheduler()
    
    scheduler.add_job(
        hourly_price_task, 
        'cron', 
        day_of_week='mon-fri', 
        hour='16-23', 
        minute='5' 
    )
    
    scheduler.add_job(
        midnight_deep_scan, 
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
    start_scheduler()