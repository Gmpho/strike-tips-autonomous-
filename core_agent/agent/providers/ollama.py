from __future__ import annotations
import asyncio
import inspect
import json
import os
import re
import httpx
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.config.model_registry import get_model_by_id
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
import logging

logger = logging.getLogger("ollama-provider")

_THINK_RE = re.compile(r'<think>.*?</think>', re.DOTALL)
_TOOL_RE = re.compile(r'^\s*TOOL:\s*(\w+)\((\{.*?\})\)\s*$', re.MULTILINE)

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
                "options": {
                    "num_ctx": 2048,
                    "temperature": 0.2
                }
            }
        else:
            url = f"{self.host}/api/chat"
            payload = {
                "model": model,
                "messages": messages,
                "stream": True,
                "options": {
                    "num_ctx": 2048,
                    "temperature": 0.2
                }
            }

        in_think = False
        async with httpx.AsyncClient(timeout=600.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                buffer = ""
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning("[OLLAMA] non-JSON response from %s: %r", url, line[:80])
                        continue
                    if fmt == "generate":
                        content = data.get("response", "")
                    elif "message" in data:
                        content = data["message"].get("content", "")
                    else:
                        content = ""
                    if content:
                        cleaned, in_think = _strip_think(content, in_think)
                        if cleaned:
                            buffer += cleaned
                    if data.get("done"):
                        break

        # ── TOOL: interceptor ──────────────────────────────────────────────────
        tool_match = _TOOL_RE.search(buffer)
        if tool_match:
            tool_name = tool_match.group(1)
            try:
                tool_args = json.loads(tool_match.group(2))
            except json.JSONDecodeError:
                tool_args = {}

            fn = TOOL_REGISTRY.get(tool_name)
            if fn:
                try:
                    kwargs = dict(tool_args)
                    if "strike" in inspect.signature(fn).parameters:
                        from core_agent.core.strike_brain import brain
                        if brain and brain.strike:
                            kwargs["strike"] = brain.strike
                    if asyncio.iscoroutinefunction(fn):
                        result = await fn(**kwargs)
                    else:
                        result = fn(**kwargs)
                    result_text = json.dumps(result, indent=2) if isinstance(result, dict) else str(result)
                    logger.info("[OLLAMA] TOOL: %s executed successfully", tool_name)
                    pre_tool = buffer[:tool_match.start()].strip()
                    yield (pre_tool + "\n\n" if pre_tool else "") + f"**{tool_name} result:**\n```\n{result_text}\n```"
                    return
                except Exception as e:
                    logger.warning("[OLLAMA] TOOL: %s failed: %s", tool_name, e)
                    yield buffer + f"\n\n*(Tool {tool_name} failed: {e})*"
                    return
            else:
                logger.warning("[OLLAMA] TOOL: unknown tool '%s'", tool_name)

        if buffer:
            yield buffer

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        result = "".join(chunks)
        result, _ = _strip_think(result, False)
        return result
