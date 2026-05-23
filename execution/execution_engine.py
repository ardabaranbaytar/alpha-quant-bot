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

    def _get_open_positions(self) -> dict:
        """Fetches all currently open positions from SQL as a dictionary."""
        query = "SELECT pair, id, price_a_entry, price_b_entry, action FROM positions WHERE status = 'OPEN';"
        with db.engine.connect() as conn:
            result = conn.execute(text(query)).mappings().fetchall()
        return {r['pair']: r for r in result}

    def _is_risk_approved(self, conn, pair, stock_A, stock_B) -> tuple[bool, str]:
        """Runs portfolio risk filters with raw SQL before opening a new trade."""
        
        query_drawdown = text("""
            SELECT COALESCE(SUM(pnl), 0) FROM positions 
            WHERE status = 'CLOSED' AND exit_time >= CURRENT_DATE;
        """)
        daily_pnl = conn.execute(query_drawdown).scalar() or 0.0
        if daily_pnl <= RiskConfig.DAILY_DRAWDOWN_LIMIT:
            return False, f"Daily Drawdown Limit Hit (${daily_pnl:.2f})"

        query_count = text("SELECT COUNT(*) FROM positions WHERE status = 'OPEN';")
        open_count = conn.execute(query_count).scalar() or 0
        if open_count >= RiskConfig.MAX_OPEN_POSITIONS:
            return False, f"Max Open Positions Reached ({open_count})"

        query_exposure = text("SELECT pair FROM positions WHERE status = 'OPEN';")
        open_pairs = conn.execute(query_exposure).scalars().all()
        
        active_stocks = []
        for p in open_pairs:
            active_stocks.extend(p.split(" / "))
            
        if active_stocks.count(stock_A) >= RiskConfig.MAX_STOCK_EXPOSURE:
            return False, f"Max Exposure Limit Hit for {stock_A}"
        if active_stocks.count(stock_B) >= RiskConfig.MAX_STOCK_EXPOSURE:
            return False, f"Max Exposure Limit Hit for {stock_B}"

        query_cooldown = text("""
            SELECT MAX(exit_time) FROM positions 
            WHERE status = 'CLOSED' AND pair = :pair;
        """)
        last_close = conn.execute(query_cooldown, {"pair": pair}).scalar()
        if last_close:
            elapsed_time = datetime.datetime.now() - last_close
            limit_time = datetime.timedelta(hours=RiskConfig.COOLDOWN_HOURS)
            if elapsed_time < limit_time:
                minutes_left = int((limit_time - elapsed_time).total_seconds() / 60)
                return False, f"Pair in Cooldown ({minutes_left} min left)"

        return True, "Risk Approved"

    def manage_orders_and_positions(self):
        """Main loop that synchronizes the signal radar with the database ledger."""
        logger.info("Execution cycle triggered at %s", datetime.datetime.now().strftime('%H:%M:%S'))
        
        current_opportunities = signals_hub.scan_instant_opportunities()
        open_positions = self._get_open_positions()
        df_matrix = signals_hub._build_price_matrix()
        
        signaled_pairs = [f['pair'] for f in current_opportunities]
        
        for pair, p_data in list(open_positions.items()):
            stock_A, stock_B = pair.split(" / ")
            if stock_A in df_matrix.columns and stock_B in df_matrix.columns:
                price_A_current = float(df_matrix[stock_A].iloc[-1])
                price_B_current = float(df_matrix[stock_B].iloc[-1])
                
                return_A = (price_A_current - float(p_data['price_a_entry'])) / float(p_data['price_a_entry'])
                return_B = (price_B_current - float(p_data['price_b_entry'])) / float(p_data['price_b_entry'])
                
                if p_data['action'].startswith("BUY"):
                    gross_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * return_A) - (RiskConfig.POSITION_SIZE_PER_LEG * return_B)
                else:
                    gross_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * return_B) - (RiskConfig.POSITION_SIZE_PER_LEG * return_A)
                    
                cost = (RiskConfig.POSITION_SIZE_PER_LEG * 2) * RiskConfig.TRANSACTION_COST_RATE
                current_net_pnl = gross_pnl - cost
                
                if current_net_pnl <= RiskConfig.TRADE_STOP_LOSS_USD:
                    logger.warning("STOP-LOSS triggered for %s. Net PnL: $%.2f", pair, current_net_pnl)
                    query_stop = text("""
                        UPDATE positions 
                        SET status = 'CLOSED', exit_time = CURRENT_TIMESTAMP,
                            price_a_exit = :pA, price_b_exit = :pB, pnl = :pnl
                        WHERE id = :id;
                    """)
                    with db.engine.begin() as conn:
                        conn.execute(query_stop, {"pA": price_A_current, "pB": price_B_current, "pnl": round(current_net_pnl, 2), "id": p_data['id']})
                    open_positions.pop(pair)

        for f in current_opportunities:
            pair = f['pair']
            if pair not in open_positions:
                stock_A, stock_B = pair.split(" / ")
                
                with db.engine.connect() as conn:
                    is_approved, reason = self._is_risk_approved(conn, pair, stock_A, stock_B)
                
                if not is_approved:
                    logger.info("Signal for %s blocked by risk engine: %s", pair, reason)
                    continue
                
                logger.info("Opening position for %s. Action: %s", pair, f['action'])
                
                query_insert = text("""
                    INSERT INTO positions (pair, entry_z_score, price_a_entry, price_b_entry, status, action)
                    VALUES (:pair, :z, :pA, :pB, 'OPEN', :action);
                """)
                with db.engine.begin() as conn:
                    conn.execute(query_insert, {
                        "pair": pair, "z": f['z_score'], 
                        "pA": f['price_A'], "pB": f['price_B'], "action": f['action']
                    })
                logger.info("Position opened and recorded: %s", pair)

        for pair, p_data in open_positions.items():
            if pair not in signaled_pairs:
                logger.info("Closing position for %s: ratio reverted to mean.", pair)
                
                stock_A, stock_B = pair.split(" / ")
                price_A_exit = float(df_matrix[stock_A].iloc[-1])
                price_B_exit = float(df_matrix[stock_B].iloc[-1])
                
                return_A = (price_A_exit - float(p_data['price_a_entry'])) / float(p_data['price_a_entry'])
                return_B = (price_B_exit - float(p_data['price_b_entry'])) / float(p_data['price_b_entry'])
                
                if p_data['action'].startswith("BUY"): 
                    gross_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * return_A) - (RiskConfig.POSITION_SIZE_PER_LEG * return_B)
                else:
                    gross_pnl = (RiskConfig.POSITION_SIZE_PER_LEG * return_B) - (RiskConfig.POSITION_SIZE_PER_LEG * return_A)
                    
                cost = (RiskConfig.POSITION_SIZE_PER_LEG * 2) * RiskConfig.TRANSACTION_COST_RATE
                net_pnl = gross_pnl - cost
                
                query_update = text("""
                    UPDATE positions 
                    SET status = 'CLOSED', exit_time = CURRENT_TIMESTAMP,
                        price_a_exit = :pA, price_b_exit = :pB, pnl = :pnl
                    WHERE id = :id;
                """)
                with db.engine.begin() as conn:
                    conn.execute(query_update, {"pA": price_A_exit, "pB": price_B_exit, "pnl": round(net_pnl, 2), "id": p_data['id']})
                logger.info("Position closed: %s. Net PnL: $%.2f", pair, net_pnl)

execution_engine = ExecutionEngine()