from fastapi import APIRouter
from core_agent.skills.dreamer import dream_engine
from typing import List, Dict

router = APIRouter(prefix="/api/dreaming", tags=["dreaming"])


@router.get("/logs")
async def get_dream_logs():
    """Get the most recent AI dreams. Auto-generates 3 on first call if empty."""
    if not dream_engine.history:
        for _ in range(3):
            await dream_engine.generate_dream()
    return dream_engine.get_recent_dreams()


@router.post("/pulse")
async def trigger_dream():
    """Trigger a new AI dream using live race data + Groq. Saves to ChromaDB."""
    dream = await dream_engine.generate_dream()

    # Save to ChromaDB
    try:
        from core_agent.skills.memory.chroma_memory import RacingMemory
        memory = RacingMemory()
        if memory._is_ready:
            memory.add_form_insight(
                horse=f"dream_{dream.track}",
                insight=f"{dream.scenario} → {dream.insight}",
                metadata={"type": "dream", "track": dream.track, "ts": dream.timestamp},
            )
    except Exception:
        pass

    return {"status": "success", "dream": dream}


from pydantic import BaseModel

class CustomDreamRequest(BaseModel):
    track: str
    race_number: int
    scenario: str


@router.post("/custom")
async def trigger_custom_dream(req: CustomDreamRequest):
    """Trigger a custom AI dream scenario for a specific track/race"""
    dream = await dream_engine.generate_custom_dream(req.track, req.race_number, req.scenario)

    # Save to ChromaDB
    try:
        from core_agent.skills.memory.chroma_memory import RacingMemory
        memory = RacingMemory()
        if memory._is_ready:
            memory.add_form_insight(
                horse=f"dream_{dream.track}",
                insight=f"{dream.scenario} → {dream.insight}",
                metadata={"type": "dream", "track": dream.track, "ts": dream.timestamp},
            )
    except Exception:
        pass

    return {"status": "success", "dream": dream}
