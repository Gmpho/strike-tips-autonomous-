"""
ai_pydantic.py — backward-compatibility shim.
All logic has moved to:
  - context_builder.py
  - providers/groq_provider.py
  - providers/gemini_provider.py
  - providers/ollama_provider.py
  - pipeline.py
  - orchestrator.py

Existing imports like `from core_agent.agents.ai_pydantic import UnifiedOrchestrator`
continue to work unchanged.
"""

from core_agent.agents.orchestrator import AgentResponse, UnifiedOrchestrator, _reply_to_response
from core_agent.agents.schemas import AgentReply
from core_agent.agents.intent_classifier import IntentClassifier


class ModelPipeline:
    """Thin shim — delegates to the new pipeline module."""

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.classifier = IntentClassifier()

    async def chat(self, message: str, model_override=None) -> AgentResponse:
        from core_agent.agents import pipeline
        reply = await pipeline.run(message, model_override=model_override)
        return _reply_to_response(reply)


class ModelFactory:
    MODELS = {}
    FALLBACK_CHAIN = ["racing_llama", "racing_qwen"]

    @classmethod
    def get_all(cls):
        return cls.MODELS


__all__ = [
    "AgentResponse",
    "AgentReply",
    "UnifiedOrchestrator",
    "ModelPipeline",
    "ModelFactory",
    "IntentClassifier",
]
