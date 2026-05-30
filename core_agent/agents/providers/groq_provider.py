import json
import logging
import os
from typing import Any, Dict, List, Optional

from core_agent.agents.context_builder import build_system_prompt
from core_agent.agents.providers.base_provider import BaseProvider
from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

logger = logging.getLogger("groq-provider")

_URL = "https://api.groq.com/openai/v1/chat/completions"

TOOLS: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "get_odds_snapshot",
        "description": "Return latest odds for one or all tracks.",
        "parameters": {"type": "object", "properties": {
            "track": {"type": "string", "description": "Track name, or omit for all"}
        }, "required": []},
    }},
    {"type": "function", "function": {
        "name": "get_account_summary",
        "description": "Return bankroll balance, P&L and open bets.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "verify_race_exists",
        "description": "Check if a race is scheduled today.",
        "parameters": {"type": "object", "properties": {
            "track": {"type": "string"},
            "race_number": {"type": "integer"},
        }, "required": ["track", "race_number"]},
    }},
    {"type": "function", "function": {
        "name": "search_past_races",
        "description": "Search historical race data.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string"}
        }, "required": ["query"]},
    }},
    {"type": "function", "function": {
        "name": "calculate_probability_edge",
        "description": "Calculate betting edge from decimal odds and estimated probability.",
        "parameters": {"type": "object", "properties": {
            "decimal_odds": {"type": "number"},
            "estimated_probability": {"type": "number"},
        }, "required": ["decimal_odds", "estimated_probability"]},
    }},
    {"type": "function", "function": {
        "name": "search_racing_data",
        "description": "Search the web for horse racing information.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query"}
        }, "required": ["query"]},
    }},
]


async def _execute_tool(name: str, args: Dict) -> Dict:
    fn = TOOL_REGISTRY.get(name)
    if not fn:
        return {"error": f"Tool '{name}' not found"}
    try:
        result = fn(**args)
        if hasattr(result, "__await__"):
            result = await result
        return result
    except Exception as e:
        return {"error": str(e)}


class GroqProvider(BaseProvider):
    MAX_RETRIES = 1

    async def _call(self, message: str, model: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")

        _tool_keywords = ("tomorrow", "yesterday", "result", "search", "find", "news", "latest", "recent", "fixture")
        needs_tools = any(kw in message.lower() for kw in _tool_keywords) or intent in ("search_racing_data", "run_daily_analysis")
        model = model or (ModelConfig.ORCHESTRATOR if needs_tools else "llama-3.1-8b-instant")

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        messages = [
            {"role": "system", "content": build_system_prompt(intent=intent)},
            {"role": "user", "content": message},
        ]

        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=25.0)
        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": 400,
            "temperature": 0.3,
        }
        if needs_tools:
            payload["tools"] = TOOLS

        resp = await client.post(_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]

        if choice.get("finish_reason") == "tool_calls":
            messages.append(choice["message"])
            for tc in choice["message"].get("tool_calls", []):
                fn_name = tc["function"]["name"]
                fn_args = json.loads(tc["function"].get("arguments", "{}"))
                result = await _execute_tool(fn_name, fn_args)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": json.dumps(result),
                })

            payload2 = {
                "model": model,
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.3,
            }
            if needs_tools:
                payload2["tools"] = TOOLS
            resp2 = await client.post(_URL, headers=headers, json=payload2)
            resp2.raise_for_status()
            data = resp2.json()

        text = data["choices"][0]["message"]["content"]
        return AgentReply(summary=text, model_used=f"groq:{model}")


provider = GroqProvider()
chat = provider.chat
