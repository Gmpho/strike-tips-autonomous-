"""
Pipeline — routes a message to the correct provider with fallback chain.
Fallback order: Groq → Gemini (each model in chain) → Ollama.
Single responsibility: try providers in order, return first success.
"""

import asyncio
import logging
import hashlib
import os
from typing import Optional

from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig
from core_agent.core.redis_cache import get_cache, set_cache

logger = logging.getLogger("pipeline")


async def run(message: str, model_override: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
    """
    Route message through provider fallback chain with Redis caching and intent awareness.
    Returns AgentReply from the first provider that succeeds.
    """
    # 0a. Ensure snapshot has live race data
    try:
        from core_agent.core.snapshot_cache import ensure_populated
        await ensure_populated()
    except Exception:
        pass

    # 0. Check Response Cache
    # We cache based on a hash of the full enriched message (system + user + history)
    msg_hash = hashlib.md5(message.encode()).hexdigest()
    cache_key = f"llm_response:{msg_hash}"
    
    cached = await get_cache(cache_key)
    if cached and not model_override:
        logger.info(f"LLM Cache Hit: {msg_hash}")
        try:
            return AgentReply(**cached)
        except Exception as e:
            logger.warning(f"Cache read failed (stale format): {e}")

    from core_agent.agents.providers import groq_provider, gemini_provider, ollama_provider

    reply = None

    # 1. Groq — fast, free, supports tools
    if ModelConfig.groq_available():
        try:
            reply = await groq_provider.chat(message, intent=intent)
        except Exception as e:
            logger.warning(f"Groq failed: {e}")

    # 2. Gemini chain — try each model
    if not reply:
        for gemini_model in ModelConfig.GEMINI_CHAIN:
            try:
                reply = await gemini_provider.chat(message, model=gemini_model, intent=intent)
                break
            except Exception as e:
                logger.warning(f"Gemini {gemini_model} failed: {e}")

    # 3. Ollama — last resort (cloud or local)
    if not reply:
        ollama_timeout = 25.0 if os.getenv("OLLAMA_API_KEY") else 5.0
        try:
            local_model = None
            if intent in ("get_account_summary", "calculate_max_position", "verify_race_exists"):
                local_model = ModelConfig.FAST_LOCAL
            
            reply = await asyncio.wait_for(
                ollama_provider.chat(message, model=local_model, intent=intent),
                timeout=ollama_timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("Ollama timed out (skipped)")
        except Exception as e:
            logger.warning(f"Ollama failed: {e}")

    if not reply:
        return AgentReply(
            summary="All models unavailable. Please try again in 30 seconds.",
            model_used="unavailable",
        )

    # Cache successful response for 10 minutes (600s)
    if not model_override:
        try:
            cache_data = reply.model_dump()
            await set_cache(cache_key, cache_data, ttl=600)
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")

    return reply
