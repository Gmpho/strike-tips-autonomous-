
import asyncio
import os
import sys
from unittest.mock import MagicMock

# Mocking the strike instance
strike_mock = MagicMock()
strike_mock.get_bankroll_status.return_value = {
    "current_bankroll": 1000.0,
    "total_profit_loss": 50.0,
    "open_bets": 2
}

# Add core_agent to path
sys.path.append(os.path.abspath("."))

from core_agent.agents.ai_pydantic import UnifiedOrchestrator, IntentClassifier

async def test_intent_classifier():
    classifier = IntentClassifier()

    test_cases = [
        ("What is my balance?", "get_account_summary"),
        ("Scan today's races", "run_daily_analysis"),
        ("Analyze race 3 at Turffontein", "evaluate_race"),
        ("Record a bet on Horse X", "record_selection"),
        ("Search for Greyville results", "search_racing_data")
    ]

    print("Testing Intent Classifier...")
    for msg, expected in test_cases:
        result = classifier.classify(msg)
        print(f"Query: '{msg}' -> Expected: {expected}, Got: {result}")
        assert result == expected

async def test_orchestrator_instant_handlers():
    orchestrator = UnifiedOrchestrator(strike_mock)

    print("\nTesting Orchestrator Instant Handlers...")

    # Test Greeting
    response = await orchestrator.chat("Hi")
    print(f"Greeting response: {response.summary}")
    assert "ready" in response.summary.lower()
    assert response.model_used == "intent_handler"

    # Test Balance
    response = await orchestrator.chat("How much money do I have?")
    print(f"Balance response: {response.summary}")
    assert "R1000.00" in response.summary
    assert response.model_used == "intent_handler"

async def main():
    await test_intent_classifier()
    await test_orchestrator_instant_handlers()
    print("\nAI Pipeline Basic Verification Complete.")

if __name__ == "__main__":
    asyncio.run(main())
