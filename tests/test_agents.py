"""Unit tests placeholder for agent schemas and factory."""

import unittest
from src.database.models import TeamCreate, AgentCreate


class TestAgentsEngine(unittest.TestCase):

    def test_team_and_agent_models(self):
        team = TeamCreate(
            name="Test Team",
            architecture="sequential",
            description="Testing sequential architecture"
        )
        self.assertEqual(team.name, "Test Team")

        agent = AgentCreate(
            team_id="00000000-0000-0000-0000-000000000001",
            name="Analyst",
            role="Macro Specialist",
            llm_model="openrouter/qwen/qwen3.7-flash"
        )
        self.assertEqual(agent.name, "Analyst")


if __name__ == "__main__":
    unittest.main()
