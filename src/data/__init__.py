"""Data ingestion engine package for financial indicators, global news, and sentiment analysis."""

from src.data.yfinance_client import fetch_ohlcv, add_technical_indicators, get_stock_summary
from src.data.noozra_client import fetch_market_news
from src.data.sentiment import score_text, score_news_list

__all__ = [
    "fetch_ohlcv",
    "add_technical_indicators",
    "get_stock_summary",
    "fetch_market_news",
    "score_text",
    "score_news_list",
]
