from __future__ import annotations
import os
import json
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.core.http_client import get_async_client
import logging

logger = logging.getLogger("ollama-provider")

class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    async def stream(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> AsyncIterator[str]:
        # Simple local chat completion
        url = f"{self.host}/api/chat"
        payload = {
            "model": "qwen:1.8b", # Default local model
            "messages": messages,
            "stream": True,
        }

        client = get_async_client(timeout=30.0)
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if "message" in data:
                        yield data["message"].get("content", "")
                    if data.get("done"):
                        break

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        return "".join(chunks)
