"""
StrikeMAFAgent - Router/Orchestrator stub.
Kept for backward compat with tests. Delegates to ModelPipeline internally.
"""

from dataclasses import dataclass
from core_agent.config.model_config import ModelConfig


@dataclass
class AgentConfig:
    @staticmethod
    def get_model(role: str) -> str:
        if role == "bankroll":
            return ModelConfig.REASONER
        if role == "scanner":
            return ModelConfig.SCRAPER
        if role == "analyst":
            return ModelConfig.REASONER
        return ModelConfig.ORCHESTRATOR


class StrikeMAFAgent:
    def __init__(self, strike_instance):
        self.strike = strike_instance
        from core_agent.agents.ai_pydantic import ModelPipeline

        self._pipeline = ModelPipeline(strike_instance)

    async def route_intent(self, intent: str, message: str):
        response = await self._pipeline.chat(message)
        return response.summary


def get_maf_agent(strike_instance):
    return StrikeMAFAgent(strike_instance)
