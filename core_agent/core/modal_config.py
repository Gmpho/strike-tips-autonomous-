"""
Strike Tips - Modal Deployment Configuration
Optimized for Modal's free tier ($30 credit)
"""

import modal
import os

# Create Modal app
app = modal.App("strike-tips")

# Lightweight image with minimal dependencies
image = (
    modal.Image.debian_slim()
    .apt_install("curl")
    .pip_install(
        "httpx",
        "beautifulsoup4",
        "python-telegram-bot",
        "google-generativeai",
        "anthropic",
        "openai",
    )
)

# Secrets for API keys
secrets = [
    modal.Secret.from_name(
        "strike-tips-secrets",
        required_keys=[
            "TELEGRAM_BOT_TOKEN",
            "TELEGRAM_CHAT_ID",
        ],
    )
]

# Optional AI provider secrets (at least one recommended)
ai_secrets = modal.Secret.from_dict(
    {
        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "OLLAMA_HOST": os.getenv("OLLAMA_HOST", "http://localhost:11434"),
    }
)

# Volume for persistent data (bet history, bankroll)
data_volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)
