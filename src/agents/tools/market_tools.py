"""CrewAI market tools for technical indicator ingestion."""

import logging
from crewai.tools import tool
from src.data.yfinance_client import get_stock_summary

logger = logging.getLogger(__name__)


def _fetch_technical_indicators_impl(symbol: str) -> str:
    """Core logic to fetch stock technical indicators as string summary."""
    logger.info(f"Executing tool fetch_technical_indicators for '{symbol}'")
    summary = get_stock_summary(symbol=symbol)

    lines = [
        f"Symbol: {summary.get('symbol', symbol)}",
        f"Latest Price: ${summary.get('latest_price', 0.0):.2f}",
        f"RSI (14): {summary.get('rsi_14')}",
        f"SMA (20): ${summary.get('sma_20')}",
        f"SMA (50): ${summary.get('sma_50')}",
        f"MACD: {summary.get('macd')}",
        f"MACD Signal: {summary.get('macd_signal')}",
        f"MACD Histogram: {summary.get('macd_hist')}",
        f"Calculated Technical Trend: {summary.get('trend', 'NEUTRAL')}"
    ]

    return "\n".join(lines)


@tool("fetch_technical_indicators")
def fetch_technical_indicators(symbol: str) -> str:
    """
    Fetch current stock price and key quantitative technical indicators (RSI, SMA20, SMA50, MACD, Trend).
    
    :param symbol: Ticker symbol (e.g. 'AAPL', 'NVDA', 'MSFT')
    :return: Formatted text of latest price, indicators, and calculated technical trend signal.
    """
    return _fetch_technical_indicators_impl(symbol)


@tool("get_stock_technicals")
def get_stock_technicals(symbol: str) -> str:
    """Fetch quantitative technical indicators for a stock ticker symbol."""
    return _fetch_technical_indicators_impl(symbol)


@tool("get_historical_prices")
def get_historical_prices(symbol: str) -> str:
    """Fetch historical prices and technical metrics for a stock ticker symbol."""
    return _fetch_technical_indicators_impl(symbol)


@tool("get_stock_price")
def get_stock_price(symbol: str) -> str:
    """Fetch current market price and technical indicators for a stock ticker symbol."""
    return _fetch_technical_indicators_impl(symbol)
