"""
Intent Classifier — keyword-based fast path, no LLM required.
"""

from typing import Optional

from core_agent.agents.schemas import IntentResponse


class IntentClassifier:
    PATTERNS = {
        "get_account_summary": ["balance", "bankroll", "how much", "account", "pnl", "profit", "loss"],
        "run_daily_analysis": ["tracks", "racing today", "races", "scan", "today", "what's running"],
        "evaluate_race": ["analyse", "analyze", "evaluate", "assess race", "pick", "who will win", "predict"],
        "record_selection": ["record", "place", "select", "back", "wager"],
        "search_racing_data": ["search", "find", "lookup", "info", "news"],
        "calculate_probability_edge": ["edge", "probability", "odds math"],
        "calculate_max_position": ["max stake", "position size", "how much can i"],
        "verify_race_exists": ["exists", "check race", "valid"],
        "get_odds_snapshot": ["odds", "prices", "snapshot"],
        "search_past_races": ["past", "memory", "history", "previous"],
        "update_race_result": ["settle", "won", "lost", "result"],
    }

    INTENT_SPECIALIST = {
        "evaluate_race": "analyst",
        "search_past_races": "analyst",
        "search_racing_data": "search",
        "calculate_probability_edge": "analyst",
        "run_daily_analysis": "scanner",
        "verify_race_exists": "scanner",
        "get_odds_snapshot": "scanner",
        "get_account_summary": "bankroll",
        "calculate_max_position": "bankroll",
        "record_selection": "bankroll",
        "update_race_result": "bankroll",
    }

    def classify(self, message: str) -> Optional[str]:
        msg = message.lower()
        for intent, keywords in self.PATTERNS.items():
            if any(kw in msg for kw in keywords):
                return intent
        return None

    def specialist_for(self, intent: str) -> str:
        return self.INTENT_SPECIALIST.get(intent, "analyst")


__all__ = ["IntentClassifier", "IntentResponse"]
