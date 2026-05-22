# config.py
from datetime import timedelta

class RiskConfig:
    # --- Portföy Seviyesi Risk Limitleri ---
    MAX_OPEN_POSITIONS = 5          # Aynı anda açık olabilecek maksimum parite sayısı
    DAILY_DRAWDOWN_LIMIT = -500.0   # Günlük maksimum gerçekleşen zarar eşiği ($)
    
    # --- Varlık Seviyesi Risk Limitleri ---
    MAX_STOCK_EXPOSURE = 2          # Bir hissenin (Örn: AAPL) farklı paritelerde maksimum yer alma sayısı
    COOLDOWN_HOURS = 4              # Kapatılan bir pariteye yeniden girmek için gereken minimum süre
    
    # --- Trade Seviyesi Risk Limitleri ---
    TRADE_STOP_LOSS_USD = -300.0    # Pozisyon başına maksimum katlanılabilir net zarar ($)
    TRANSACTION_COST_RATE = 0.0015  # %0.15 Brüt işlem maliyeti oranı (giriş + çıkış toplamı)
    POSITION_SIZE_PER_LEG = 5000.0  # Her bir bacak için işlem büyüklüğü ($)