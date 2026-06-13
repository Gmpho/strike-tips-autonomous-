from __future__ import annotations
import os
import json
import inspect
import logging
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.agent.providers.retry import retry_on_429
from core_agent.agent.prompts import build_system_prompt
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
from core_agent.core.http_client import get_async_client
from core_agent.core.strike_brain import brain

logger = logging.getLogger("groq-provider")


class GroqProvider:
    URL = "https://api.groq.com/openai/v1/chat/completions"
    MODELS = ["llama-3.1-8b-instant", "llama-3.3-70b-versatile"]

    def __init__(self) -> None:
        self.api_key = os.getenv("GROQ_API_KEY", "")
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
        def _schema(fn):
            sig = inspect.signature(fn)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname in ("strike", "kwargs", "args"):
                    continue
                ptype = "string"
                anno = param.annotation
                origin = getattr(anno, "__origin__", None)
                if origin is list:
                    ptype = "array"
                elif origin is dict:
                    ptype = "object"
                else:
                    if anno in (int, float):
                        ptype = "number"
                    elif anno is bool:
                        ptype = "boolean"
                entry = {"type": ptype, "description": pname.replace("_", " ")}
                if param.default is not inspect.Parameter.empty:
                    entry["default"] = None if param.default is None else str(param.default)
                else:
                    required.append(pname)
                props[pname] = entry
            return {"type": "object", "properties": props, "required": required}

        return [
            {"type": "function", "function": {"name": name, "description": fn.__doc__ or "", "parameters": _schema(fn)}}
            for name, fn in TOOL_REGISTRY.items()
        ]

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

    async def _post_and_parse(self, messages: list[dict], needs_tools: bool, model: str) -> tuple[str, list[dict]]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": build_system_prompt()}] + messages,
            "max_tokens": 800,
            "temperature": 0.3,
        }
        if needs_tools:
            payload["tools"] = self._get_tools()

        client = get_async_client(timeout=30.0)
        async def _do_post():
            return await client.post(self.URL, headers=headers, json=payload)
        resp = await retry_on_429(_do_post, max_retries=1, base_delay=1.0)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]

        content = choice.get("message", {}).get("content", "") or ""
        tool_calls_raw = choice.get("message", {}).get("tool_calls", [])

        tool_calls = []
        for tc in tool_calls_raw:
            tool_calls.append({
                "id": tc.get("id", ""),
                "name": tc["function"]["name"],
                "args": tc["function"].get("arguments", "{}"),
            })

        return content, tool_calls

    async def stream(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> AsyncIterator[str]:
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set")

        last_msg = messages[-1]["content"] if messages else ""
        needs_tools = self._needs_tools(last_msg, intent)
        model = "llama-3.1-8b-instant" if not needs_tools else "llama-3.3-70b-versatile"

        content, tool_calls = await self._post_and_parse(messages, needs_tools, model)
        if content:
            yield content

        if tool_calls:
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls:
                if tc.get("name") and tc.get("args"):
                    try:
                        args = json.loads(tc["args"]) or {}
                    except Exception:
                        args = {}
                    result = await self._execute_tool(tc["name"], args)
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "content": json.dumps(result)})

            content2, _ = await self._post_and_parse(messages, needs_tools, model)
            if content2:
                yield content2

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        return "".join(chunks)
