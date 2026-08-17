"""Unit tests for data ingestion, technical indicators, news fallbacks, and sentiment analysis."""

import unittest
import pandas as pd
from src.data.yfinance_client import add_technical_indicators, fetch_ohlcv
from src.data.noozra_client import fetch_market_news, fetch_yfinance_news, get_neutral_fallback_news
from src.data.sentiment import score_text, score_news_list
from src.config_loader import load_team_config, load_default_settings


class TestDataEngine(unittest.TestCase):

    def test_sentiment_scoring_bounds(self):
        bullish = score_text("Company reports massive record profits and surging revenue growth!")
        bearish = score_text("Stock plunges after sharp loss, severe recession warning and layoffs")
        neutral = score_text("The market opened today at 9:30 AM EST.")

        self.assertGreater(bullish, 0.0)
        self.assertLess(bearish, 0.0)
        self.assertAlmostEqual(neutral, 0.0, delta=0.2)
        self.assertTrue(-1.0 <= bullish <= 1.0)
        self.assertTrue(-1.0 <= bearish <= 1.0)

    def test_sentiment_negation(self):
        score_normal = score_text("growth profit")
        score_negated = score_text("no growth and fails to profit")
        self.assertGreater(score_normal, 0.0)
        self.assertLess(score_negated, 0.0)

    def test_news_fallback_chain(self):
        neutral_fallback = get_neutral_fallback_news("AAPL")
        self.assertEqual(len(neutral_fallback), 1)
        self.assertIn("AAPL", neutral_fallback[0]["title"])

        news = fetch_market_news("AAPL", limit_per_category=2)
        self.assertIsInstance(news, list)
        self.assertGreater(len(news), 0)

    def test_technical_indicators_calculation(self):
        data = {
            "Open": [100.0 + i for i in range(60)],
            "High": [105.0 + i for i in range(60)],
            "Low": [95.0 + i for i in range(60)],
            "Close": [102.0 + i for i in range(60)],
            "Volume": [1000000 for _ in range(60)],
        }
        df = pd.DataFrame(data)
        df_indicators = add_technical_indicators(df)

        self.assertIn("RSI_14", df_indicators.columns)
        self.assertIn("SMA_20", df_indicators.columns)
        self.assertIn("SMA_50", df_indicators.columns)

    def test_config_loader(self):
        team_config = load_team_config("config/teams/sequential_team_alpha.yaml")
        self.assertEqual(team_config.team.name, "Sequential Team Alpha")
        self.assertEqual(team_config.team.architecture, "sequential")
        self.assertEqual(len(team_config.agents), 3)

        settings = load_default_settings("config/default_settings.yaml")
        self.assertEqual(settings.portfolio.initial_cash, 10000.00)
        self.assertGreater(len(settings.markets.stock_markets), 0)
        self.assertGreater(len(settings.markets.default_etfs), 0)
        all_tickers = settings.markets.get_all_tickers()
        self.assertIn("^GSPC", all_tickers)
        self.assertIn("SPY", all_tickers)
        self.assertIn("QQQ", all_tickers)
        self.assertIn("XLK", all_tickers)



if __name__ == "__main__":
    unittest.main()
