"""
Strike Tips - AI Providers
Unified orchestrator for Groq and Gemini (primary/fallback).
No local Ollama cloud dependency, no Kimi.
"""

import os
import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, List
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("strike-ai")


@dataclass
class AIResponse:
    content: str
    provider: str
    error: Optional[str] = None


class AIProvider:
    ALLOWED_MODELS = {
        "groq": ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
        "gemini": ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash", "gemini-2.5-flash-lite"],
    }

    def __init__(self):
        self._genai_client = None

    def validate_model(self, provider: str, model: str) -> bool:
        return model in self.ALLOWED_MODELS.get(provider, [])

    async def _call_parallel(self, prompts: List[str]) -> List[AIResponse]:
        """Dispatch prompts in parallel via Groq (primary) with Gemini fallback."""
        from core_agent.config.model_factory import get_client

        async def _run(prompt: str) -> AIResponse:
            # Primary: Groq gpt-oss-120b
            if ModelConfig.groq_available():
                try:
                    client = get_client("openai/gpt-oss-120b")
                    agent = client.as_agent()
                    session = agent.create_session()
                    from agent_framework import Message
                    result = await agent.run([Message(role="user", text=prompt)], session=session)
                    return AIResponse(content=result.text, provider="groq")
                except Exception as e:
                    logger.warning(f"Groq failed, falling back to Gemini: {e}")
            # Fallback: Gemini 3.5 flash
            try:
                client = get_client("gemini-3.5-flash")
                agent = client.as_agent()
                session = agent.create_session()
                from agent_framework import Message
                result = await agent.run([Message(role="user", text=prompt)], session=session)
                return AIResponse(content=result.text, provider="gemini")
            except Exception as e:
                logger.error(f"All providers failed for prompt: {e}")
                return AIResponse(content="", provider="error", error=str(e))

        tasks = [_run(p) for p in prompts]
        return await asyncio.gather(*tasks)

    # Alias for backward compatibility
    _call_kimi_parallel = _call_parallel

    async def direct_chat(
        self, prompt: str, model_name: str = "groq:openai/gpt-oss-20b"
    ) -> AIResponse:
        from core_agent.config.model_factory import get_client

        if ":" not in model_name:
            return AIResponse(
                content="", provider="error", error="Invalid format. Use provider:model"
            )

        provider, model = model_name.split(":", 1)

        try:
            client = get_client(f"{provider}:{model}")
            agent = client.as_agent()
            session = agent.create_session()
            from agent_framework import Message
            result = await agent.run([Message(role="user", text=prompt)], session=session)
            return AIResponse(content=result.text, provider=provider)
        except Exception as e:
            return AIResponse(content="", provider=provider, error=str(e))
