"""
Strike Tips - Model Registry
Complete model registry with semantic task types (Google AI Edge style).
"""

import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


# ── Semantic Task Types ────────────────────────────────────────────────────────
# LLM-oriented naming following Google AI Edge Gallery conventions.

TASK_CHAT = "llm_chat"
TASK_TOOLS = "llm_tools"  # General tool calling / function execution
TASK_RACING = "llm_racing"  # Racing domain knowledge (form, tracks, odds)
TASK_ANALYSIS = "llm_analysis"  # Deep analysis, probability edges
TASK_FAST_ANALYSIS = "llm_fast_analysis"  # Lightweight quick predictions
TASK_TRANSACTION = "llm_transaction_write"  # Record/settle bets (write ops)
TASK_EMBEDDING = "llm_embedding"  # Vector embeddings only
TASK_MULTIMODAL = "llm_multimodal"  # Image/audio input


@dataclass
class ModelInfo:
    """Model metadata with semantic task types (Google AI Edge style)."""

    id: str
    name: str
    type: str  # "cloud" or "local"
    provider: str  # Groq, Google, Ollama
    description: str  # Business description

    taskTypes: List[str]  # Semantic task types this model can handle
    bestForTaskTypes: List[str]  # Task types this model is best for
    defaultConfig: Dict  # Generation defaults: temperature, maxTokens, topK

    api_format: str = "chat"  # "chat" for /api/chat, "generate" for /api/generate
    frontend_visible: bool = True  # Show in Agent Dashboard / dropdown


# Complete Model Registry
MODEL_REGISTRY: List[ModelInfo] = [
    # ═══════════════════════════════════════════════════════════
    # LOCAL MODELS - Free, Always Available
    # ═══════════════════════════════════════════════════════════
    ModelInfo(
        id="functiongemma:270m",
        name="FunctionGemma 270M",
        type="local",
        provider="Ollama",
        description="Tool calling specialist - best for function execution.",
        taskTypes=[TASK_TOOLS, TASK_TRANSACTION],
        bestForTaskTypes=[TASK_TOOLS],
        defaultConfig={"temperature": 0.0, "maxTokens": 1024, "topK": 64},
    ),
    ModelInfo(
        id="qwen3.5:0.8b",
        name="Qwen3.5 0.8B",
        type="local",
        provider="Ollama",
        description="Fast extraction and chat - quick data retrieval.",
        taskTypes=[TASK_CHAT, TASK_TOOLS, TASK_RACING],
        bestForTaskTypes=[TASK_CHAT],
        defaultConfig={"temperature": 0.3, "maxTokens": 4096, "topK": 20},
    ),
    ModelInfo(
        id="racing_qwen:latest",
        name="Racing Qwen",
        type="local",
        provider="Ollama",
        description="Racing analysis specialist (Llama 3.2 1B base) — form analysis, racecards, general chat.",
        taskTypes=[TASK_RACING, TASK_ANALYSIS, TASK_CHAT],
        bestForTaskTypes=[TASK_RACING, TASK_ANALYSIS],
        defaultConfig={"temperature": 0.1, "maxTokens": 512, "topK": 40},
        api_format="generate",
    ),
    ModelInfo(
        id="lfm_racing:latest",
        name="LFM Racing (Thinking)",
        type="local",
        provider="Ollama",
        description="LFM 2.5 Thinking model — deep step-by-step reasoning for race evaluation and analysis.",
        taskTypes=[TASK_ANALYSIS],
        bestForTaskTypes=[TASK_ANALYSIS],
        defaultConfig={"temperature": 0.2, "maxTokens": 256, "topK": 40},
        api_format="generate",
    ),
    ModelInfo(
        id="func_gemma:latest",
        name="Func Gemma",
        type="local",
        provider="Ollama",
        description="Tool-aware specialist (FunctionGemma 270M) — transaction operations and structured data tasks.",
        taskTypes=[TASK_TRANSACTION, TASK_TOOLS],
        bestForTaskTypes=[TASK_TRANSACTION],
        defaultConfig={"temperature": 0.0, "maxTokens": 512, "topK": 64},
        api_format="generate",
        frontend_visible=False,
    ),
    ModelInfo(
        id="racing_llama:latest",
        name="Racing Llama",
        type="local",
        provider="Ollama",
        description="Search results summarizer (Llama 3.2 1B) — summarizes web search results for racing queries.",
        taskTypes=[TASK_RACING],
        bestForTaskTypes=[TASK_RACING],
        defaultConfig={"temperature": 0.1, "maxTokens": 384, "topK": 40},
        api_format="generate",
        frontend_visible=False,
    ),
    ModelInfo(
        id="ds_racing:latest",
        name="DS Racing (DeepSeek R1)",
        type="local",
        provider="Ollama",
        description="DeepSeek R1 1.5B — deep structured reasoning for complex racing analysis.",
        taskTypes=[TASK_ANALYSIS],
        bestForTaskTypes=[TASK_ANALYSIS],
        defaultConfig={"temperature": 0.3, "maxTokens": 512, "topK": 40},
        api_format="generate",
        frontend_visible=False,
    ),
    ModelInfo(
        id="embeddinggemma:300m",
        name="EmbeddingGemma 300M",
        type="local",
        provider="Ollama",
        description="Embeddings specialist - for vector search tasks.",
        taskTypes=[TASK_EMBEDDING],
        bestForTaskTypes=[TASK_EMBEDDING],
        defaultConfig={"temperature": 0.0, "maxTokens": 1},
        frontend_visible=False,
    ),
    # ═══════════════════════════════════════════════════════════
    # CLOUD MODELS - May Have Limits
    # ═══════════════════════════════════════════════════════════
    ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Groq Llama 70B",
        type="cloud",
        provider="Groq",
        description="Fast cloud model - primary cloud orchestrator.",
        taskTypes=[TASK_CHAT, TASK_TOOLS, TASK_ANALYSIS],
        bestForTaskTypes=[TASK_CHAT, TASK_ANALYSIS],
        defaultConfig={"temperature": 0.3, "maxTokens": 400, "topK": 20},
    ),
    ModelInfo(
        id="gemini-3.5-flash",
        name="Gemini 3.5 Flash",
        type="cloud",
        provider="Google",
        description="Google AI flagship - multimodal, function calling.",
        taskTypes=[TASK_CHAT, TASK_TOOLS, TASK_MULTIMODAL],
        bestForTaskTypes=[TASK_MULTIMODAL],
        defaultConfig={"temperature": 0.3, "maxTokens": 400, "topK": 64},
    ),
]


