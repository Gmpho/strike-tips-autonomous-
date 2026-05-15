"""
Gemini provider — direct REST API call (no agent_framework dependency).
Single responsibility: send a message to Gemini, return text.
"""

import json
import logging
import os
from typing import Optional

import httpx

from core_agent.agents.context_builder import build_system_prompt
from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("gemini-provider")

_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


async def chat(message: str, model: Optional[str] = None) -> AgentReply:
    """Send message to Gemini REST API, return AgentReply."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    model = model or ModelConfig.GEMINI_CHAIN[0]
    system_prompt = build_system_prompt()
    url = f"{_BASE}/{model}:generateContent?key={api_key}"

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": message}]}],
        "generationConfig": {"maxOutputTokens": 400, "temperature": 0.3},
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    token_usage = {
        "input": usage.get("promptTokenCount"),
        "output": usage.get("candidatesTokenCount"),
        "total": usage.get("totalTokenCount"),
    }
    return AgentReply(summary=text, model_used=f"gemini:{model}", token_usage=token_usage)
