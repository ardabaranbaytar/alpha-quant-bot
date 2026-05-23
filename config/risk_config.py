from datetime import timedelta

class RiskConfig:
    MAX_OPEN_POSITIONS = 5          
    DAILY_DRAWDOWN_LIMIT = -500.0   
    
    MAX_STOCK_EXPOSURE = 2          
    COOLDOWN_HOURS = 4              
    
    TRADE_STOP_LOSS_USD = -300.0    
    TRANSACTION_COST_RATE = 0.0015  
    POSITION_SIZE_PER_LEG = 5000.0