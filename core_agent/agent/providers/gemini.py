from __future__ import annotations
import os
import json
import inspect
from collections.abc import AsyncIterator
from core_agent.agent.providers.base import LLMProvider
from core_agent.agent.providers.retry import retry_on_429
from core_agent.agent.prompts import build_system_prompt
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
from core_agent.core.http_client import get_async_client


class GeminiProvider:
    BASE = "https://generativelanguage.googleapis.com/v1beta/models"
    MODELS = ["gemini-1.5-flash", "gemini-2.0-flash", "gemini-2.5-flash"]

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
        def _schema(fn):
            sig = inspect.signature(fn)
            props = {}
            required = []
            for pname, param in sig.parameters.items():
                if pname in ("strike", "kwargs", "args"):
                    continue
                ptype = "STRING"
                anno = param.annotation
                origin = getattr(anno, "__origin__", None)
                if origin is list:
                    ptype = "ARRAY"
                elif origin is dict:
                    ptype = "OBJECT"
                else:
                    if anno in (int, float):
                        ptype = "NUMBER"
                    elif anno is bool:
                        ptype = "BOOLEAN"
                entry = {"type": ptype, "description": pname.replace("_", " ")}
                if param.default is not inspect.Parameter.empty:
                    entry["default"] = None if param.default is None else str(param.default)
                else:
                    required.append(pname)
                props[pname] = entry
            return {"type": "OBJECT", "properties": props, "required": required}

        return [{
            "functionDeclarations": [
                {"name": name, "description": fn.__doc__ or "", "parameters": _schema(fn)}
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

        from core_agent.agent.providers.task_router import TaskRouter
        raw_msg = TaskRouter._extract_user_query(messages)
        needs_tools = self._needs_tools(raw_msg, intent)
        model = self.MODELS[0]

        contents = []
        for m in messages:
            role = m.get("role")
            content = m.get("content") or ""
            if role == "user":
                contents.append({"role": "user", "parts": [{"text": content}]})
            elif role == "assistant":
                parts = []
                if content:
                    parts.append({"text": content})
                tool_calls = m.get("tool_calls")
                if tool_calls:
                    for tc in tool_calls:
                        parts.append({
                            "functionCall": {
                                "name": tc["name"],
                                "args": json.loads(tc["args"]) if isinstance(tc["args"], str) else tc["args"]
                            }
                        })
                contents.append({"role": "model", "parts": parts})
            elif role == "tool":
                tool_call_id = m.get("tool_call_id")
                name = m.get("name")
                if not name and tool_call_id:
                    for msg in reversed(messages):
                        if msg.get("role") == "assistant" and msg.get("tool_calls"):
                            for tc in msg["tool_calls"]:
                                if tc.get("id") == tool_call_id:
                                    name = tc.get("name")
                                    break
                            if name:
                                break
                if not name:
                    name = "unknown"
                
                resp_obj = content
                try:
                    if isinstance(content, str):
                        resp_obj = json.loads(content)
                except Exception:
                    resp_obj = {"result": content}

                contents.append({
                    "role": "function",
                    "parts": [{
                        "functionResponse": {
                            "name": name,
                            "response": resp_obj if isinstance(resp_obj, dict) else {"result": resp_obj}
                        }
                    }]
                })

        resp = None
        last_err = None
        active_model = None

        for model in self.MODELS:
            payload = {
                "system_instruction": {"parts": [{"text": build_system_prompt(for_cloud=True)}]},
                "contents": contents,
                "generationConfig": {"maxOutputTokens": 400, "temperature": 0.3},
            }
            if needs_tools:
                payload["tools"] = self._get_tools()

            client = get_async_client(timeout=15.0)
            async def _do_post(p_payload, p_model=model):
                url = f"{self.BASE}/{p_model}:generateContent?key={self.api_key}"
                return await client.post(url, json=p_payload)

            try:
                logger.info("[GEMINI] Trying model %s", model)
                resp = await retry_on_429(lambda: _do_post(payload, model), max_retries=1, base_delay=1.0)
                resp.raise_for_status()
                logger.info("[GEMINI] Success with model %s", model)
                active_model = model
                break
            except Exception as e:
                logger.warning("[GEMINI] Model %s failed: %s", model, e)
                last_err = e

        if not resp or not active_model:
            if last_err:
                raise last_err
            raise RuntimeError("All Gemini models failed")

        data = resp.json()

        candidates = data.get("candidates", [])
        if not candidates:
            return

        parts = candidates[0].get("content", {}).get("parts", [])
        function_calls = []
        for p in parts:
            if "text" in p:
                yield p["text"]
            if "functionCall" in p:
                fc = p["functionCall"]
                function_calls.append({
                    "name": fc["name"],
                    "args": fc.get("args", {}),
                })

        if function_calls:
            # Append model turn with function calls
            gemini_parts = []
            for fc in function_calls:
                gemini_parts.append({
                    "functionCall": {
                        "name": fc["name"],
                        "args": fc["args"]
                    }
                })
            payload["contents"].append({
                "role": "model",
                "parts": gemini_parts
            })

            # Execute function calls and add to request turn
            tool_response_parts = []
            for fc in function_calls:
                result = await self._execute_tool(fc["name"], fc["args"])
                tool_response_parts.append({
                    "functionResponse": {
                        "name": fc["name"],
                        "response": {"result": result}
                    }
                })

            payload["contents"].append({
                "role": "function",
                "parts": tool_response_parts
            })

            # Call Gemini again with the tool responses
            resp2 = await retry_on_429(lambda: _do_post(payload, active_model), max_retries=1, base_delay=1.0)
            resp2.raise_for_status()
            data2 = resp2.json()

            candidates2 = data2.get("candidates", [])
            if candidates2:
                parts2 = candidates2[0].get("content", {}).get("parts", [])
                for p2 in parts2:
                    if "text" in p2:
                        yield p2["text"]

    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        chunks = []
        async for chunk in self.stream(messages, tools, intent):
            chunks.append(chunk)
        return "".join(chunks)
