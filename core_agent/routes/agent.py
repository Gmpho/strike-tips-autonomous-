from __future__ import annotations
from fastapi import APIRouter, HTTPException, Request
from typing import Optional, List, Dict, Any
import logging

from core_agent.core.strike_brain import brain

logger = logging.getLogger("agent-routes")

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.get("/tools")
async def list_tools():
    from core_agent.tools.maf_tool_registry import get_tool_names
    tools = get_tool_names()
    return {"success": True, "tools": tools, "count": len(tools)}


@router.get("/models")
async def list_models():
    from core_agent.config.model_registry import get_all_models
    models = get_all_models()
    return {"success": True, "models": models, "count": len(models)}


@router.get("/history")
async def get_agent_history(limit: int = 20):
    return {"success": True, "history": [], "count": 0}


@router.post("/embedding")
async def generate_embedding(text: str):
    if not brain.memory:
        raise HTTPException(503, "Memory not initialized")
    embedding = brain.memory.generate_embedding(text)
    return {"success": True, "embedding": embedding}


@router.post("/history/clear")
async def clear_agent_history():
    if brain and brain.memory:
        brain.memory.clear_chat_history(source="web")
    return {"success": True, "message": "Chat history cleared"}


@router.get("/memory/search")
async def search_memory(query: str):
    from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
    result = TOOL_REGISTRY.get("search_past_races")(query=query)
    return {"success": True, "query": query, "results": result}


@router.get("/memory")
async def get_memory(query: str = "betting preferences, favourite tracks, risk tolerance", user_id: Optional[str] = None):
    from core_agent.skills.memory.honcho_memory import HonchoMemory, dream_honcho
    mem = HonchoMemory(user_id=user_id)
    user_context = mem.get_context(query)
    dream_context = dream_honcho.get_dream_context()
    return {
        "success": True,
        "user_id": user_id or "anon_web",
        "context": user_context,
        "dream_context": dream_context,
    }


@router.post("/kill")
async def kill_switch():
    brain.set_emergency_stop(True)
    return {"success": True, "message": "EMERGENCY STOP ACTIVATED", "status": "locked"}


@router.post("/reset")
async def reset_switch():
    brain.set_emergency_stop(False)
    return {"success": True, "message": "SYSTEM RESET COMPLETE", "status": "active"}
