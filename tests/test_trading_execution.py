"""Integration tests for CrewAI agent validation, retry/fallback, and paper trading execution."""

import os
import unittest
from unittest.mock import MagicMock, patch

from src.agents.schemas import TradeDecision, TeamTradingPlan
from src.agents.crews import (
    extract_and_parse_json_plan,
    execute_crew_trading_cycle,
    build_trading_crew,
)
from src.execution.paper_trading import PaperTradingEngine
from src.config_loader import load_team_config
from src.database.supabase_client import SupabaseDBClient


class TestTradingExecutionEngine(unittest.TestCase):
    """Test suite covering schema validation, fallback logic, balance sheet constraints, and execution."""

    def setUp(self):
        """Set up in-memory mock Supabase DB client for tests."""
        self.mock_db = SupabaseDBClient(url="", key="")
        self.portfolio_id = "00000000-0000-0000-0000-000000000003"
        self.engine = PaperTradingEngine(db_client=self.mock_db)

    def test_json_parsing_and_schema_validation(self):
        """Test extraction of TeamTradingPlan from raw LLM output strings."""
        raw_json_str = '```json\n{"decisions": [{"symbol": "AAPL", "action": "BUY", "quantity": 10.0, "reasoning": "Strong RSI and news"}]}\n```'
        plan = extract_and_parse_json_plan(raw_json_str, default_ticker="AAPL")
        self.assertEqual(len(plan.decisions), 1)
        self.assertEqual(plan.decisions[0].symbol, "AAPL")
        self.assertEqual(plan.decisions[0].action, "BUY")
        self.assertEqual(plan.decisions[0].quantity, 10.0)

    def test_validation_fallback_trigger_on_double_failure(self):
        """Test that 2 consecutive validation failures trigger the Safety Fallback (HOLD, 0 qty)."""
        team_config = load_team_config("config/teams/sequential_team_alpha.yaml")

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "mock-key"}), patch("src.agents.crews.Crew.kickoff") as mock_kickoff:
            # Simulate broken output on both attempts
            mock_kickoff.return_value = "Broken invalid non-JSON output"

            plan = execute_crew_trading_cycle(
                team_config=team_config,
                portfolio_id=self.portfolio_id,
                ticker="AAPL",
                db_client=self.mock_db,
            )

            # Should fall back to SAFETY FALLBACK HOLD
            self.assertEqual(len(plan.decisions), 1)
            self.assertEqual(plan.decisions[0].action, "HOLD")
            self.assertEqual(plan.decisions[0].quantity, 0.0)
            self.assertIn("SAFETY FALLBACK", plan.decisions[0].reasoning)

            # Check that errors.log was written
            self.assertTrue(os.path.exists("./logs/errors.log"))

    def test_paper_trading_buy_constraints_and_weighted_avg(self):
        """Test BUY cash constraint capping and weighted average buy price calculation."""
        # 1. Buy 100 shares of XYZ at $200 with $10,000 cash -> Total cost $20,000 > $10,000 cash.
        # Should reduce quantity to floor(10000 / 200) = 50 shares.
        buy_decision = TradeDecision(
            symbol="XYZ",
            action="BUY",
            quantity=100.0,
            reasoning="Testing cash constraint capping"
        )
        res1 = self.engine.process_decision(
            portfolio_id=self.portfolio_id,
            decision=buy_decision,
            current_price=200.0,
        )

        self.assertEqual(res1["action"], "BUY")
        self.assertEqual(res1["quantity"], 50.0)
        self.assertEqual(res1["new_cash"], 0.0)
        self.assertEqual(res1["new_position_qty"], 50.0)
        self.assertEqual(res1["new_avg_buy_price"], 200.0)

        # 2. Add cash via portfolio mock update, then Buy 10 more shares of XYZ at $100.
        # Weighted average buy price should be ((50 * 200) + (10 * 100)) / 60 = 11000 / 60 = 183.33
        self.mock_db.update_portfolio(self.portfolio_id, current_cash=2000.0, total_value=12000.0)
        buy_decision_2 = TradeDecision(
            symbol="XYZ",
            action="BUY",
            quantity=10.0,
            reasoning="Averaging down"
        )
        res2 = self.engine.process_decision(
            portfolio_id=self.portfolio_id,
            decision=buy_decision_2,
            current_price=100.0,
        )

        self.assertEqual(res2["quantity"], 10.0)
        self.assertEqual(res2["new_position_qty"], 60.0)
        self.assertEqual(res2["new_avg_buy_price"], 183.33)

    def test_paper_trading_sell_constraints(self):
        """Test SELL owned shares constraint capping."""
        # Setup position with 20 shares owned
        self.engine.process_decision(
            portfolio_id=self.portfolio_id,
            decision=TradeDecision(symbol="ABC", action="BUY", quantity=20.0, reasoning="Initial buy"),
            current_price=50.0,
        )

        # Attempt to sell 50 shares when only 20 owned -> Should reduce sell quantity to 20 shares.
        sell_decision = TradeDecision(
            symbol="ABC",
            action="SELL",
            quantity=50.0,
            reasoning="Selling all"
        )
        res = self.engine.process_decision(
            portfolio_id=self.portfolio_id,
            decision=sell_decision,
            current_price=60.0,
        )

        self.assertEqual(res["action"], "SELL")
        self.assertEqual(res["quantity"], 20.0)
        self.assertEqual(res["new_position_qty"], 0.0)

    def test_dry_run_trade_cycle_integration(self):
        """Dry-run test executing full trade cycle with sequential team configuration."""
        team_config = load_team_config("config/teams/sequential_team_alpha.yaml")

        valid_json_response = (
            '{"decisions": [{"symbol": "NVDA", "action": "BUY", "quantity": 5.0, "reasoning": "Strong momentum"}]}'
        )

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "mock-key"}), patch("src.agents.crews.Crew.kickoff") as mock_kickoff:
            mock_kickoff.return_value = valid_json_response

            plan = execute_crew_trading_cycle(
                team_config=team_config,
                portfolio_id=self.portfolio_id,
                ticker="NVDA",
                db_client=self.mock_db,
            )

            self.assertEqual(len(plan.decisions), 1)
            decision = plan.decisions[0]
            self.assertEqual(decision.symbol, "NVDA")
            self.assertEqual(decision.action, "BUY")
            self.assertEqual(decision.quantity, 5.0)

            # Process through paper trading accountant
            exec_res = self.engine.process_decision(
                portfolio_id=self.portfolio_id,
                decision=decision,
                current_price=120.0,
            )

            self.assertEqual(exec_res["symbol"], "NVDA")
            self.assertEqual(exec_res["action"], "BUY")
            self.assertEqual(exec_res["quantity"], 5.0)
            self.assertEqual(exec_res["total_amount"], 600.0)


if __name__ == "__main__":
    unittest.main()
