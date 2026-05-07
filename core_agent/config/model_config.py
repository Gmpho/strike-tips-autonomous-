"""
Strike Tips - Centralized Model Configuration
Based on OpenClaw/MAF verified patterns.
Uses native Ollama API (no /v1) and strictly defined provider blocks.
"""

import os
from typing import Dict, List

# Load environment variables
from dotenv import load_dotenv

load_dotenv()


class ModelConfig:
    # ── HARDWARE GUARD (Optimized for 8GB RAM)
    LOCAL_THREADS = int(os.getenv("LOCAL_THREADS", "3"))
    LOCAL_GPU = int(os.getenv("LOCAL_GPU", "0"))
    LOCAL_CTX = int(os.getenv("MAX_LOCAL_CTX", "32768"))

    # ── MODEL REGISTRY
    # We define providers explicitly to stop the container from guessing.
    # Native Ollama API: http://host.docker.internal:11434 (no /v1)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_HOST", "http://host.docker.internal:11434")

    # Local Specialist Swarm (The "Resident" Trio)
    # These stay loaded in RAM thanks to OLLAMA_MAX_LOADED_MODELS=3
    LOCAL_MODELS = [
        {"id": "func_gemma", "name": "func_gemma", "input": ["text"]},
        {"id": "lfm_racing", "name": "lfm_racing", "input": ["text"]},
        {"id": "racing_llama", "name": "racing_llama", "input": ["text"]},
    ]

    # Cloud Proxy Swarm (Accessed via Host's Ollama Sign-in)
    # These are manifest-only pointers; they use no local space.
    CLOUD_MODELS = [
        {
            "id": "gemini-3-flash-preview:cloud",
            "name": "gemini-3-flash-preview:cloud",
            "input": ["text", "image"],
        },
        {"id": "gemma4:31b-cloud", "name": "gemma4:31b-cloud", "input": ["text"]},
        {"id": "qwen3.5:397b-cloud", "name": "qwen3.5:397b-cloud", "input": ["text"]},
        {
            "id": "nemotron-3-nano:30b-cloud",
            "name": "nemotron-3-nano:30b-cloud",
            "input": ["text"],
        },
        {"id": "glm-4.7:cloud", "name": "glm-4.7:cloud", "input": ["text"]},
    ]

    # Fallback chains
    PARALLEL = "gemini-3-flash-preview:cloud"
    CLOUD_FALLBACK = "gemini-3-flash-preview:cloud"
    GEMINI_CHAIN = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-3-flash-preview"]

    @classmethod
    def get_provider_config(cls) -> Dict:
        """Returns OpenClaw-verified provider configuration."""
        return {
            "models": {
                "providers": {
                    "ollama": {
                        "baseUrl": cls.OLLAMA_BASE_URL,
                        "apiKey": "ollama-local",
                        "api": "ollama",  # Native API mode
                        "timeoutSeconds": 300,
                        "contextWindow": cls.LOCAL_CTX,
                        "models": cls.LOCAL_MODELS + cls.CLOUD_MODELS,
                    }
                }
            }
        }

    @classmethod
    def groq_available(cls) -> bool:
        """Check if Groq API key is configured."""
        return bool(os.getenv("GROQ_API_KEY"))

    @classmethod
    def ollama_host(cls) -> str:
        """Return the base URL of the Ollama host."""
        return cls.OLLAMA_BASE_URL

    @classmethod
    def ollama_native_url(cls, path: str) -> str:
        """Native Ollama API endpoint builder (/api/*)."""
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{cls.ollama_host()}{clean_path}"

    @classmethod
    def summary(cls) -> str:
        return f"=== Strike Tips Config ===\nHost: {cls.OLLAMA_BASE_URL}\nSwarm Size: {len(cls.LOCAL_MODELS) + len(cls.CLOUD_MODELS)}"


if __name__ == "__main__":
    print(ModelConfig.summary())
