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

    # Groq production models
    ORCHESTRATOR = "llama-3.3-70b-versatile"  # Tool calling + reasoning
    GROQ_FAST = "llama-3.1-8b-instant"         # Fast reads
    GROQ_REASONER = "deepseek-r1-distill-llama-70b"  # Deep math/edge calculations
    GROQ_QWEN_38 = "qwen/qwen3.8-27b"          # Tabular racecard & form analysis
    GROQ_QWEN_36 = "qwen/qwen3.6-27b"          # Steward reports & rapid summarization
    GROQ_GEMMA2 = "gemma2-9b-it"              # Ultra-fast Google architecture on Groq

    @classmethod
    def groq_available(cls) -> bool:
        """Check if Groq API key is configured."""
        return bool(os.getenv("GROQ_API_KEY"))
