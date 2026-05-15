"""
Pipeline — routes a message to the correct provider with fallback chain.
Fallback order: Groq → Gemini (each model in chain) → Ollama.
Single responsibility: try providers in order, return first success.
"""

import logging
from typing import Optional

from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("pipeline")


async def run(message: str, model_override: Optional[str] = None) -> AgentReply:
    """
    Route message through provider fallback chain.
    Returns AgentReply from the first provider that succeeds.
    """
    from core_agent.agents.providers import groq_provider, gemini_provider, ollama_provider

    # 1. Groq — fast, free, supports tools
    if ModelConfig.groq_available():
        try:
            return await groq_provider.chat(message)
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # 2. Gemini chain — try each model
    for gemini_model in ModelConfig.GEMINI_CHAIN:
        try:
            return await gemini_provider.chat(message, model=gemini_model)
        except Exception as e:
            logger.warning(f"Gemini {gemini_model} failed: {e}")

    # 3. Ollama local — last resort
    try:
        return await ollama_provider.chat(message)
    except Exception as e:
        logger.warning(f"Ollama failed: {e}")

    return AgentReply(
        summary="All models unavailable. Please try again in 30 seconds.",
        model_used="unavailable",
    )
