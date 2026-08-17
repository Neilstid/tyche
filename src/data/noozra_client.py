"""Noozra News API client with yfinance & neutral payload fallback mechanisms."""

import os
import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import yfinance as yf
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

NOOZRA_BASE_URL = "https://api.noozra.com/v1"  # Target Noozra API Endpoint


def fetch_noozra_news(category: str = "Finance", limit: int = 10, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch news articles from Noozra API (Public API, no API key required).
    
    :param category: News category ('Politics', 'Finance', 'Business', 'World')
    :param limit: Maximum number of news articles to retrieve
    :param api_key: Unused (Noozra API does not require an API key)
    :return: List of normalized news dictionaries
    """
    url = f"{NOOZRA_BASE_URL}/news"
    params = {"category": category, "limit": limit}
    headers = {"Accept": "application/json", "User-Agent": "Tyche/1.0"}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            articles = data.get("articles", [])
            normalized = []
            for art in articles:
                normalized.append({
                    "title": art.get("title", ""),
                    "summary": art.get("summary", art.get("description", "")),
                    "source": art.get("source", "Noozra API"),
                    "category": category,
                    "published_at": art.get("published_at", datetime.now(timezone.utc).isoformat()),
                    "url": art.get("url", ""),
                })
            logger.info(f"Retrieved {len(normalized)} articles from Noozra for category '{category}'")
            return normalized
        else:
            logger.warning(f"Noozra API responded with HTTP status {response.status_code}: {response.text}")
            return []
    except Exception as e:
        logger.warning(f"Failed to fetch news from Noozra API: {e}")
        return []


def fetch_yfinance_news(symbol: str) -> List[Dict[str, Any]]:
    """
    Fallback 1: Fetch news from yfinance.Ticker.news.
    
    :param symbol: Ticker symbol (e.g. 'AAPL')
    :return: List of normalized news dictionaries
    """
    try:
        logger.info(f"Fetching fallback yfinance news for symbol '{symbol}'")
        ticker = yf.Ticker(symbol)
        raw_news = ticker.news
        if not raw_news:
            return []

        articles = []
        for item in raw_news:
            # Handle nested or flat yfinance news dictionary format
            content = item.get("content", item) if isinstance(item, dict) else {}
            title = content.get("title") or item.get("title") or ""
            summary = content.get("summary") or item.get("summary") or title
            publisher = content.get("provider", {}).get("displayName") or item.get("publisher") or "yfinance"
            pub_date = content.get("pubDate") or item.get("providerPublishTime") or datetime.now(timezone.utc).isoformat()

            if title:
                articles.append({
                    "title": title,
                    "summary": summary,
                    "source": publisher,
                    "category": "Finance",
                    "published_at": str(pub_date),
                    "url": content.get("canonicalUrl", {}).get("url", "") if isinstance(content.get("canonicalUrl"), dict) else item.get("link", ""),
                })
        return articles
    except Exception as e:
        logger.warning(f"Failed to fetch yfinance news for '{symbol}': {e}")
        return []


def get_neutral_fallback_news(symbol: str, category: str = "Finance") -> List[Dict[str, Any]]:
    """Fallback 2: Return a neutral market news structure."""
    return [
        {
            "title": f"Market Overview for {symbol}",
            "summary": f"Neutral market environment for {symbol}. No major breaking headlines reported.",
            "source": "Neutral Fallback System",
            "category": category,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "url": "",
        }
    ]


def fetch_market_news(
    symbol: str = "AAPL",
    categories: Optional[List[str]] = None,
    limit_per_category: int = 5
) -> List[Dict[str, Any]]:
    """
    Fetch market news with multi-tier fallback architecture:
    Tier 1: Noozra API
    Tier 2: yfinance.Ticker.news
    Tier 3: Neutral fallback structure
    
    :param symbol: Ticker symbol to query for yfinance fallback
    :param categories: List of categories ('Politics', 'Finance', 'Business', 'World')
    :param limit_per_category: Maximum articles per category
    :return: List of normalized news article dictionaries
    """
    if categories is None:
        categories = ["Finance", "Business", "Politics", "World"]

    all_articles: List[Dict[str, Any]] = []

    # Attempt Tier 1: Noozra API
    for cat in categories:
        articles = fetch_noozra_news(category=cat, limit=limit_per_category)
        all_articles.extend(articles)

    if all_articles:
        logger.info(f"Total articles retrieved via Noozra API: {len(all_articles)}")
        return all_articles

    # Attempt Tier 2: yfinance ticker news fallback
    logger.info(f"Noozra API returned 0 articles. Falling back to yfinance ticker news for {symbol}.")
    yf_articles = fetch_yfinance_news(symbol=symbol)
    if yf_articles:
        logger.info(f"Retrieved {len(yf_articles)} fallback articles via yfinance.")
        return yf_articles

    # Tier 3: Neutral payload fallback
    logger.info("yfinance returned 0 articles. Using neutral fallback news structure.")
    return get_neutral_fallback_news(symbol=symbol)
