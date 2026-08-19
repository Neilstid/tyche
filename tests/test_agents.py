"""Unit tests placeholder for agent schemas and factory."""

import unittest
from src.database.models import TeamCreate, AgentCreate
from src.config_loader import load_team_config


class TestAgentsEngine(unittest.TestCase):

    def test_team_and_agent_models(self):
        team = TeamCreate(
            name="Test Team",
            architecture="sequential",
            model="openrouter/qwen/qwen3.7-flash",
            description="Testing sequential architecture"
        )
        self.assertEqual(team.name, "Test Team")
        self.assertEqual(team.architecture, "sequential")
        self.assertEqual(team.model, "openrouter/qwen/qwen3.7-flash")

        agent = AgentCreate(
            team_id="00000000-0000-0000-0000-000000000001",
            name="Analyst",
            role="Macro Specialist",
            llm_model="openrouter/qwen/qwen3.7-flash"
        )
        self.assertEqual(agent.name, "Analyst")

    def test_load_all_team_configs_with_model(self):
        import glob
        team_files = glob.glob("config/teams/*.yaml")
        self.assertGreater(len(team_files), 0)
        for tf in team_files:
            cfg = load_team_config(tf)
            self.assertTrue(len(cfg.team.name) > 0)
            self.assertIn(cfg.team.architecture, ["sequential", "hierarchical"])
            self.assertTrue(len(cfg.team.model) > 0, f"Team in {tf} is missing model")


if __name__ == "__main__":
    unittest.main()
