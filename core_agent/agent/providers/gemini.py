from __future__ import annotations
import os
import json
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.agent.providers.retry import retry_on_429
from core_agent.agent.prompts import build_system_prompt
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
from core_agent.core.http_client import get_async_client


class GeminiProvider:
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS = ["gemini-2.0-flash", "gemini-2.5-flash"]

    def __init__(self) -> None:
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self._tool_keywords = (
            "bet", "place", "stake", "record", "selection", "settle", "value", "edge",
            "tomorrow", "yesterday", "result", "search", "find", "news", "latest", "recent", "fixture",
            "evaluate", "analyse", "analyze", "scan", "account", "balance", "bankroll", "profit",
            "wager", "lay", "tip", "recommend", "odds",
            "market", "mover", "predictor", "prediction", "probability", "stake", "bank",
            "race", "runner", "horse", "jockey", "trainer",
        )

    def _needs_tools(self, message: str, intent: str | None) -> bool:
        msg = message.lower()
        return any(kw in msg for kw in self._tool_keywords) or intent in (
            "search_racing_data", "run_daily_analysis", "get_account_summary",
            "calculate_max_position", "verify_race_exists", "get_odds_snapshot"
        )

    def _get_tools(self) -> list[dict]:
        return [{
            "functionDeclarations": [
                {"name": name, "description": fn.__doc__ or "", "parameters": {"type": "object", "properties": {}, "required": []}}
                for name, fn in TOOL_REGISTRY.items()
            ]
        }]

    async def _execute_tool(self, name: str, args: dict | None) -> dict:
        fn = TOOL_REGISTRY.get(name)
        if not fn:
            return {"error": f"Tool '{name}' not found"}
        try:
            kwargs = dict(args or {})
            if "strike" in inspect.signature(fn).parameters:
                from core_agent.core.strike_brain import brain
                if brain and brain.strike:
                    kwargs["strike"] = brain.strike
            result = fn(**kwargs)
            import inspect as _inspect
            if _inspect.iscoroutine(result):
                result = await result
            return result
        except Exception as e:
            return {"error": str(e)}

    async def stream(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

        last_msg = messages[-1]["content"] if messages else ""
        needs_tools = self._needs_tools(last_msg, intent)
        model = self.MODELS[0]

        url = f"{self.BASE}/{model}:generateContent?key={self.api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": build_system_prompt()}]},
            "contents": [{"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]} for m in messages],
            "generationConfig": {"maxOutputTokens": 400, "temperature": 0.3},
        }
        if needs_tools:
            payload["tools"] = self._get_tools()

        client = get_async_client(timeout=15.0)
        async def _do_post():
            return await client.post(url, json=payload)
        resp = await retry_on_429(_do_post, max_retries=1, base_delay=1.0)
        resp.raise_for_status()
        data = resp.json()

        candidates = data.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            for p in parts:
                if "text" in p:
                    yield p["text"]

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        return "".join(chunks)
