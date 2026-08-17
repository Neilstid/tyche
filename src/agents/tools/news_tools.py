"""CrewAI news and sentiment analysis tools."""

import logging
from crewai.tools import tool
from src.data.noozra_client import fetch_market_news
from src.data.sentiment import score_news_list

logger = logging.getLogger(__name__)


def _fetch_market_news_and_sentiment_impl(symbol: str) -> str:
    """Core logic to fetch market news and calculate aggregate sentiment."""
    logger.info(f"Executing tool fetch_market_news_and_sentiment for '{symbol}'")
    articles = fetch_market_news(symbol=symbol)
    agg_score, scored_articles = score_news_list(articles)

    summary_lines = [
        f"Symbol: {symbol}",
        f"Aggregate Sentiment Score: {agg_score:.4f}",
        f"Total Articles Retrieved: {len(scored_articles)}",
        "Recent News Articles:"
    ]
    for idx, art in enumerate(scored_articles[:5], start=1):
        summary_lines.append(
            f"  {idx}. [{art.get('category', 'General')}] {art.get('title', 'No Title')} "
            f"(Source: {art.get('source', 'Unknown')}, Sentiment: {art.get('sentiment_score', 0.0):.2f})\n"
            f"     Summary: {art.get('summary', '')[:200]}"
        )

    return "\n".join(summary_lines)


@tool("fetch_market_news_and_sentiment")
def fetch_market_news_and_sentiment(symbol: str) -> str:
    """
    Fetch global news headlines, financial articles, and compute aggregate news sentiment score for a stock ticker symbol.
    
    :param symbol: Ticker symbol (e.g. 'AAPL', 'NVDA', 'MSFT')
    :return: Formatted text summarizing news headlines and overall sentiment score.
    """
    return _fetch_market_news_and_sentiment_impl(symbol)


@tool("fetch_news")
def fetch_news(symbol: str) -> str:
    """Fetch recent news articles for a stock ticker symbol."""
    return _fetch_market_news_and_sentiment_impl(symbol)


@tool("analyze_sentiment")
def analyze_sentiment(symbol: str) -> str:
    """Analyze sentiment score for recent news of a stock ticker symbol."""
    return _fetch_market_news_and_sentiment_impl(symbol)
