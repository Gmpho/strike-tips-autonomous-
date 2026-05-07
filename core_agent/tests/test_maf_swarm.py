import asyncio
import pytest
from unittest.mock import MagicMock
from core_agent.maf_agent import get_maf_agent


# Mock StrikeTips class to hold dependencies
class MockStrikeTips:
    def get_bankroll_status(self):
        return {"current_bankroll": 1000.0, "total_profit_loss": 0.0, "open_bets": 0}

    def calculate_max_stake(self, edge):
        return 50.0

    def bankroll(self):
        return self

    # Mock other methods needed by tools
    async def run_daily_scan(self, tracks=None):
        return {"status": "SUCCESS", "found": 3}


@pytest.mark.asyncio
async def test_agent_swarm():
    # Setup
    mock_strike = MockStrikeTips()
    agent = get_maf_agent(mock_strike)

    print("--- 1. Testing Bankroll Intent Routing ---")
    response = await agent.route_intent("get_account_summary", "Show me my balance")
    print(f"Bankroll Agent Response: {response}")

    print("\n--- 2. Testing Scanner Intent Routing ---")
    response = await agent.route_intent("run_daily_analysis", "Scan today's races")
    print(f"Scanner Agent Response: {response}")

    print("\n--- 3. Testing Analyst Intent Routing ---")
    response = await agent.route_intent(
        "search_past_races", "Search previous Turffontein races"
    )
    print(f"Analyst Agent Response: {response}")


if __name__ == "__main__":
    asyncio.run(test_agent_swarm())
