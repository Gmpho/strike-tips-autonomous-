import os
from dotenv import load_dotenv

load_dotenv()

# ── Tier → (provider_type, model_name) resolution ────────────────────────────


def _resolve(tier_or_model: str) -> tuple[str, str]:
    """Return (provider_type, model_name) for a ModelConfig tier key OR direct model name."""
    from core_agent.config.model_config import ModelConfig

    # Check if it's a tier key or a direct model name
    model_name = getattr(ModelConfig, tier_or_model, None)
    if not model_name:
        model_name = tier_or_model

    # Gemini models
    if any(g in model_name for g in ("gemini", "flash", "pro")):
        return "gemini", model_name

    # ORCHESTRATOR tier → Groq when key is available
    if tier_or_model == "ORCHESTRATOR" and ModelConfig.groq_available():
        return "groq", "llama-3.3-70b-versatile"

    return "groq", model_name


def get_client(tier_or_model: str):
    """
    Return a MAF client for the given ModelConfig tier or specific model.
    Groq/Gemini → OpenAIChatClient (OpenAI-compat).
    """
    from agent_framework.openai import OpenAIChatClient
    from core_agent.config.model_config import ModelConfig
    import os

    provider, model = _resolve(tier_or_model)

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
    return OpenAIChatClient(
        model_id=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY", ""),
    )


def get_client_chain(tiers: list[str]) -> list:
    """Return ordered list of MAF clients for fallback chain."""
    clients = []
    for tier in tiers:
        try:
            clients.append(get_client(tier))
        except Exception:
            pass
    return clients
