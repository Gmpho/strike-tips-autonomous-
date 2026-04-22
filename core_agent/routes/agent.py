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
import logging
from core_agent.core.strike_brain import brain

logger = logging.getLogger("agent-routes")

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
        result = await orchestrator.chat(request.message, model_override=request.model)

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
            "confidence": result.confidence,
            "token_usage": result.token_usage,
        }

    except Exception as e:
        logger.error(f"[API ERROR] {e}")
        return {
            "success": False,
            "response": "An internal error occurred.",
            "state": "error"
        }


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentRequest):
    """Streaming chat — sends tokens as SSE as soon as they arrive."""
    from fastapi.responses import StreamingResponse
    import json as _json

    async def event_stream():
        try:
            if hasattr(brain, "emergency_stop") and brain.emergency_stop:
                yield f"data: {_json.dumps({'token': '🚨 System locked.', 'done': True})}\n\n"
                return

            orchestrator = get_orchestrator()
            # Fast instant-intent path — no LLM needed
            msg = request.message.lower().strip()
            if any(kw in msg for kw in ("balance", "bankroll", "status", "how much", "my account")):
                result = await orchestrator.chat(request.message)
                yield f"data: {_json.dumps({'token': result.summary, 'done': True, 'model': result.model_used})}\n\n"
                return

            # Stream via Ollama /api/chat stream=true
            import httpx
            from core_agent.config.model_config import ModelConfig
            host = ModelConfig.OLLAMA_HOST or "http://ollama:11434"
            payload = {
                "model": "racing_qwen",
                "messages": [{"role": "user", "content": request.message}],
                "stream": True,
                "think": False,
                "options": {"num_predict": 256, "temperature": 0.1},
            }
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", f"{host}/api/chat", json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if not line:
                            continue
                        try:
                            chunk = _json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            done = chunk.get("done", False)
                            if token:
                                yield f"data: {_json.dumps({'token': token, 'done': done})}\n\n"
                            if done:
                                yield f"data: {_json.dumps({'token': '', 'done': True, 'model': 'racing_qwen'})}\n\n"
                                break
                        except Exception:
                            continue
        except Exception as e:
            yield f"data: {_json.dumps({'token': f'Error: {str(e)[:60]}', 'done': True})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
        from core_agent.tools.maf_tool_registry import list_tools_with_descriptions

        tools_info = list_tools_with_descriptions()
        return {"success": True, "tools": tools_info, "count": len(tools_info)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/models")
async def list_models():
    """List all available models with fallback chain."""
    try:
        from core_agent.config.model_registry import get_all_models
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
            from core_agent.config.model_config import ModelConfig
            ollama_host = ModelConfig.OLLAMA_HOST or "http://localhost:11434"
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{ollama_host}/api/tags", timeout=5)
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
        if not brain.memory:
            raise HTTPException(status_code=503, detail="Memory not initialized")
        embedding = brain.memory.generate_embedding(text)
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

