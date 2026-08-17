"""End-to-End Integration Test for Tyche Multi-Agent Trading Platform Phase 3."""

import os
import unittest
import pandas as pd

from src.config_loader import load_team_config
from src.database.supabase_client import SupabaseDBClient
from src.execution.metrics import (
    compute_base100,
    compute_sharpe_ratio,
    compute_max_drawdown,
    compute_portfolio_summary_metrics,
)
from src.execution.backtester import BacktestRunner
from src.dashboard.gh_pages_builder import build_github_pages


class TestFullPipeline(unittest.TestCase):
    """End-to-end integration test suite verifying metrics formulas, 5-day backtest, and dashboard compilation."""

    def setUp(self):
        """Set up in-memory mock Supabase DB client."""
        self.mock_db = SupabaseDBClient(url="", key="")
        self.team_config = load_team_config("config/teams/sequential_team_alpha.yaml")

    def test_base100_computation_formula(self):
        """Verify Base 100 formula: Base100 = 100 * (value / initial_value)."""
        series = pd.Series([50.0, 75.0, 100.0, 25.0])
        base100 = compute_base100(series)

        self.assertAlmostEqual(base100.iloc[0], 100.0)
        self.assertAlmostEqual(base100.iloc[1], 150.0)
        self.assertAlmostEqual(base100.iloc[2], 200.0)
        self.assertAlmostEqual(base100.iloc[3], 50.0)

    def test_sharpe_ratio_computation_formula(self):
        """Verify Annualized Sharpe Ratio formula."""
        # 10 trading days of positive consistent returns
        daily_returns = pd.Series([0.01, 0.02, 0.015, 0.01, 0.02, 0.012, 0.018, 0.01, 0.014, 0.016])
        sharpe = compute_sharpe_ratio(daily_returns, risk_free_rate=0.02)
        self.assertGreater(sharpe, 0.0)
        self.assertIsInstance(sharpe, float)

    def test_max_drawdown_computation_formula(self):
        """Verify Max Drawdown formula: min((value - peak) / peak)."""
        # Peak is 120 at index 1, trough is 90 at index 2 -> Drawdown = (90 - 120) / 120 = -0.25 (-25%)
        values = pd.Series([100.0, 120.0, 90.0, 110.0])
        max_dd = compute_max_drawdown(values)
        self.assertAlmostEqual(max_dd, -0.25)

    def test_five_day_backtest_execution(self):
        """Execute 5-day simulated backtest and verify snapshots and metrics."""
        runner = BacktestRunner(
            team_config=self.team_config,
            start_date="2026-01-05",
            end_date="2026-01-09",
            initial_cash=10000.0,
            db_client=self.mock_db,
            use_mock_llm=True
        )

        res = runner.run_backtest(tickers=["AAPL"])

        self.assertEqual(res["team_name"], "Sequential Team Alpha")
        self.assertEqual(res["total_trading_days"], 5)
        self.assertIn("portfolio_id", res)

        snapshots = self.mock_db.get_snapshots(res["portfolio_id"])
        self.assertEqual(len(snapshots), 5)
        self.assertAlmostEqual(snapshots[0]["portfolio_base100"], 100.0)

    def test_static_github_pages_builder(self):
        """Verify static GitHub Pages compilation generates valid ./docs/index.html."""
        output_file = build_github_pages(output_dir="./docs", db_client=self.mock_db)

        self.assertTrue(os.path.exists(output_file))
        self.assertGreater(os.path.getsize(output_file), 1000)

        with open(output_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("TYCHE PLATFORM", content)
        self.assertIn("Total Portfolio Value", content)
        self.assertIn("Plotly", content)


    def test_supabase_url_sanitization(self):
        """Verify that trailing /rest/v1 or slashes are stripped from Supabase URL."""
        client1 = SupabaseDBClient(url="https://xyz.supabase.co/rest/v1/", key="dummy")
        self.assertEqual(client1.url, "https://xyz.supabase.co")

        client2 = SupabaseDBClient(url="https://xyz.supabase.co/rest/v1", key="dummy")
        self.assertEqual(client2.url, "https://xyz.supabase.co")


if __name__ == "__main__":
    unittest.main()
