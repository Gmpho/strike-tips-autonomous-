"""
Strike Tips - AI Providers
Unified orchestrator for Gemini, Groq, and Ollama (Local/Cloud).
"""
import os
import json
import logging
import asyncio
from openai import OpenAI
from dataclasses import dataclass
from typing import Optional, List
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("strike-ai")

@dataclass
class AIResponse:
    content: str
    provider: str
    error: Optional[str] = None

class AIProvider:
    ALLOWED_MODELS = {
        "ollama": ["racing_llama", "racing_qwen", "func_gemma", "lfm_racing", "ds_racing", "llama3.2:1b"],
        "groq": ["llama-3.3-70b-versatile"],
        "gemini": ["gemini-1.5-flash", "gemini-1.5-pro"]
    }

    def __init__(self):
        self._genai_client = None

    def _get_client(self, provider: str):
        if provider == "groq":
            return OpenAI(api_key=ModelConfig.GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")
        elif provider == "ollama":
            return OpenAI(api_key="ollama", base_url="http://ollama:11434/v1")
        return None

    def validate_model(self, provider: str, model: str) -> bool:
        return model in self.ALLOWED_MODELS.get(provider, [])

    async def direct_chat(self, prompt: str, model_name: str = "ollama:llama3.2:1b") -> AIResponse:
        if ":" not in model_name:
            return AIResponse(content="", provider="error", error="Invalid format. Use provider:model")
        
        provider, model = model_name.split(":", 1)
        if provider == "local":
            provider = "ollama"
            
        if not self.validate_model(provider, model):
            return AIResponse(content="", provider="error", error=f"Model {model} unauthorized")
            
        try:
            client = self._get_client(provider)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return AIResponse(content=response.choices[0].message.content, provider=provider)
        except Exception as e:
            return AIResponse(content="", provider=provider, error=str(e))
