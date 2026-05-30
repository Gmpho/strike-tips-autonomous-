import logging
import os
from typing import Optional

from core_agent.agents.context_builder import build_system_prompt
from core_agent.agents.providers.base_provider import BaseProvider
from core_agent.agents.schemas import AgentReply
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("ollama-provider")

OLLAMA_CLOUD_BASE = "https://api.ollama.com"


class OllamaProvider(BaseProvider):
    MAX_RETRIES = 1

    async def _call(self, message: str, model: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
        model = model or ModelConfig.SCRAPER
        system_prompt = build_system_prompt(intent=intent)

        api_key = os.getenv("OLLAMA_API_KEY")
        if api_key:
            url = f"{OLLAMA_CLOUD_BASE}/api/chat"
            headers = {"Authorization": f"Bearer {api_key}"}
        else:
            url = ModelConfig.ollama_native_url("/api/chat")
            headers = {}

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message},
            ],
            "stream": False,
            "options": {"num_predict": 256, "temperature": 0.1},
        }

        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=30.0)
        resp = await client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        text = data.get("message", {}).get("content", "")
        if not text:
            raise ValueError(f"Empty response from Ollama model {model}")

        return AgentReply(summary=text, model_used=f"ollama:{model}")


provider = OllamaProvider()
chat = provider.chat
