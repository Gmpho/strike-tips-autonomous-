from fastapi import APIRouter
from core_agent.skills.dreamer import dream_engine
from typing import List, Dict

router = APIRouter(prefix="/api/dreaming", tags=["dreaming"])


@router.get("/logs")
async def get_dream_logs():
    """Get the most recent AI dreams/simulations."""
    return dream_engine.get_recent_dreams()


@router.post("/pulse")
async def trigger_dream():
    """Manually trigger a new neural dream simulation."""
    dream = dream_engine.generate_dream()
    return {"status": "success", "dream": dream}
