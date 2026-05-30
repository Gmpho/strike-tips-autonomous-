"""
Strike Tips - Config & Status Routes
Endpoints for system configuration, status, and reporting.
"""

import json
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, Optional
from core_agent.core.strike_brain import brain
from core_agent.config.settings import TRACKS
from core_agent.config.paths import DATA_DIR

router = APIRouter(prefix="/api", tags=["config"])

SETTINGS_FILE = str(DATA_DIR / "settings.json")


def _load_settings() -> Dict[str, Any]:
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_settings(data: Dict[str, Any]):
    os.makedirs(str(DATA_DIR), exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)


@router.get("/status")
async def get_status():
    """Get current bankroll status"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    return brain.strike.get_bankroll_status()


@router.get("/config")
async def get_config():
    """Get current system configuration merged with persisted settings"""
    from core_agent.config.settings import BANKROLL
    saved = _load_settings()
    return {
        "bankroll": {
            "total_bankroll": BANKROLL.total_bankroll,
            "max_bet_percent": BANKROLL.max_bet_percent,
            "daily_loss_limit": BANKROLL.daily_loss_limit,
            "min_edge_threshold": BANKROLL.min_edge_threshold,
            "kelly_fraction": BANKROLL.kelly_fraction,
        },
        "tracks": TRACKS,
        # Flat saved keys — returned as-is so frontend can read them directly
        **saved,
    }


@router.post("/config")
async def save_config(payload: Dict[str, Any]):
    """Persist settings to data/settings.json and sync bankroll if balance changed"""
    existing = _load_settings()
    existing.update(payload)
    _save_settings(existing)

    new_balance = payload.get("startingBalance")
    if new_balance is not None:
        import json as _json
        state_path = str(DATA_DIR / "bankroll_state.json")
        state = {}
        if os.path.exists(state_path):
            try:
                with open(state_path) as f:
                    state = _json.load(f)
            except Exception:
                pass
        # Only reset live balance if no bets have changed it yet
        if state.get("total_profit_loss", 0.0) == 0.0:
            state["current_bankroll"] = float(new_balance)
            state["peak_bankroll"] = float(new_balance)
        state["starting_balance"] = float(new_balance)
        with open(state_path, "w") as f:
            _json.dump(state, f, indent=2)
        # Update live governor instance if running
        if brain and brain.strike and brain.strike.bankroll:
            if brain.strike.bankroll.total_profit_loss == 0.0:
                brain.strike.bankroll.current_bankroll = float(new_balance)
                brain.strike.bankroll.peak_bankroll = float(new_balance)
                brain.strike.bankroll._save_state()

    return {"success": True, "saved": existing}


@router.post("/config/test_telegram")
async def test_telegram():
    """Send a test Telegram message and verify delivery"""
    if not brain.strike or not brain.strike.telegram:
        raise HTTPException(status_code=503, detail="Telegram not configured")
    ok = await brain.strike.telegram.send_message("🏇 Strike Tips — test message OK")
    if not ok:
        raise HTTPException(status_code=502, detail="Telegram delivery failed — check TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
    return {"success": True, "detail": "Test message delivered successfully"}


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
