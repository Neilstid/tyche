"""Rule/keyword-based financial sentiment analysis scoring module."""

import re
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Financial Lexicon Keywords
BULLISH_KEYWORDS = {
    "surge", "surged", "surging", "growth", "growing", "profit", "profitable", "profits",
    "bullish", "outpace", "outperformed", "outperform", "beat", "beats", "rally", "rallied",
    "upgrade", "upgraded", "upgrades", "record", "revenue", "gain", "gains", "gained",
    "boom", "booming", "soar", "soared", "soaring", "positive", "breakthrough", "expansion",
    "dividend", "buyback", "exceed", "exceeded", "optimism", "optimistic", "climb", "climbed",
    "strong", "stronger", "strongest", "high", "higher", "highest", "all-time high", "upside"
}

BEARISH_KEYWORDS = {
    "drop", "dropped", "dropping", "loss", "losses", "downgrade", "downgraded", "downgrades",
    "plunge", "plunged", "plunging", "decline", "declined", "declining", "bearish", "miss",
    "missed", "misses", "deficit", "slump", "slumped", "slumping", "crash", "crashed",
    "recession", "inflation", "tariff", "tariffs", "lawsuit", "sued", "sanction", "sanctions",
    "risk", "risks", "cut", "cuts", "cutting", "layoff", "layoffs", "downside", "bankrupt",
    "bankruptcy", "weak", "weaker", "weakest", "low", "lower", "lowest", "collapse", "warning"
}

INTENSIFIERS = {
    "very": 1.5, "strongly": 1.8, "significantly": 1.8, "hugely": 2.0, "massively": 2.0,
    "major": 1.5, "sharp": 1.5, "sharply": 1.6, "substantial": 1.5, "substantially": 1.6
}

NEGATIONS = {"not", "no", "never", "fails", "failed", "failing", "without", "lack", "lacks"}


def _preprocess_text(text: str) -> List[str]:
    """Clean text and tokenize into lowercase words."""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return cleaned.split()


def score_text(text: str) -> float:
    """
    Compute financial sentiment score for a single string.
    
    :param text: Text to analyze (title + summary)
    :return: Normalized sentiment float strictly in range [-1.0, +1.0]
    """
    if not text or not text.strip():
        return 0.0

    words = _preprocess_text(text)
    if not words:
        return 0.0

    bullish_score = 0.0
    bearish_score = 0.0

    for i, word in enumerate(words):
        multiplier = 1.0
        is_negated = False

        # Look back up to 2 words for intensifiers or negations
        for j in range(max(0, i - 2), i):
            prev_word = words[j]
            if prev_word in INTENSIFIERS:
                multiplier *= INTENSIFIERS[prev_word]
            if prev_word in NEGATIONS:
                is_negated = True

        if word in BULLISH_KEYWORDS:
            if is_negated:
                bearish_score += 1.0 * multiplier
            else:
                bullish_score += 1.0 * multiplier
        elif word in BEARISH_KEYWORDS:
            if is_negated:
                bullish_score += 1.0 * multiplier
            else:
                bearish_score += 1.0 * multiplier

    total_matches = bullish_score + bearish_score
    if total_matches == 0.0:
        return 0.0

    net_score = (bullish_score - bearish_score) / total_matches
    # Clamp strictly between -1.0 and +1.0
    return max(-1.0, min(1.0, round(net_score, 4)))


def score_news_list(news_items: List[Dict[str, Any]]) -> Tuple[float, List[Dict[str, Any]]]:
    """
    Score a list of news items and calculate aggregate overall sentiment score.
    
    :param news_items: List of news article dictionaries
    :return: Tuple of (aggregate_sentiment_score, enriched_news_items)
    """
    if not news_items:
        return 0.0, []

    scored_items = []
    total_score = 0.0

    for item in news_items:
        title = item.get("title", "")
        summary = item.get("summary", "")
        combined_text = f"{title} {summary}"

        score = score_text(combined_text)
        item_copy = dict(item)
        item_copy["sentiment_score"] = score
        scored_items.append(item_copy)
        total_score += score

    aggregate_score = total_score / len(news_items)
    clamped_aggregate = max(-1.0, min(1.0, round(aggregate_score, 4)))

    return clamped_aggregate, scored_items
