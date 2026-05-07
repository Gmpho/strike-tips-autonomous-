"""
Strike Tips - AI Providers
Unified orchestrator for Gemini, Groq, and Ollama (Local/Cloud).
"""

import os
import json
import logging
import asyncio
from openai import OpenAI
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
        "ollama": [
            "racing_llama",
            "racing_qwen",
            "func_gemma",
            "lfm_racing",
            "ds_racing",
            "llama3.2:1b",
        ],
        "ollama_cloud": [
            "nemotron-3-nano:30b",
            "glm-4.7",
            "kimi-k2-thinking",
            "kimi-k2.5",
            "qwen3.5:397b",
            "gemini-3-flash-preview",
            "gemma4:31b",
        ],
        "groq": ["llama-3.3-70b-versatile"],
        "gemini": ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-3-flash-preview"],
    }

    def __init__(self):
        self._genai_client = None

    def validate_model(self, provider: str, model: str) -> bool:
        return model in self.ALLOWED_MODELS.get(provider, [])

    async def direct_chat(
        self, prompt: str, model_name: str = "ollama:llama3.2:1b"
    ) -> AIResponse:
        from core_agent.config.model_factory import get_client

        if ":" not in model_name:
            return AIResponse(
                content="", provider="error", error="Invalid format. Use provider:model"
            )

        provider, model = model_name.split(":", 1)
        if provider == "local":
            provider = "ollama"
        elif provider == "cloud" or model_name.endswith(":cloud"):
            provider = "ollama_cloud"
            model = model.replace(":cloud", "")

        try:
            client = get_client(f"{provider}:{model}")
            result = await client.run(prompt, session=client.create_session())
            text = result.text if hasattr(result, "text") else str(result)
            return AIResponse(content=text, provider=provider)
        except Exception as e:
            return AIResponse(content="", provider=provider, error=str(e))

    async def _call_kimi_parallel(
        self, prompts: List[str], strike_instance=None
    ) -> List[AIResponse]:
        """Parallel dispatch specifically optimized for Kimi (multi-race simultaneous)."""
        from core_agent.config.model_factory import get_client

        model_key = ModelConfig.PARALLEL  # e.g. "kimi-k2-thinking:cloud"
        client = get_client(model_key)

        async def _safe_run(p):
            try:
                from agent_framework import Message, Content

                # Try the primary model
                messages = [Message(role="user", contents=[Content.from_text(text=p)])]
                res = await client.get_response(messages=messages)

                text = (
                    res.text
                    if hasattr(res, "text")
                    else "".join(
                        [c.text for c in res.messages[0].contents if hasattr(c, "text")]
                    )
                )
                return AIResponse(content=text, provider="kimi")
            except Exception as e:
                # Fallback: Groq first (High speed, generous quota)
                if ModelConfig.groq_available():
                    logger.warning(
                        f"[SWARM] Cloud proxy {client.model_id} failed, falling back to Groq..."
                    )
                    from agent_framework.openai import OpenAIChatClient

                    groq_client = OpenAIChatClient(
                        model_id="llama-3.3-70b-versatile",
                        base_url="https://api.groq.com/openai/v1/",
                        api_key=os.getenv("GROQ_API_KEY", ""),
                    )
                    res = await groq_client.get_response(messages=messages)
                    text = (
                        res.text
                        if hasattr(res, "text")
                        else "".join(
                            [
                                c.text
                                for c in res.messages[0].contents
                                if hasattr(c, "text")
                            ]
                        )
                    )
                    return AIResponse(content=text, provider="groq-fallback")

                # Last resort: Gemini
                if "404" in str(e) or "429" in str(e):
                    logger.warning(
                        f"[SWARM] Groq/Proxy failed, falling back to Gemini..."
                    )
                    from agent_framework.openai import OpenAIChatClient

                    gem_client = OpenAIChatClient(
                        model_id="gemini-3-flash-preview",
                        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                        api_key=os.getenv("GEMINI_API_KEY", ""),
                    )
                    res = await gem_client.get_response(messages=messages)
                    text = (
                        res.text
                        if hasattr(res, "text")
                        else "".join(
                            [
                                c.text
                                for c in res.messages[0].contents
                                if hasattr(c, "text")
                            ]
                        )
                    )
                    return AIResponse(content=text, provider="gemini-fallback")

                logger.error(f"Kimi Parallel Error: {e}")
                return AIResponse(content="", provider="kimi", error=str(e))

        tasks = [_safe_run(p) for p in prompts]
        return await asyncio.gather(*tasks)

    async def swarm_dispatch(self, tasks: List[str]) -> List[AIResponse]:
        """Dispatch a list of tasks across the HEALING_POOL swarm."""
        from core_agent.config.model_factory import get_client
        import random

        pool = ModelConfig.HEALING_POOL

        async def _run_swarm_task(task_text):
            # Rotate models or pick one randomly for the swarm task
            model_name = random.choice(pool)
            client = get_client(model_name)
            try:
                res = await client.run(task_text, session=client.create_session())
                return AIResponse(content=res.text, provider=model_name)
            except Exception as e:
                logger.error(f"Swarm Task Error ({model_name}): {e}")
                return AIResponse(content="", provider=model_name, error=str(e))

        dispatch_tasks = [_run_swarm_task(t) for t in tasks]
        return await asyncio.gather(*dispatch_tasks)
