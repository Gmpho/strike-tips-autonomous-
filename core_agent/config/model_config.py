"""
Strike Tips - Centralized Model Configuration
Single source of truth for ALL AI model assignments.

Swap any model by changing ONE .env variable - zero code changes needed.
Add a new provider by wiring a new _call_X() method in ai_providers.py.
"""
import os 
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables at the top level to ensure they are available 
# to all class-level variables in ModelConfig.
load_dotenv()


class ModelConfig:
    """ 
    Model role registry. All values are driven by .env environment variables.
    Defaults are optimized for a 16GB RAM / 256GB SSD laptop running Ollama.
    """

    # ── PRIMARY ORCHESTRATOR (Groq LPU - 14,400 req/day free)
    # Tier 1: Fastest inference, sub-second tool calling.
    ORCHESTRATOR    = os.getenv("MODEL_ORCHESTRATOR",    "local:llama3.2:1b")
    GROQ_API_KEY    = os.getenv("GROQ_API_KEY", "")

    # ── CLOUD FALLBACK CHAIN (Gemini tiers - free quota)
    # Tiers 2-4: Rotated if Groq fails or hits quota.
    # Note: gemini-1.5-flash deprecated - removed from chain
    ORCHESTRATOR_T2 = os.getenv("MODEL_ORCHESTRATOR_T2", "gemini-3-flash-preview")
    ORCHESTRATOR_T3 = os.getenv("MODEL_ORCHESTRATOR_T3", "gemini-2.5-flash")
    ORCHESTRATOR_T4 = os.getenv("MODEL_ORCHESTRATOR_T4", "gemini-2.0-flash-lite")
    ORCHESTRATOR_T5 = os.getenv("MODEL_ORCHESTRATOR_T5", "gemini-2.0-flash-lite")  # Fallback to T4

    # List for easy iteration in fallback loop
    GEMINI_CHAIN: list = [ORCHESTRATOR_T2, ORCHESTRATOR_T3, ORCHESTRATOR_T4]

    # ── HEALING SWARM (Cloud Ollama Models)
    # Optimized for autonomous repair, selector healing, and deep log analysis.
    HEALING_POOL = [
        "nemotron-3-nano:30b-cloud",
        "glm-4.7:cloud",
        "kimi-k2-thinking:cloud",
        "kimi-k2.5:cloud",
        "qwen3.5:397b-cloud",
        "gemini-3-flash-preview:cloud",
        "gemma4:31b-cloud"
    ]

    # ── PARALLEL TASKS (Kimi K2 Thinking - multi-race simultaneous dispatch)
    PARALLEL        = os.getenv("MODEL_PARALLEL",        "kimi-k2-thinking:cloud")

    # ── CLOUD REASONING FALLBACK (Tier 6 - when all above are exhausted)
    CLOUD_FALLBACK  = os.getenv("MODEL_CLOUD_FALLBACK",  "kimi-k2.5:cloud")

    # ── LOCAL MODELS (CHAT / FAST LOCAL - Always available)
    # Using OPTIMIZED Modelfiles (racing_llama, ds_racing, racing_qwen, func_gemma, lfm_racing)
    REASONER        = os.getenv("MODEL_REASONER",        "ds_racing")
    SCRAPER         = os.getenv("MODEL_SCRAPER",         "racing_qwen")
    FUNC_CALL       = os.getenv("MODEL_FUNC_CALL",       "func_gemma")
    THINKING        = os.getenv("MODEL_THINKING",         "lfm_racing")
    FAST_LOCAL      = os.getenv("MODEL_FAST_LOCAL",       "racing_llama")
    EMBEDDER        = os.getenv("MODEL_EMBEDDER",        "embeddinggemma:300m")

    # ── HARDWARE GUARD (optimized for 16GB RAM / 4-core laptop)
    # These cap memory and CPU usage for all local Ollama calls.
    MAX_LOCAL_CTX   = int(os.getenv("MAX_LOCAL_CTX",     "512"))    # context tokens (Reduced for faster local inference)
    MAX_LOCAL_PRED  = int(os.getenv("MAX_LOCAL_PRED",    "256"))    # output tokens (Reduced for faster response)
    LOCAL_THREADS   = int(os.getenv("LOCAL_THREADS",     "3"))      # CPU threads (Leave one for OS/API)
    LOCAL_GPU       = int(os.getenv("LOCAL_GPU",         "0"))      # 0 = CPU only
    LOCAL_TEMP      = float(os.getenv("LOCAL_TEMP",      "0.1"))    # low = less hallucination
    LOCAL_REPEAT_PENALTY = float(os.getenv("LOCAL_REPEAT_PENALTY", "1.2"))
    OLLAMA_HOST     = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    
    # ── OLLAMA PERFORMANCE TUNING (for 16GB RAM systems)
    OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "-1")  # -1 = keep loaded forever
    OLLAMA_FLASH_ATTENTION = os.getenv("OLLAMA_FLASH_ATTENTION", "1")  # 1 = enabled
    OLLAMA_KV_CACHE_TYPE = os.getenv("OLLAMA_KV_CACHE_TYPE", "q8_0")  # q8_0 = half memory
    OLLAMA_MAX_LOADED_MODELS = os.getenv("OLLAMA_MAX_LOADED_MODELS", "1")
    OLLAMA_CONTEXT_LENGTH = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "1024"))

    @classmethod
    def ollama_host(cls) -> str:
        """
        Return normalized Ollama host root (scheme://host[:port]) without API suffixes.
        Accepts env values like:
        - http://ollama:11434
        - http://ollama:11434/
        - http://ollama:11434/v1
        - http://ollama:11434/api
        """
        raw = (cls.OLLAMA_HOST or "http://localhost:11434").strip().rstrip("/")
        parsed = urlparse(raw)

        # If scheme/netloc are missing (e.g. "ollama:11434"), coerce to http://
        if not parsed.scheme or not parsed.netloc:
            raw = f"http://{raw.lstrip('/')}"
            parsed = urlparse(raw)

        base = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        return base or "http://localhost:11434"

    @classmethod
    def ollama_openai_base_url(cls) -> str:
        """OpenAI-compatible Ollama endpoint (/v1)."""
        return f"{cls.ollama_host()}/v1"

    @classmethod
    def ollama_native_url(cls, path: str) -> str:
        """Native Ollama API endpoint builder (/api/*)."""
        clean_path = path if path.startswith("/") else f"/{path}"
        return f"{cls.ollama_host()}{clean_path}"

    @classmethod
    def ollama_options(cls) -> dict:
        """Returns a safe hardware-guarded options dict for all local Ollama calls."""
        return {
            "num_gpu":        cls.LOCAL_GPU,
            "num_thread":     cls.LOCAL_THREADS,
            "temperature":    cls.LOCAL_TEMP,
            "repeat_penalty": cls.LOCAL_REPEAT_PENALTY,
            "num_ctx":        cls.OLLAMA_CONTEXT_LENGTH,
            "num_predict":    cls.MAX_LOCAL_PRED,
            "keep_alive":     cls.OLLAMA_KEEP_ALIVE,
        }

    @classmethod
    def groq_available(cls) -> bool:
        """Returns True if a real Groq API key is configured."""
        key = cls.GROQ_API_KEY.strip().strip("'").strip('"')
        return bool(key) and len(key) > 10 and key != "your_free_groq_key_here"

    @classmethod
    def summary(cls) -> str:
        """Print-friendly summary of active model assignments."""
        lines = [
            "=== Strike Tips Model Config ===",
            f"  Orchestrator Tier 1:  {cls.ORCHESTRATOR} (Groq) "
            f"{'[ACTIVE]' if cls.groq_available() else '[NO KEY - add GROQ_API_KEY]'}",
            f"  Orchestrator Tier 2:  {cls.ORCHESTRATOR_T2}",
            f"  Orchestrator Tier 3:  {cls.ORCHESTRATOR_T3}",
            f"  Orchestrator Tier 4:  {cls.ORCHESTRATOR_T4}",
            f"  Orchestrator Tier 5:  {cls.ORCHESTRATOR_T5}",
            f"  Parallel Tasks:       {cls.PARALLEL}",
            f"  Cloud Fallback T6:    {cls.CLOUD_FALLBACK}",
            f"  -- LOCAL MODELS (Optimized Modelfiles) --",
            f"  Reasoner (reasoning): {cls.REASONER}",
            f"  Scraper (fast):      {cls.SCRAPER}",
            f"  Fast Local:           {cls.FAST_LOCAL}",
            f"  Tool Calling:         {cls.FUNC_CALL}",
            f"  Thinking:             {cls.THINKING}",
            f"  Embedder:             {cls.EMBEDDER}",
            f"  -- Performance --",
            f"  Local ctx/pred:       {cls.MAX_LOCAL_CTX}/{cls.MAX_LOCAL_PRED} tokens",
            f"  Local threads/GPU:    {cls.LOCAL_THREADS} threads / GPU={cls.LOCAL_GPU}",
            f"  Ollama keep_alive:     {cls.OLLAMA_KEEP_ALIVE}",
            f"  Ollama KV cache:      {cls.OLLAMA_KV_CACHE_TYPE}",
            f"  Ollama host:          {cls.ollama_host()}",
            f"  Healing Swarm Pool:   {len(cls.HEALING_POOL)} models available",
            "================================",
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    print(ModelConfig.summary())
