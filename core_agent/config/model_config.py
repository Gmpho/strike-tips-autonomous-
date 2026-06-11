"""
Strike Tips - Centralized Model Configuration
"""

import os

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


class ModelConfig:
    # Ollama host — kept for ChromaDB embedding (falls through to Gemini when down)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "https://gmpho--strike-tips-racing-ollama-server.modal.run")
    EMBEDDER = os.getenv("MODEL_EMBEDDER", "embeddinggemma:300m")

    # Fallback chains — latest Gemini models (GA as of May 2026)
    PARALLEL = "gemini-3.5-flash"
    CLOUD_FALLBACK = "gemini-3.5-flash"
    GEMINI_CHAIN = ["gemini-3.5-flash", "gemini-3.1-flash-lite", "gemini-3-flash"]

    # Groq model alias
    ORCHESTRATOR = "llama-3.3-70b-versatile"  # Better tool calling than 8b

    @classmethod
    def groq_available(cls) -> bool:
        """Check if Groq API key is configured."""
        return bool(os.getenv("GROQ_API_KEY"))
