from __future__ import annotations
import os
import json
import re
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.core.http_client import get_async_client
from core_agent.config.model_registry import get_model_by_id
import logging

logger = logging.getLogger("ollama-provider")

class OllamaProvider(LLMProvider):
    def __init__(self) -> None:
        self.host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    def _get_api_format(self, model: str) -> str:
        info = get_model_by_id(model)
        if info:
            return info.api_format
        info = get_model_by_id(f"{model}:latest")
        if info:
            return info.api_format
        logger.warning("[OLLAMA] model %s not in registry, defaulting to chat format", model)
        return "chat"

    async def stream(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        intent: str | None,
        model_override: str | None = None,
    ) -> AsyncIterator[str]:
        model = model_override or "qwen3.5:0.8b"
        fmt = self._get_api_format(model)
        logger.info("[OLLAMA] streaming with model=%s format=%s", model, fmt)

        if fmt == "generate":
            prompt = messages[-1]["content"] if messages else ""
            url = f"{self.host}/api/generate"
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
            }
        else:
            url = f"{self.host}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

        client = get_async_client(timeout=180.0)
        async with client.stream("POST", url, json=payload) as response:
            async for line in response.aiter_lines():
                if line:
                    data = json.loads(line)
                    if fmt == "generate":
                        content = data.get("response", "")
                        if content:
                            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                            yield content
                    elif "message" in data:
                        content = data["message"].get("content", "")
                        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
                        yield content
                    if data.get("done"):
                        break

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        return "".join(chunks)
