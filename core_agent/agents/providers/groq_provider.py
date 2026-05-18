"""
Groq provider — direct OpenAI-compatible API with proper tool calling.
Single responsibility: send a message to Groq, execute any tool calls, return text.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from core_agent.agents.context_builder import build_system_prompt
from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

logger = logging.getLogger("groq-provider")

_URL = "https://api.groq.com/openai/v1/chat/completions"

# OpenAI-format tool definitions for the 5 most useful tools
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
        "description": "Search the web for horse racing information — tomorrow's races, results, news, track conditions.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Search query e.g. 'tomorrow SA races 2026' or 'Kenilworth results today'"}
        }, "required": ["query"]},
    }},
]


async def _execute_tool(name: str, args: Dict) -> Dict:
    """Execute a registered tool and return its result."""
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


async def chat(message: str, model: Optional[str] = None) -> AgentReply:
    """Send message to Groq, handle tool calls, return AgentReply."""
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")

    # Use fast 8b for simple queries, 70b only when tools are likely needed
    _tool_keywords = ("tomorrow", "yesterday", "result", "search", "find", "news", "latest", "recent", "fixture")
    needs_tools = any(kw in message.lower() for kw in _tool_keywords)
    model = model or (ModelConfig.ORCHESTRATOR if needs_tools else "llama-3.1-8b-instant")

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": message},
    ]

    async with httpx.AsyncClient(timeout=25.0) as client:
        # Only pass tools to the 70b model — 8b hallucinates tool calls
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

        # Execute tool calls if requested
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
                logger.debug(f"Tool {fn_name}({fn_args}) → {str(result)[:100]}")

            # Second call with tool results
            resp2 = await client.post(_URL, headers=headers, json={
                "model": model,
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.3,
            })
            resp2.raise_for_status()
            data = resp2.json()

    text = data["choices"][0]["message"]["content"]
    return AgentReply(summary=text, model_used=f"groq:{model}")
