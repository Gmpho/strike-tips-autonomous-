import os
from dotenv import load_dotenv
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider

load_dotenv()

# ── Tier → (provider_type, model_name) resolution ────────────────────────────


def _resolve(tier_or_model: str) -> tuple[str, str]:
    """Return (provider_type, model_name) for a ModelConfig tier key OR direct model name."""
    from core_agent.config.model_config import ModelConfig

    # Check if it's a tier key or a direct model name
    model_name = getattr(ModelConfig, tier_or_model, None)
    if not model_name:
        model_name = tier_or_model

    # Strip local: prefix
    if model_name.startswith("local:"):
        return "ollama", model_name.split(":", 1)[1]

    # Cloud Ollama suffix
    if model_name.endswith(":cloud"):
        return "ollama_cloud", model_name

    # Gemini models
    if any(g in model_name for g in ("gemini", "flash", "pro")):
        return "gemini", model_name

    # ORCHESTRATOR tier → Groq when key is available
    if tier_or_model == "ORCHESTRATOR" and ModelConfig.groq_available():
        return "groq", "llama-3.3-70b-versatile"

    return "ollama", model_name


def get_client(tier_or_model: str):
    """
    Return a MAF client for the given ModelConfig tier or specific model.
    Ollama → OllamaClient, Groq/Gemini → OpenAIChatClient (OpenAI-compat).
    """
    from agent_framework.ollama import OllamaChatClient
    from agent_framework.openai import OpenAIChatClient
    from core_agent.config.model_config import ModelConfig
    import os

    provider, model = _resolve(tier_or_model)
    ollama_host = ModelConfig.ollama_host()

    if provider == "ollama":
        return OllamaChatClient(model_id=model, host=ollama_host)

    if provider == "ollama_cloud":
        # Cloud-hosted Ollama might require an API Key
        api_key = os.getenv("OLLAMA_API_KEY", "")
        # Assuming OllamaChatClient can handle headers or specific cloud auth
        # If not, we fallback to native Ollama logic
        return OllamaChatClient(
            model_id=model,
            host=ollama_host,
            # headers={"X-API-Key": api_key} if api_key else None
        )

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
    return OllamaChatClient(model_id=model, host=ollama_host)


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

    ollama_host = ModelConfig.ollama_openai_base_url()
    model_name = os.getenv(f"{tier.upper()}_MODEL", "racing_llama")
    provider_type = os.getenv(f"{tier.upper()}_PROVIDER", "ollama")
    if provider_type == "ollama":
        provider = OllamaProvider(base_url=ollama_host)
        return OpenAIChatModel(model_name=model_name, provider=provider)
    return OpenAIChatModel(model_name=model_name)
