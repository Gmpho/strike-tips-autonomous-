"""
Strike Tips - Centralized Model Configuration
"""

import os

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


class ModelConfig:
    # Ollama host — kept for ChromaDB embedding (falls through to Gemini when down)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "https://gmpho--strike-tips-ollama-cloud-ollama.modal.run")
    EMBEDDER = os.getenv("MODEL_EMBEDDER", "embeddinggemma:300m")

    # Fallback chains — production Gemini models
    PARALLEL = "gemini-2.5-flash"
    CLOUD_FALLBACK = "gemini-2.5-flash"
    GEMINI_CHAIN = ["gemini-2.5-flash", "gemini-2.0-flash"]

    # Groq production models (live-verified Sep-2026: llama/deepseek retired)
    ORCHESTRATOR = "openai/gpt-oss-120b"  # Tool calling + reasoning
    GROQ_FAST = "openai/gpt-oss-20b"         # Fast reads
    GROQ_REASONER = "openai/gpt-oss-120b"  # Deep math/edge calculations
    GROQ_QWEN_38 = "openai/gpt-oss-20b"      # Tabular racecard & form analysis
    GROQ_QWEN_36 = "openai/gpt-oss-20b"      # Steward reports & rapid summarization
    GROQ_GEMMA2 = "openai/gpt-oss-20b"       # Fast Google-style calls on Groq

    @classmethod
    def groq_available(cls) -> bool:
        """Check if Groq API key is configured."""
        return bool(os.getenv("GROQ_API_KEY"))
