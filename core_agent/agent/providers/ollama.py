from __future__ import annotations
import os
import json
import re
import httpx
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.config.model_registry import get_model_by_id
import logging

logger = logging.getLogger("ollama-provider")

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

def _strip_think(chunk: str, in_think: bool) -> tuple[str, bool]:
    if not chunk:
        return "", in_think
    if in_think:
        idx = chunk.find("</think>")
        if idx == -1:
            return "", True
        remaining = chunk[idx + 8:]
        return _strip_think(remaining, False)
    idx = chunk.find("<think>")
    if idx == -1:
        return chunk, False
    before = chunk[:idx]
    remaining = chunk[idx + 7:]
    cleaned, after_in_think = _strip_think(remaining, True)
    return before + cleaned, after_in_think

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

        # ── Headroom compression ────────────────────────────────────────────
        try:
            from headroom import compress
            if fmt == "generate":
                prompt = messages[-1]["content"] if messages else ""
                if len(prompt) > 500:
                    result = compress(
                        [{"role": "user", "content": prompt}],
                        model=model,
                    )
                    if result.tokens_saved > 0:
                        logger.info(
                            "[HEADROOM] %s: %d→%d tokens (%.0f%% saved)",
                            model, result.tokens_before, result.tokens_after,
                            (1 - result.tokens_after / max(result.tokens_before, 1)) * 100,
                        )
                        messages[-1]["content"] = result.messages[-1]["content"]
            else:
                total = sum(len(m.get("content", "") or "") for m in messages)
                if total > 1000:
                    result = compress(messages, model=model)
                    if result.tokens_saved > 0:
                        logger.info(
                            "[HEADROOM] %s: %d→%d tokens (%.0f%% saved)",
                            model, result.tokens_before, result.tokens_after,
                            (1 - result.tokens_after / max(result.tokens_before, 1)) * 100,
                        )
                        messages = result.messages
        except ImportError:
            pass
        except Exception as e:
            logger.debug("[HEADROOM] compression failed: %s", e)

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

        in_think = False
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        if fmt == "generate":
                            content = data.get("response", "")
                        elif "message" in data:
                            content = data["message"].get("content", "")
                        else:
                            content = ""
                        if content:
                            cleaned, in_think = _strip_think(content, in_think)
                            if cleaned:
                                yield cleaned
                        if data.get("done"):
                            break

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        result = "".join(chunks)
        result, _ = _strip_think(result, False)
        return result
