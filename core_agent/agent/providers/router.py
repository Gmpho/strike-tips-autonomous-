from __future__ import annotations
from collections.abc import AsyncIterator
from core_agent.agent.providers.groq import GroqProvider
from core_agent.agent.providers.gemini import GeminiProvider
from core_agent.agent.providers.ollama import OllamaProvider


class ProviderRouter:
    def __init__(self) -> None:
        self.providers = [GroqProvider(), GeminiProvider(), OllamaProvider()]

    async def stream(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> AsyncIterator[str]:
        last_error = None
        for provider in self.providers:
            try:
                async for chunk in provider.stream(messages, None, None):
                    yield chunk
                return
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(f"All providers failed: {last_error}")
