import os
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

load_dotenv()

# ── Tier → (provider_type, model_name) resolution ────────────────────────────

def _resolve(tier: str) -> tuple[str, str]:
    """Return (provider_type, model_name) for a ModelConfig tier key."""
    from core_agent.config.model_config import ModelConfig
    model_name = getattr(ModelConfig, tier, None) or os.getenv(f"{tier.upper()}_MODEL", "racing_llama")

    # Strip local: prefix → always Ollama
    if model_name.startswith("local:"):
        return "ollama", model_name.split(":", 1)[1]

    # Gemini models
    if any(g in model_name for g in ("gemini", "flash", "pro")):
        return "gemini", model_name

    # ORCHESTRATOR tier → Groq when key is available
    if tier == "ORCHESTRATOR" and ModelConfig.groq_available():
        return "groq", "llama-3.3-70b-versatile"

    return "ollama", model_name


def get_client(tier: str):
    """
    Return a MAF client for the given ModelConfig tier.
    Ollama → OllamaClient, Groq/Gemini → OpenAIChatClient (OpenAI-compat).
    """
    from agent_framework.ollama import OllamaChatClient
    from agent_framework.openai import OpenAIChatClient
    from core_agent.config.model_config import ModelConfig

    provider, model = _resolve(tier)
    ollama_host = ModelConfig.OLLAMA_HOST or "http://localhost:11434"

    if provider == "ollama":
        return OllamaChatClient(model_id=model, host=ollama_host)
    if provider == "groq":
        return OpenAIChatClient(
            model_id=model,
            base_url="https://api.groq.com/openai/v1",
            api_key=os.getenv("GROQ_API_KEY", ""),
        )
    if provider == "gemini":
        return OpenAIChatClient(
            model_id=model,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            api_key=os.getenv("GEMINI_API_KEY", ""),
        )
    # fallback
    return OllamaClient(model=model, host=ollama_host)


def get_client_chain(tiers: list[str]) -> list:
    """Return ordered list of MAF clients for fallback chain."""
    clients = []
    for tier in tiers:
        try:
            clients.append(get_client(tier))
        except Exception:
            pass
    return clients


# ── Deprecated: pydantic-ai model factory (kept for backward compat) ─────────

def get_model(tier: str):
    """Deprecated. Use get_client() for MAF agents."""
    from core_agent.config.model_config import ModelConfig
    ollama_host = "http://host.docker.internal:11434"
    model_name = os.getenv(f"{tier.upper()}_MODEL", "racing_llama")
    provider_type = os.getenv(f"{tier.upper()}_PROVIDER", "ollama")
    if provider_type == "ollama":
        provider = OllamaProvider(base_url=f"{ollama_host}/v1")
        return OpenAIChatModel(model_name=model_name, provider=provider)
    return OpenAIChatModel(model_name=model_name)
