"""Paper Trading Accounting Engine enforcing balance sheet equations and execution constraints."""

import os
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from src.agents.schemas import TradeDecision
from src.database.models import PositionCreate, TransactionCreate
from src.database.supabase_client import SupabaseDBClient

logger = logging.getLogger(__name__)


def setup_execution_file_logging() -> str:
    """Ensure logs directory exists and return daily log file path."""
    os.makedirs("./logs", exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f"./logs/raw_execution_{today}.log"


def log_raw_execution(message: str) -> None:
    """Append detailed execution log entry to daily log file."""
    log_path = setup_execution_file_logging()
    timestamp = datetime.now(timezone.utc).isoformat()
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


class PaperTradingEngine:
    """Engine executing paper trade decisions against balance sheet constraints."""

    def __init__(self, db_client: Optional[SupabaseDBClient] = None) -> None:
        self.db_client = db_client or SupabaseDBClient()

    def process_decision(
        self,
        portfolio_id: str,
        decision: TradeDecision,
        current_price: float,
        agent_name: str = "Portfolio Manager"
    ) -> Dict[str, Any]:
        """
        Execute paper trade decision enforcing cash and position balance sheet constraints.
        
        :param portfolio_id: Portfolio UUID or string identifier
        :param decision: Validated TradeDecision model
        :param current_price: Latest market price of ticker
        :param agent_name: Name of executing agent
        :return: Execution summary dictionary
        """
        symbol = decision.symbol
        action = decision.action
        requested_qty = decision.quantity
        reasoning = decision.reasoning

        log_raw_execution(
            f"Processing trade decision for Portfolio '{portfolio_id}': "
            f"Action={action}, Symbol={symbol}, Qty={requested_qty}, Price=${current_price:.2f}"
        )

        # 1. Fetch current portfolio and position state
        portfolio = self.db_client.get_portfolio_by_id(portfolio_id) or self.db_client.get_or_create_portfolio(portfolio_id)
        current_cash = float(portfolio.get("current_cash", 10000.00))

        positions = self.db_client.get_positions(portfolio_id)
        existing_pos = next((p for p in positions if p.get("symbol") == symbol), None)

        owned_qty = float(existing_pos.get("quantity", 0.0)) if existing_pos else 0.0
        old_avg_buy_price = float(existing_pos.get("avg_buy_price", 0.0)) if existing_pos else 0.0

        executed_qty = requested_qty
        executed_price = current_price
        final_action = action
        adjusted_reasoning = reasoning

        # 2. Enforce execution constraints
        if action == "BUY":
            total_cost = requested_qty * current_price
            if total_cost > current_cash:
                max_possible_qty = math.floor(current_cash / current_price) if current_price > 0 else 0
                if max_possible_qty > 0:
                    executed_qty = float(max_possible_qty)
                    adjusted_reasoning = f"{reasoning} (ADJUSTED: Cash insufficient for {requested_qty} shares. Quantity reduced to {executed_qty})."
                    log_raw_execution(f"BUY constraint triggered: Cash ${current_cash:.2f} < ${total_cost:.2f}. Reduced Qty to {executed_qty}.")
                else:
                    final_action = "HOLD"
                    executed_qty = 0.0
                    adjusted_reasoning = f"{reasoning} (REJECTED: Insufficient cash (${current_cash:.2f}) to purchase 1 share at ${current_price:.2f})."
                    log_raw_execution("BUY constraint triggered: Insufficient cash for 1 share. Forced action to HOLD.")

        elif action == "SELL":
            if requested_qty > owned_qty:
                if owned_qty > 0:
                    executed_qty = owned_qty
                    adjusted_reasoning = f"{reasoning} (ADJUSTED: Requested sell {requested_qty} > owned {owned_qty}. Reduced Qty to {executed_qty})."
                    log_raw_execution(f"SELL constraint triggered: Owned {owned_qty} < requested {requested_qty}. Reduced Qty to {executed_qty}.")
                else:
                    final_action = "HOLD"
                    executed_qty = 0.0
                    adjusted_reasoning = f"{reasoning} (REJECTED: Cannot sell {requested_qty} shares. Owned quantity is 0)."
                    log_raw_execution("SELL constraint triggered: No shares owned. Forced action to HOLD.")

        elif action == "HOLD":
            executed_qty = 0.0

        # 3. Calculate balance sheet & weighted average buy price updates
        executed_amount = executed_qty * executed_price

        if final_action == "BUY":
            new_cash = current_cash - executed_amount
            new_qty = owned_qty + executed_qty
            new_avg_buy_price = ((owned_qty * old_avg_buy_price) + (executed_qty * executed_price)) / new_qty
        elif final_action == "SELL":
            new_cash = current_cash + executed_amount
            new_qty = owned_qty - executed_qty
            new_avg_buy_price = old_avg_buy_price if new_qty > 0 else 0.0
        else:  # HOLD
            new_cash = current_cash
            new_qty = owned_qty
            new_avg_buy_price = old_avg_buy_price

        new_market_value = new_qty * current_price

        # 4. Upsert Position Record
        position_record = PositionCreate(
            portfolio_id=portfolio_id,
            symbol=symbol,
            quantity=new_qty,
            avg_buy_price=round(new_avg_buy_price, 2),
            current_price=round(current_price, 2),
            market_value=round(new_market_value, 2),
        )
        self.db_client.upsert_position(position_record)

        # 5. Compute Total Portfolio Value (Cash + sum of position market values)
        all_positions = self.db_client.get_positions(portfolio_id)
        pos_dict = {p.get("symbol"): float(p.get("market_value", 0.0)) for p in all_positions}
        pos_dict[symbol] = new_market_value
        total_positions_val = sum(pos_dict.values())
        new_total_portfolio_value = new_cash + total_positions_val

        # Update Portfolio Record
        self.db_client.update_portfolio(
            portfolio_id=portfolio_id,
            current_cash=round(new_cash, 2),
            total_value=round(new_total_portfolio_value, 2)
        )

        # 6. Log Transaction Record
        daily_log_path = setup_execution_file_logging()
        transaction_record = TransactionCreate(
            portfolio_id=portfolio_id,
            agent_name=agent_name,
            symbol=symbol,
            action=final_action,
            quantity=executed_qty,
            executed_price=round(executed_price, 2),
            total_amount=round(executed_amount, 2),
            reasoning=adjusted_reasoning,
            raw_log_path=daily_log_path,
        )
        trans_res = self.db_client.log_transaction(transaction_record)

        log_raw_execution(
            f"Execution Completed for '{symbol}': Action={final_action}, Qty={executed_qty}, "
            f"ExecPrice=${executed_price:.2f}, NewCash=${new_cash:.2f}, PortfolioTotalVal=${new_total_portfolio_value:.2f}"
        )

        return {
            "symbol": symbol,
            "action": final_action,
            "quantity": executed_qty,
            "executed_price": executed_price,
            "total_amount": executed_amount,
            "new_cash": round(new_cash, 2),
            "new_position_qty": new_qty,
            "new_avg_buy_price": round(new_avg_buy_price, 2),
            "new_total_portfolio_value": round(new_total_portfolio_value, 2),
            "transaction": trans_res,
        }
