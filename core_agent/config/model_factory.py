import os
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from dotenv import load_dotenv

load_dotenv()

def get_model(tier: str):
    """Factory to retrieve the correct model based on .env config."""
    # Force host.docker.internal for Docker-based backend
    ollama_host = "http://host.docker.internal:11434"
    model_name = os.getenv(f"{tier.upper()}_MODEL", "racing_llama")
    provider_type = os.getenv(f"{tier.upper()}_PROVIDER", "ollama")
    
    if provider_type == "ollama":
        provider = OllamaProvider(base_url=f"{ollama_host}/v1")
        return OpenAIChatModel(model_name=model_name, provider=provider)
    else:
        # Generic OpenAI-compatible client (Groq, Gemini, etc.)
        return OpenAIChatModel(model_name=model_name)
