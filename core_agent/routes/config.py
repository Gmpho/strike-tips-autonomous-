"""
Strike Tips - Config & Status Routes
Endpoints for system configuration, status, and reporting.
"""

from fastapi import APIRouter, HTTPException
from core_agent.core.strike_brain import brain
from core_agent.config.settings import TRACKS

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/status")
async def get_status():
    """Get current bankroll status"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    return brain.strike.get_bankroll_status()


@router.get("/config")
async def get_config():
    """Get current system configuration"""
    from core_agent.config.settings import BANKROLL

    return {
        "bankroll": {
            "total_bankroll": BANKROLL.total_bankroll,
            "max_bet_percent": BANKROLL.max_bet_percent,
            "daily_loss_limit": BANKROLL.daily_loss_limit,
            "min_edge_threshold": BANKROLL.min_edge_threshold,
            "kelly_fraction": BANKROLL.kelly_fraction,
        },
        "tracks": TRACKS,
    }


@router.get("/report")
async def get_report():
    """Get daily betting report"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    return {"report": brain.strike.generate_report()}


@router.get("/models")
async def get_models():
    """Get available AI models"""
    from core_agent.config.model_registry import get_all_models

    models = get_all_models()
    return {"models": models, "count": len(models)}
