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


SA_TRACKS = {"turffontein", "vaal", "fairview", "scottsville", "kenilworth", "greyville", "durbanville"}
UK_ALIASES = {"cheltenham", "ascot", "newmarket", "goodwood", "epsom", "york", "southwell"}


def build_unsupported_track_response(query: str) -> str | None:
    query_lower = query.lower()
    for alias in UK_ALIASES:
        if alias in query_lower:
            return (
                f"I can't scan {alias.title()} — this system only supports South African tracks. "
                f"Try one of: Vaal, Turffontein, Kenilworth, Fairview, Scottsville, Greyville, Durbanville."
            )
    for sa_track in SA_TRACKS:
        if sa_track in query_lower:
            return None
    return None


class ModelPipeline:
    """Thin shim — delegates to the new pipeline module."""

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.classifier = IntentClassifier()

    async def chat(self, message: str, model_override=None) -> AgentResponse:
        from core_agent.agents import pipeline
        intent = self.classifier.classify(message)
        reply = await pipeline.run(message, model_override=model_override, intent=intent)
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
