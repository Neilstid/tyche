"""CrewAI portfolio tools for querying cash balance and position status."""

import logging
from crewai.tools import tool
from src.database.supabase_client import SupabaseDBClient

logger = logging.getLogger(__name__)


def _get_db_client() -> SupabaseDBClient:
    return SupabaseDBClient()


def _get_portfolio_state_impl(portfolio_id: str) -> str:
    """Core logic to query portfolio state."""
    logger.info(f"Executing tool get_portfolio_state for portfolio '{portfolio_id}'")
    db = _get_db_client()

    positions = db.get_positions(portfolio_id)

    lines = [
        f"Portfolio ID: {portfolio_id}",
        f"Active Positions Count: {len(positions)}"
    ]

    if positions:
        lines.append("Open Positions:")
        for pos in positions:
            lines.append(
                f"  - Ticker: {pos.get('symbol')}, Quantity: {pos.get('quantity')}, "
                f"Avg Buy Price: ${pos.get('avg_buy_price', 0.0):.2f}, Market Value: ${pos.get('market_value', 0.0):.2f}"
            )
    else:
        lines.append("Open Positions: None")

    return "\n".join(lines)


@tool("get_portfolio_state")
def get_portfolio_state(portfolio_id: str) -> str:
    """
    Query current portfolio state including cash balance, current total value, and active open positions.
    
    :param portfolio_id: Portfolio UUID or identifier string
    :return: Formatted text summarizing cash, total value, and positions list.
    """
    return _get_portfolio_state_impl(portfolio_id)


@tool("get_portfolio_status")
def get_portfolio_status(portfolio_id: str) -> str:
    """Fetch current portfolio cash balance and active positions."""
    return _get_portfolio_state_impl(portfolio_id)
