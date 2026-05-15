"""
Ollama provider — local model via native Ollama API.
Single responsibility: send a message to a local Ollama model, return text.
"""

import logging
from typing import Optional

import httpx

from core_agent.agents.context_builder import build_system_prompt
from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("ollama-provider")


async def chat(message: str, model: Optional[str] = None) -> AgentReply:
    """Send message to local Ollama, return AgentReply."""
    model = model or ModelConfig.SCRAPER
    url = ModelConfig.ollama_native_url("/api/chat")
    system_prompt = build_system_prompt()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "stream": False,
        "options": {"num_predict": 256, "temperature": 0.1},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()

    text = data.get("message", {}).get("content", "")
    if not text:
        raise ValueError(f"Empty response from Ollama model {model}")

    return AgentReply(summary=text, model_used=f"ollama:{model}")
