"""
Strike Tips - Agent Routes (Phase 3)
API endpoints for AI Agent chat, history, and memory.

NOW USING: Unified Orchestrator with Pydantic AI
- 11 schema-enabled tools
- Fallback chain (local -> cloud)
- ChromaDB stateful memory
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from core_agent.core.strike_brain import brain

# Unified Orchestrator (Phase 3)
from core_agent.agents.ai_pydantic import UnifiedOrchestrator, ModelPipeline, ModelFactory
from core_agent.tools.maf_tool_registry import get_tool_names

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Unified Orchestrator singleton (lazy initialization)
_orchestrator: Optional[UnifiedOrchestrator] = None
_pipeline: Optional[ModelPipeline] = None


def get_orchestrator() -> UnifiedOrchestrator:
    """Get or create unified orchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        if not brain or not brain.strike:
            raise RuntimeError("StrikeTips not initialized")
        _orchestrator = UnifiedOrchestrator(brain.strike)
    return _orchestrator


def get_pipeline() -> ModelPipeline:
    """Get or create model pipeline singleton."""
    global _pipeline
    if _pipeline is None:
        if not brain or not brain.strike:
            raise RuntimeError("StrikeTips not initialized")
        _pipeline = ModelPipeline(brain.strike)
    return _pipeline


class AgentRequest(BaseModel):
    """Chat request with optional model override."""

    message: str
    model: Optional[str] = (
        None  # racing_llama, racing_qwen, llama-3.3-70b-versatile, etc.
    )


@router.post("/chat", response_model=Dict[str, Any])
async def agent_chat(request: AgentRequest):
    """
    Strict API Contract: Always returns a consistent JSON structure.
    """
    try:
        # Emergency Stop Check
        if hasattr(brain, "emergency_stop") and brain.emergency_stop:
            return {
                "success": False,
                "response": "🚨 SYSTEM LOCK ACTIVE: Kill Switch has been triggered. All AI operations are halted for safety. Click 'Reset System' to resume.",
                "state": "locked"
            }

        orchestrator = get_orchestrator()
        
        # 1. Immediate Intent Check (Frontend UX optimization)
        # Allows frontend to avoid calling LLM for simple queries
        instant = await orchestrator._handle_intents(request.message, is_user_msg=True)
        if instant:
            return {
                "success": True, 
                "response": instant, 
                "state": "ready",
                "model": "intent_bypass"
            }

        # 2. Main AI Agent Call
        result = await orchestrator.chat(request.message, model_override=request.model)

        # 3. Handle potential Agent failure
        if result.confidence == 0.0:
            return {
                "success": False, 
                "response": "Model is busy or loading. Please wait 30 seconds.", 
                "state": "loading"
            }

        return {
            "success": True,
            "response": result.summary,
            "state": "ready",
            "model": result.model_used,
            "confidence": result.confidence
        }

    except Exception as e:
        logger.error(f"[API ERROR] {e}")
        return {
            "success": False,
            "response": "An internal error occurred.",
            "state": "error"
        }


@router.get("/tools")
async def list_tools():
    """List all available tools (Phase 3: 11 schema-enabled tools)."""
    try:
        tools = get_tool_names()
        return {"success": True, "tools": tools, "count": len(tools)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tools/info")
async def get_tools_info():
    """Get detailed tool information with descriptions and use cases."""
    try:
        from tools.maf_tool_registry import list_tools_with_descriptions

        tools_info = list_tools_with_descriptions()
        return {"success": True, "tools": tools_info, "count": len(tools_info)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List all available models with fallback chain."""
    try:
        from config.model_registry import get_all_models

        models = get_all_models()
        return {"success": True, "models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def orchestrator_health():
    """Check orchestrator and model health."""
    try:
        orchestrator = get_orchestrator()

        # Test Ollama connection
        import httpx

        ollama_status = "unknown"
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:11434/api/generate",
                    json={"model": "racing_llama", "prompt": "hi", "stream": False},
                    timeout=5,
                )
                ollama_status = "connected" if response.status_code == 200 else "error"
        except Exception:
            ollama_status = "not_running"

        return {
            "success": True,
            "orchestrator": "ready",
            "ollama": ollama_status,
            "models_count": len(ModelFactory.get_all()),
            "tools_count": len(get_tool_names()),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/scan")
async def run_daily_scan():
    """Run full daily scan via unified orchestrator."""
    try:
        orchestrator = get_orchestrator()

        # Run scan
        result = await orchestrator.chat("Run daily scan for all tracks")

        return {"success": True, "result": result.summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_agent_history(limit: int = 20):
    """Get the last N messages for frontend localStorage sync."""
    try:
        orchestrator = get_orchestrator()
        # Assume orchestrator has a history list or we fetch from memory
        history = brain.memory.get_chat_history(limit=limit) if brain.memory else []
        return {"success": True, "history": history, "count": len(history)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/embedding")
async def generate_embedding(text: str):
    """Generate vector embedding for semantic search."""
    try:
        # Use our existing AI provider to generate embeddings
        embedding = await brain.ai.generate_embedding(text)
        return {"success": True, "embedding": embedding}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history/clear")
async def clear_agent_history():
    """Clear chat history from orchestrator and ChromaDB."""
    try:
        orchestrator = get_orchestrator()
        orchestrator.clear_history()

        if brain and brain.memory:
            brain.memory.clear_chat_history(source="web")

        return {"success": True, "message": "Chat history cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memory/search")
async def search_memory(query: str):
    """Search memory via unified orchestrator."""
    try:
        orchestrator = get_orchestrator()
        # Use query_memory tool
        from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

        result = TOOL_REGISTRY.get("search_past_races")(query=query)
        return {"success": True, "query": query, "results": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Legacy endpoints for backwards compatibility
# =============================================================================


@router.get("/maf/tools")
async def legacy_maf_list_tools():
    """Legacy: List MAF tools (redirects to /tools)."""
    return await list_tools()


@router.get("/maf/health")
async def legacy_maf_health():
    """Legacy: MAF health check (redirects to /health)."""
    return await orchestrator_health()


# ─── Emergency Kill Switch ───────────────────────────────────────────────────

@router.post("/kill")
async def kill_switch():
    """Immediately halt all system operations."""
    brain.set_emergency_stop(True)
    return {"success": True, "message": "EMERGENCY STOP ACTIVATED", "status": "locked"}


@router.post("/reset")
async def reset_switch():
    """Resume normal system operations."""
    brain.set_emergency_stop(False)
    return {"success": True, "message": "SYSTEM RESET COMPLETE", "status": "active"}

