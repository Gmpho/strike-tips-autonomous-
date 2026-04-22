"""
Strike Tips - Model Registry
Complete model registry with capabilities for business logic.
"""
import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from dotenv import load_dotenv

load_dotenv()

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")


@dataclass
class ModelInfo:
    """Model metadata with full capabilities"""
    id: str
    name: str
    type: str  # "cloud" or "local"
    provider: str  # Groq, Google, Ollama
    description: str  # Business description
    
    # Capabilities
    supports_tools: bool  # Can use get_bankroll, search_racecard, etc.
    is_orchestrator: bool  # Primary orchestration model
    is_reasoning: bool  # Does thinking/reasoning
    is_fast: bool  # Fast response
    is_free: bool  # Always free (local models)
    rate_limit_risk: str  # "none", "low", "medium", "high"


# Complete Model Registry with ALL 10 Models
MODEL_REGISTRY: List[ModelInfo] = [
    # ═══════════════════════════════════════════════════════════
    # LOCAL MODELS - Free, Always Available
    # ═══════════════════════════════════════════════════════════
    
    ModelInfo(
        id="racing_llama",
        name="Racing Llama",
        type="local",
        provider="Ollama",
        description="Best local model - tool capable, reliable. RECOMMENDED for daily use.",
        supports_tools=True,
        is_orchestrator=True,
        is_reasoning=False,
        is_fast=True,
        is_free=True,
        rate_limit_risk="none"
    ),
    ModelInfo(
        id="racing_qwen",
        name="Racing Qwen",
        type="local",
        provider="Ollama",
        description="Fast local extraction - quick data retrieval, lightweight tasks.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=False,
        is_fast=True,
        is_free=True,
        rate_limit_risk="none"
    ),
    ModelInfo(
        id="func_gemma",
        name="FuncGemma",
        type="local",
        provider="Ollama",
        description="Tool calling specialist - best for function execution, structured output.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=False,
        is_fast=True,
        is_free=True,
        rate_limit_risk="none"
    ),
    ModelInfo(
        id="lfm_racing",
        name="LFM Racing",
        type="local",
        provider="Ollama",
        description="Large FM thinking model - complex reasoning, analysis tasks.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=True,
        is_fast=False,
        is_free=True,
        rate_limit_risk="none"
    ),
    ModelInfo(
        id="ds_racing",
        name="DeepSeek Racing",
        type="local",
        provider="Ollama",
        description="Reasoning model - no thinking output, simple Q&A. NO TOOL SUPPORT.",
        supports_tools=False,
        is_orchestrator=False,
        is_reasoning=True,
        is_fast=True,
        is_free=True,
        rate_limit_risk="none"
    ),
    
    # ═══════════════════════════════════════════════════════════
    # CLOUD MODELS - May Have Limits
    # ═══════════════════════════════════════════════════════════
    
    ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Groq Llama 70B",
        type="cloud",
        provider="Groq",
        description="Fastest cloud model - free 14,400 req/day. Primary cloud orchestrator.",
        supports_tools=True,
        is_orchestrator=True,
        is_reasoning=False,
        is_fast=True,
        is_free=False,
        rate_limit_risk="medium"
    ),
    ModelInfo(
        id="gemini-3-flash-preview",
        name="Gemini 3 Flash",
        type="cloud",
        provider="Google",
        description="Google AI flagship - free quota, balanced performance.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=False,
        is_fast=True,
        is_free=False,
        rate_limit_risk="medium"  # quota based
    ),
    ModelInfo(
        id="gemini-2.0-flash-lite",
        name="Gemini 2.0 Flash Lite",
        type="cloud",
        provider="Google",
        description="Google lightweight - fastest, lowest cost, good for simple tasks.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=False,
        is_fast=True,
        is_free=False,
        rate_limit_risk="low"
    ),
    ModelInfo(
        id="gemini-3-flash-preview:cloud",
        name="Gemini Cloud",
        type="cloud",
        provider="Ollama Cloud",
        description="Ollama cloud hosting - rate limited, use when others fail.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=False,
        is_fast=False,
        is_free=False,
        rate_limit_risk="high"
    ),
    ModelInfo(
        id="kimi-k2-thinking:cloud",
        name="Kimi Thinking Cloud",
        type="cloud",
        provider="Ollama Cloud",
        description="Kimi AI thinking model - complex reasoning, rate limited.",
        supports_tools=True,
        is_orchestrator=False,
        is_reasoning=True,
        is_fast=False,
        is_free=False,
        rate_limit_risk="high"
    ),
]


def get_all_models() -> List[Dict[str, Any]]:
    """Get ALL models (no health checks - just return all)"""
    return [
        {
            **asdict(model),
            "is_available": True,  # Assume available, let user try
            "status_reason": "Ready to try"
        }
        for model in MODEL_REGISTRY
    ]


def get_model_by_id(model_id: str) -> Optional[ModelInfo]:
    """Get model info by ID"""
    for model in MODEL_REGISTRY:
        if model.id == model_id:
            return model
    return None


def get_fallback_order(
    preferred: Optional[str] = None,
    prefer_local: bool = True
) -> List[str]:
    """
    Get model fallback order.
    
    Args:
        preferred: User's preferred model ID (try first)
        prefer_local: Put local models first (free, reliable)
    
    Returns:
        List of model IDs in fallback order
    """
    order = []
    
    # Add preferred first
    if preferred:
        order.append(preferred)
    
    if prefer_local:
        # Local models first (free, always work)
        for model in MODEL_REGISTRY:
            if model.type == "local" and model.id not in order:
                order.append(model.id)
        # Then cloud models
        for model in MODEL_REGISTRY:
            if model.type == "cloud" and model.id not in order:
                order.append(model.id)
    else:
        # Cloud first then local
        for model in MODEL_REGISTRY:
            if model.type == "cloud" and model.id not in order:
                order.append(model.id)
        for model in MODEL_REGISTRY:
            if model.type == "local" and model.id not in order:
                order.append(model.id)
    
    return order


def get_models_by_capability(
    has_tools: Optional[bool] = None,
    is_orchestrator: Optional[bool] = None,
    is_reasoning: Optional[bool] = None,
    is_free: Optional[bool] = None
) -> List[ModelInfo]:
    """Filter models by capability"""
    results = []
    for model in MODEL_REGISTRY:
        if has_tools is not None and model.supports_tools != has_tools:
            continue
        if is_orchestrator is not None and model.is_orchestrator != is_orchestrator:
            continue
        if is_reasoning is not None and model.is_reasoning != is_reasoning:
            continue
        if is_free is not None and model.is_free != is_free:
            continue
        results.append(model)
    return results


# Convenience functions for business logic
def get_best_local_model() -> Optional[ModelInfo]:
    """Get the best local model for tool calling"""
    return get_model_by_id("racing_llama")


def get_best_orchestrator() -> Optional[ModelInfo]:
    """Get the best orchestrator model"""
    # Prefer local if available
    local = get_model_by_id("racing_llama")
    if local:
        return local
    return get_model_by_id("llama-3.3-70b-versatile")


def get_free_models() -> List[ModelInfo]:
    """Get all free (local) models"""
    return get_models_by_capability(is_free=True)


def get_tool_models() -> List[ModelInfo]:
    """Get all models that support tools"""
    return get_models_by_capability(has_tools=True)
