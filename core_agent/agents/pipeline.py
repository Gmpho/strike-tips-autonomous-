"""
Pipeline — routes a message to the correct provider with parallel short-circuit.
Tries all providers concurrently, returns first success.
Fallback (if parallel all fail): remaining Gemini models sequentially.
"""

import asyncio
import hashlib
import logging
import os
import time
from typing import Optional

from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig
from core_agent.core.redis_cache import get_cache, set_cache

logger = logging.getLogger("pipeline")

DEADLINE_SEC = float(os.getenv("AGENT_STREAM_TIMEOUT_SEC", "45"))


class ProviderCircuitBreaker:
    """Skip providers that have failed recently."""

    _failures: dict = {}
    _cooldown_until: dict = {}
    _MAX_FAILURES = 3
    _COOLDOWN_SEC = 60

    @classmethod
    def available(cls, name: str) -> bool:
        now = time.monotonic()
        cooldown = cls._cooldown_until.get(name)
        if cooldown and now < cooldown:
            logger.info("Skipping %s (circuit open, %.0fs remaining)", name, cooldown - now)
            return False
        if cooldown:
            del cls._cooldown_until[name]
        return True

    @classmethod
    def record_failure(cls, name: str):
        cls._failures[name] = cls._failures.get(name, 0) + 1
        if cls._failures[name] >= cls._MAX_FAILURES:
            cls._cooldown_until[name] = time.monotonic() + cls._COOLDOWN_SEC
            cls._failures[name] = 0
            logger.warning("Circuit opened for %s (%ss cooldown)", name, cls._COOLDOWN_SEC)

    @classmethod
    def record_success(cls, name: str):
        cls._failures.pop(name, None)
        cls._cooldown_until.pop(name, None)


async def _try_one(name: str, coro):
    """Wrap a provider call so it always returns (name, reply_or_None)."""
    try:
        reply = await coro
        return name, reply
    except Exception as e:
        logger.warning("%s failed: %s", name, e)
        return name, None


async def run(message: str, model_override: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
    """
    Route message through provider fallback chain with Redis caching and intent awareness.

    Strategy:
      1. All eligible providers run in parallel.
      2. First success wins — remaining tasks are cancelled.
      3. If all parallel fail, try remaining Gemini chain models sequentially.
    """
    # 0a. Ensure snapshot has live race data
    try:
        from core_agent.core.snapshot_cache import ensure_populated
        await ensure_populated()
    except Exception:
        pass

    # 0b. Check Response Cache
    msg_hash = hashlib.md5(message.encode()).hexdigest()
    cache_key = f"llm_response:{msg_hash}"

    cached = await get_cache(cache_key)
    if cached and not model_override:
        logger.info("LLM Cache Hit: %s", msg_hash)
        try:
            return AgentReply(**cached)
        except Exception as e:
            logger.warning("Cache read failed (stale format): %s", e)

    from core_agent.agents.providers import gemini_provider, groq_provider, ollama_provider

    reply = None
    deadline = time.monotonic() + DEADLINE_SEC

    # ── 1. Build parallel provider tasks ──────────────────────────────────
    tasks: list = []
    task_names: dict = {}  # id(task) -> name

    def _add(name: str, coro):
        if not ProviderCircuitBreaker.available(name):
            return
        t = asyncio.ensure_future(_try_one(name, coro))
        tasks.append(t)
        task_names[id(t)] = name

    if ModelConfig.groq_available():
        _add("groq", groq_provider.chat(message, intent=intent))

    if ModelConfig.GEMINI_CHAIN:
        _add("gemini", gemini_provider.chat(message, model=ModelConfig.GEMINI_CHAIN[0], intent=intent))

    ollama_timeout = 25.0 if os.getenv("OLLAMA_API_KEY") else 5.0
    local_model = None
    if intent in ("get_account_summary", "calculate_max_position", "verify_race_exists"):
        local_model = ModelConfig.FAST_LOCAL
    _add("ollama", asyncio.wait_for(
        ollama_provider.chat(message, model=local_model, intent=intent),
        timeout=ollama_timeout,
    ))

    # ── 2. Fire all providers in parallel, short-circuit ──────────────────
    if tasks:
        pending = set(tasks)
        remaining_deadline = max(1.0, deadline - time.monotonic())
        try:
            while pending and not reply:
                timeout = max(0.1, remaining_deadline)
                done, pending = await asyncio.wait(
                    pending, return_when=asyncio.FIRST_COMPLETED, timeout=timeout,
                )
                for d in done:
                    name = task_names.get(id(d), "?")
                    _, result = d.result()
                    if result is None:
                        ProviderCircuitBreaker.record_failure(name)
                        continue
                    ProviderCircuitBreaker.record_success(name)
                    reply = result
                    break
                remaining_deadline = deadline - time.monotonic()
        finally:
            for t in pending:
                t.cancel()

    # ── 3. Gemini chain fallback (if first Gemini failed in parallel) ─────
    if not reply and ModelConfig.GEMINI_CHAIN:
        remaining_deadline = max(0.1, deadline - time.monotonic())
        for gemini_model in ModelConfig.GEMINI_CHAIN[1:]:
            if remaining_deadline <= 0:
                break
            try:
                reply = await asyncio.wait_for(
                    gemini_provider.chat(message, model=gemini_model, intent=intent),
                    timeout=min(remaining_deadline, 20.0),
                )
                ProviderCircuitBreaker.record_success("gemini_fallback")
                break
            except Exception as e:
                logger.warning("Gemini %s failed: %s", gemini_model, e)
                ProviderCircuitBreaker.record_failure("gemini_fallback")
            remaining_deadline = deadline - time.monotonic()

    if not reply:
        return AgentReply(
            summary="All models are currently unavailable. Please try again in 30 seconds.",
            model_used="unavailable",
        )

    # ── 4. Cache successful response ──────────────────────────────────────
    if not model_override:
        try:
            cache_data = reply.model_dump()
            await set_cache(cache_key, cache_data, ttl=600)
        except Exception as e:
            logger.warning("Cache write failed: %s", e)

    return reply
