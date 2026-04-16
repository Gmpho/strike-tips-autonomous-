"""
Strike Tips - Intent Classifier
Centralized intent classification using Pydantic AI for consistent routing.
"""
from typing import Optional, List, Dict
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from config.model_factory import get_model
import StrikeTips

# === RESPONSE CONTRACT ===
class IntentResponse(BaseModel):
    intent: str = Field(description="The detected intent (e.g., GET_BANKROLL, SCAN_RACES, GET_RESULTS, SEARCH_FORM, GET_INTELLIGENCE, OTHER)")
    confidence: float = Field(default=1.0, description="Confidence 0-1")

# === DEPS ===
class StrikeDeps:
    def __init__(self, strike: StrikeTips):
        self.strike = strike

class IntentClassifier:
    def __init__(self, strike_instance: StrikeTips):
        self.strike = strike_instance
        self.classifier = get_model("CLASSIFIER")
        
        self.agent = Agent(
            self.classifier,
            deps_type=StrikeDeps,
            retries=2, 
            system_prompt="""You are an intent classifier for a racing bot.
            Classify user messages into EXACTLY one of these labels:
            GET_BANKROLL, SCAN_RACES, GET_RESULTS, SEARCH_FORM, GET_INTELLIGENCE, OTHER.
            Output ONLY the label."""
        )

    async def classify(self, user_msg: str) -> IntentResponse:
        # 1. Surgical Keyword Pre-Routing
        msg_lower = user_msg.lower()
        # Expanded synonyms for clearer intent mapping
        if any(k in msg_lower for k in ["computaform", "intelligence", "tips", "info", "insight", "read"]):
            return IntentResponse(intent="GET_INTELLIGENCE")
        if any(k in msg_lower for k in ["scan", "analyze", "find value", "bets", "value", "calculate", "search"]):
            return IntentResponse(intent="SCAN_RACES")
        if any(k in msg_lower for k in ["bankroll", "balance", "money", "wallet", "funds"]):
            return IntentResponse(intent="GET_BANKROLL")
        if any(k in msg_lower for k in ["result", "results", "winner", "did i win"]):
            return IntentResponse(intent="GET_RESULTS")
            
        # 2. LLM Fallback
        result_val = await self.agent.run(user_msg, deps=StrikeDeps(strike=self.strike))
        intent = str(getattr(result_val, 'output', result_val)).strip().upper()
        
        return IntentResponse(intent=intent, confidence=1.0)
