"""Tools package exporting unified TOOL_REGISTRY for CrewAI agent instantiation."""

from typing import Dict, Any
from src.agents.tools.news_tools import (
    fetch_market_news_and_sentiment,
    fetch_news,
    analyze_sentiment,
)
from src.agents.tools.market_tools import (
    fetch_technical_indicators,
    get_stock_technicals,
    get_historical_prices,
    get_stock_price,
)
from src.agents.tools.portfolio_tools import (
    get_portfolio_state,
    get_portfolio_status,
)

# Unified tool registry mapping string identifiers from YAML to CrewAI @tool objects
TOOL_REGISTRY: Dict[str, Any] = {
    "fetch_market_news_and_sentiment": fetch_market_news_and_sentiment,
    "fetch_news": fetch_news,
    "analyze_sentiment": analyze_sentiment,
    "fetch_technical_indicators": fetch_technical_indicators,
    "get_stock_technicals": get_stock_technicals,
    "get_historical_prices": get_historical_prices,
    "get_stock_price": get_stock_price,
    "get_portfolio_state": get_portfolio_state,
    "get_portfolio_status": get_portfolio_status,
}

__all__ = [
    "TOOL_REGISTRY",
    "fetch_market_news_and_sentiment",
    "fetch_news",
    "analyze_sentiment",
    "fetch_technical_indicators",
    "get_stock_technicals",
    "get_historical_prices",
    "get_stock_price",
    "get_portfolio_state",
    "get_portfolio_status",
]
