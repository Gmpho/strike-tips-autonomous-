"""
Strike Tips - Agent Routes (Phase 3)
API endpoints for AI Agent chat, history, and memory.

NOW USING: Unified Orchestrator with Pydantic AI
- 11 schema-enabled tools
- Fallback chain (local -> cloud)
- ChromaDB stateful memory
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio
import logging
import os
import time
import uuid

import httpx
from core_agent.core.strike_brain import brain

logger = logging.getLogger("agent-routes")

# Unified Orchestrator (Phase 3)
from core_agent.agents.ai_pydantic import (
    UnifiedOrchestrator,
    ModelPipeline,
    ModelFactory,
)
from core_agent.tools.maf_tool_registry import get_tool_names

router = APIRouter(prefix="/api/agent", tags=["agent"])

# Unified Orchestrator singleton (lazy initialization)
_orchestrator: Optional[UnifiedOrchestrator] = None
_pipeline: Optional[ModelPipeline] = None
AGENT_STREAM_TIMEOUT_SEC = float(os.getenv("AGENT_STREAM_TIMEOUT_SEC", "45"))
OLLAMA_HEALTH_TIMEOUT_SEC = float(os.getenv("OLLAMA_HEALTH_TIMEOUT_SEC", "20"))
OLLAMA_HEALTH_CACHE_TTL_SEC = float(os.getenv("OLLAMA_HEALTH_CACHE_TTL_SEC", "25"))
_OLLAMA_HEALTH_CACHE: Dict[str, Any] = {
    "status": "unknown",
    "expires_at": 0.0,
}
_OLLAMA_HEALTH_LOCK = asyncio.Lock()


def _request_id(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def _loading_response(model_name: str, timeout_sec: float) -> Dict[str, Any]:
    return {
        "success": False,
        "response": (
            f"Local model '{model_name}' is warming up. " "Please retry shortly."
        ),
        "state": "loading",
        "error_type": "model_warmup_timeout",
        "model": model_name,
        "retry_after_sec": 15,
        "timeout_sec": timeout_sec,
    }


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


async def _get_cached_ollama_status() -> str:
    """Fetch Ollama health with a lightweight in-memory TTL cache."""
    now = time.monotonic()
    if now < float(_OLLAMA_HEALTH_CACHE.get("expires_at", 0.0)):
        return str(_OLLAMA_HEALTH_CACHE.get("status", "unknown"))

    async with _OLLAMA_HEALTH_LOCK:
        now = time.monotonic()
        if now < float(_OLLAMA_HEALTH_CACHE.get("expires_at", 0.0)):
            return str(_OLLAMA_HEALTH_CACHE.get("status", "unknown"))

        from core_agent.config.model_config import ModelConfig

        ollama_status = "unknown"
        try:
            ollama_tags_url = ModelConfig.ollama_native_url("/api/tags")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    ollama_tags_url, timeout=OLLAMA_HEALTH_TIMEOUT_SEC
                )
            ollama_status = "connected" if response.status_code == 200 else "error"
        except Exception:
            ollama_status = "not_running"

        _OLLAMA_HEALTH_CACHE["status"] = ollama_status
        _OLLAMA_HEALTH_CACHE["expires_at"] = (
            time.monotonic() + OLLAMA_HEALTH_CACHE_TTL_SEC
        )
        return ollama_status


class AgentRequest(BaseModel):
    """Chat request with optional model override."""

    message: str
    model: Optional[str] = None
    user_id: Optional[str] = None  # Telegram user ID for Honcho memory


def _resolve_stream_model(
    message: str, model_override: Optional[str]
) -> Dict[str, str]:
    """
    Resolve stream model via:
      explicit override -> intent -> specialist -> configured model.
    Returns model + metadata for diagnostics.
    """
    from core_agent.config.model_config import ModelConfig

    pipeline = get_pipeline()
    intent = pipeline.classifier.classify(message)
    specialist = pipeline.classifier.specialist_for(intent) if intent else "analyst"

    specialist_model_map = {
        "analyst": "groq:llama-3.1-8b-instant",
        "scanner": "groq:llama-3.1-8b-instant",
        "bankroll": "groq:llama-3.1-8b-instant",
        "search": "groq:llama-3.1-8b-instant",
    }
    routed_model = specialist_model_map.get(specialist, ModelConfig.CLOUD_FALLBACK)

    override = (model_override or "").strip()
    # Safe pass-through: only allow simple model-id characters.
    if override and all(ch.isalnum() or ch in ("-", "_", ".", ":") for ch in override):
        routed_model = override
        route_source = "override"
    else:
        route_source = "intent"

    provider = "ollama"
    if routed_model.startswith("groq:"):
        provider = "groq"
    elif routed_model.startswith("gemini:"):
        provider = "gemini"
    elif routed_model.endswith(":cloud"):
        provider = "cloud"

    return {
        "intent": intent or "unknown",
        "specialist": specialist,
        "model": routed_model,
        "provider": provider,
        "route_source": route_source,
    }


@router.post("/chat", response_model=Dict[str, Any])
async def agent_chat(request: AgentRequest, fastapi_request: Request):
    """
    Strict API Contract: Always returns a consistent JSON structure.
    """
    try:
        # Emergency Stop Check
        if hasattr(brain, "emergency_stop") and brain.emergency_stop:
            return {
                "success": False,
                "response": "🚨 SYSTEM LOCK ACTIVE: Kill Switch has been triggered. All AI operations are halted for safety. Click 'Reset System' to resume.",
                "state": "locked",
            }

        orchestrator = get_orchestrator()
        routing = _resolve_stream_model(request.message, request.model)
        started = time.monotonic()
        req_id = _request_id(fastapi_request)
        try:
            result = await asyncio.wait_for(
                orchestrator.chat(request.message, model_override=request.model, user_id=request.user_id),
                timeout=AGENT_STREAM_TIMEOUT_SEC,
            )
        except asyncio.TimeoutError:
            elapsed = round(time.monotonic() - started, 2)
            logger.warning(
                "[chat-timeout] request_id=%s model=%s elapsed_sec=%.2f timeout_sec=%.2f",
                req_id,
                routing["model"],
                elapsed,
                AGENT_STREAM_TIMEOUT_SEC,
            )
            return _loading_response(routing["model"], AGENT_STREAM_TIMEOUT_SEC)
        except (httpx.ReadTimeout, httpx.TimeoutException, httpx.TransportError):
            elapsed = round(time.monotonic() - started, 2)
            logger.warning(
                "[chat-timeout] request_id=%s model=%s elapsed_sec=%.2f timeout_sec=%.2f",
                req_id,
                routing["model"],
                elapsed,
                AGENT_STREAM_TIMEOUT_SEC,
            )
            return _loading_response(routing["model"], AGENT_STREAM_TIMEOUT_SEC)

        if result.confidence == 0.0:
            return _loading_response(
                result.model_used or routing["model"], AGENT_STREAM_TIMEOUT_SEC
            )

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
            "state": "error",
        }


@router.post("/chat/stream")
async def agent_chat_stream(request: AgentRequest, fastapi_request: Request):
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
            if any(
                kw in msg
                for kw in ("balance", "bankroll", "status", "how much", "my account")
            ):
                result = await orchestrator.chat(request.message)
                yield f"data: {_json.dumps({'token': result.summary, 'done': True, 'model': result.model_used})}\n\n"
                return

            # Stream via Ollama /api/chat stream=true with routed model selection.
            from core_agent.config.model_config import ModelConfig

            routing = _resolve_stream_model(request.message, request.model)
            final_model = routing["model"]
            final_provider = routing["provider"]
            started = time.monotonic()
            req_id = _request_id(fastapi_request)

            # --- Groq fast path ---
            if final_provider == "groq":
                import os
                groq_key = os.getenv("GROQ_API_KEY", "")
                groq_model = final_model.replace("groq:", "")
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream(
                            "POST",
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                            json={"model": groq_model, "messages": [{"role": "user", "content": request.message}], "stream": True, "max_tokens": 512},
                        ) as resp:
                            async for line in resp.aiter_lines():
                                if not line or not line.startswith("data: "):
                                    continue
                                raw = line[6:]
                                if raw.strip() == "[DONE]":
                                    yield f"data: {_json.dumps({'token': '', 'done': True, 'model': groq_model, 'provider': 'groq'})}\n\n"
                                    break
                                try:
                                    chunk = _json.loads(raw)
                                    token = chunk["choices"][0]["delta"].get("content", "")
                                    if token:
                                        yield f"data: {_json.dumps({'token': token, 'done': False})}\n\n"
                                except Exception:
                                    continue
                except Exception as e:
                    yield f"data: {_json.dumps({'token': f'Groq error: {str(e)[:80]}', 'done': True})}\n\n"
                return

            chat_url = ModelConfig.ollama_native_url("/api/chat")
            payload = {
                "model": routing["model"],
                "messages": [{"role": "user", "content": request.message}],
                "stream": True,
                "think": False,
                "options": {"num_predict": 256, "temperature": 0.1},
            }

            try:
                async with httpx.AsyncClient(
                    timeout=AGENT_STREAM_TIMEOUT_SEC
                ) as client:
                    async with client.stream("POST", chat_url, json=payload) as resp:
                        logger.debug(
                            "[stream] opened ollama stream url=%s status=%s model=%s intent=%s specialist=%s",
                            chat_url,
                            resp.status_code,
                            routing["model"],
                            routing["intent"],
                            routing["specialist"],
                        )
                        if resp.status_code < 200 or resp.status_code >= 300:
                            err_text = (await resp.aread()).decode(
                                "utf-8", errors="ignore"
                            )[:180]
                            logger.debug(
                                "[stream] ollama non-2xx status=%s body=%s",
                                resp.status_code,
                                err_text,
                            )
                            yield f"data: {_json.dumps({'token': f'Ollama error ({resp.status_code}): {err_text}', 'done': True, 'model': final_model, 'provider': final_provider, 'intent': routing['intent'], 'specialist': routing['specialist'], 'route_source': routing['route_source']})}\n\n"
                            return

                        async for line in resp.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk = _json.loads(line)
                                final_model = chunk.get("model") or final_model
                                token = chunk.get("message", {}).get("content", "")
                                done = chunk.get("done", False)
                                if token:
                                    yield f"data: {_json.dumps({'token': token, 'done': done})}\n\n"
                                if done:
                                    yield f"data: {_json.dumps({'token': '', 'done': True, 'model': final_model, 'provider': final_provider, 'intent': routing['intent'], 'specialist': routing['specialist'], 'route_source': routing['route_source']})}\n\n"
                                    break
                            except Exception:
                                continue
                        logger.debug(
                            "[stream] closed ollama stream url=%s model=%s provider=%s",
                            chat_url,
                            final_model,
                            final_provider,
                        )
            except (httpx.ReadTimeout, httpx.TimeoutException, httpx.TransportError):
                elapsed = round(time.monotonic() - started, 2)
                logger.warning(
                    "[stream-timeout] request_id=%s model=%s elapsed_sec=%.2f timeout_sec=%.2f",
                    req_id,
                    final_model,
                    elapsed,
                    AGENT_STREAM_TIMEOUT_SEC,
                )
                yield (
                    "data: "
                    + _json.dumps(
                        {
                            "token": "",
                            "done": True,
                            "state": "loading",
                            "error_type": "model_warmup_timeout",
                            "model": final_model,
                            "provider": final_provider,
                            "retry_after_sec": 15,
                            "timeout_sec": AGENT_STREAM_TIMEOUT_SEC,
                        }
                    )
                    + "\n\n"
                )
                return
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
        get_orchestrator()
        ollama_status = await _get_cached_ollama_status()

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


@router.get("/memory")
async def get_memory(query: str = "betting preferences, favourite tracks, risk tolerance", user_id: Optional[str] = None):
    """Query Honcho for synthesised insights about a user."""
    try:
        from core_agent.skills.memory.honcho_memory import HonchoMemory, dream_honcho
        mem = HonchoMemory(user_id=user_id)
        user_context = mem.get_context(query)
        dream_context = dream_honcho.get_dream_context()
        return {
            "success": True,
            "user_id": user_id or "anon_web",
            "context": user_context,
            "dream_context": dream_context,
            "status": "active" if user_context else "no_data_yet",
        }
    except Exception as e:
        return {"success": False, "error": str(e), "context": "", "dream_context": ""}


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