def get_all_models(frontend_only: bool = True) -> List[Dict[str, Any]]:
    """Get models (no health checks - just return all)."""
    registry = [m for m in MODEL_REGISTRY if m.frontend_visible] if frontend_only else MODEL_REGISTRY
    return [
        {
            **asdict(model),
            "is_available": True,
            "status_reason": "Ready to try",
        }
        for model in registry
    ]


def get_model_by_id(model_id: str) -> Optional[ModelInfo]:
    """Get model info by ID"""
    for model in MODEL_REGISTRY:
        if model.id == model_id:
            return model
    return None


def get_fallback_order(
    preferred: Optional[str] = None,
    prefer_local: bool = True,
    task_type: Optional[str] = None,
) -> List[str]:
    """
    Get model fallback order, optionally filtered by task type.

    Args:
        preferred: User's preferred model ID (try first)
        prefer_local: Put local models first (free, reliable)
        task_type: If set, only include models that support this task type

    Returns:
        List of model IDs in fallback order
    """
    candidates = MODEL_REGISTRY
    if task_type:
        candidates = [m for m in candidates if task_type in m.taskTypes]

    order = []

    if preferred:
        order.append(preferred)

    if prefer_local:
        for model in candidates:
            if model.type == "local" and model.id not in order:
                order.append(model.id)
        for model in candidates:
            if model.type == "cloud" and model.id not in order:
                order.append(model.id)
    else:
        for model in candidates:
            if model.type == "cloud" and model.id not in order:
                order.append(model.id)
        for model in candidates:
            if model.type == "local" and model.id not in order:
                order.append(model.id)

    return order


def get_models_by_task_type(task_type: str) -> List[ModelInfo]:
    """Filter models by semantic task type."""
    return [m for m in MODEL_REGISTRY if task_type in m.taskTypes]


def get_best_orchestrator() -> Optional[ModelInfo]:
    """Get the best general-purpose orchestrator model."""
    local = get_model_by_id("qwen3.5:0.8b")
    if local:
        return local
    return get_model_by_id("llama-3.3-70b-versatile")


def get_best_tool_model() -> Optional[ModelInfo]:
    """Get the best model for tool calling (functiongemma)."""
    return get_model_by_id("functiongemma:270m")


def get_best_racing_analysis_model() -> Optional[ModelInfo]:
    """Get the best model for deep racing analysis (racing_qwen)."""
    return get_model_by_id("racing_qwen:latest")


def get_best_fast_analysis_model() -> Optional[ModelInfo]:
    """Get the best lightweight model for quick predictions (lfm_racing)."""
    return get_model_by_id("lfm_racing:latest")


def get_embedding_model() -> Optional[ModelInfo]:
    """Get the embedding model."""
    return get_model_by_id("embeddinggemma:300m")
