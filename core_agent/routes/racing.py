"""
Strike Tips - Racing Routes
API endpoints for scanning tracks and gathering racing intelligence.
"""

import os
from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
import logging
from core_agent.services.racing_service import RacingService
from core_agent.config.settings import TRACKS
from core_agent.config.paths import DATA_DIR, ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH
from core_agent.core.strike_brain import brain
from datetime import date, timedelta
import json

logger = logging.getLogger("racing-routes")

router = APIRouter(prefix="/api", tags=["racing"])
racing_service = RacingService()

ALLOWED_TRACKS = {
    "turffontein", "vaal", "fairview", "scottsville", "kenilworth",
    "durbanville", "greyville", "flamingo", "flamingopark", "scottburgh"
}


def _validate_track(track: str) -> str:
    clean = track.lower().replace(" ", "").replace("/", "").replace("..", "")
    if clean not in ALLOWED_TRACKS:
        raise HTTPException(status_code=400, detail=f"Unknown track: {track}")
    return clean


@router.get("/tracks")
async def get_tracks():
    """Get all supported tracks and dynamic today's schedule"""
    try:
        active_tracks = []
        if brain.strike and brain.strike.scraper:
            active = brain.strike.scraper.get_active_tracks()
            active_tracks = [t.lower() for t in active]
        else:
            active_tracks = ["turffontein"]
        return {"tracks": TRACKS, "today_tracks": active_tracks}
    except Exception as e:
        print(f"[WARN] Dynamic track discovery failed: {e}")
        return {"tracks": TRACKS, "today_tracks": ["turffontein"]}


from datetime import date, timedelta, datetime
import pytz


@router.get("/scan_all")
async def scan_all(days_ahead: int = 0):
    """Scan all tracks with local SAST date."""
    sa_tz = pytz.timezone("Africa/Johannesburg")
    today_local = datetime.now(sa_tz).date()
    target_date = (today_local + timedelta(days=days_ahead)).isoformat()
    results = {}

    try:
        active_tracks = brain.strike.scraper.get_active_tracks()
        print(
            f"[SCAN] Found {len(active_tracks)} active tracks for {target_date}: {active_tracks}"
        )
    except Exception as e:
        print(f"[ERR] Dynamic track discovery failed: {e}")
        active_tracks = list(TRACKS.keys())

    for track in active_tracks:
        try:
            results[track] = await racing_service.scan_and_analyze(
                track, date_str=target_date
            )
        except Exception as e:
            print(f"Error scanning {track}: {e}")
            results[track] = []

    return {"date": target_date, "results": results}


@router.get("/scan/{track}")
async def scan_track(track: str):
    """Scan a specific track and analyze races."""
    track_clean = _validate_track(track)
    try:
        results = await racing_service.scan_and_analyze(track_clean)
        return {"track": track_clean, "results": results}
    except Exception as e:
        logger.error(f"Failed to scan track {track_clean}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to scan track: {e}")


@router.get("/racing/intelligence")
async def get_racing_intelligence(
    track: str = "Turffontein",
    intelligence_type: str = "Computaform SA",
    date: Optional[str] = None,
):
    """Get PDF racing intelligence directly."""
    track_clean = _validate_track(track)
    try:
        data = await racing_service.get_intelligence(track_clean, intelligence_type, date)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": "Failed to retrieve intelligence"}


@router.get("/racing/analyze/{track}/{race_number}")
async def analyze_specific_race(track: str, race_number: int):
    """Trigger the AI Agent to evaluate a specific race for value."""
    track_clean = _validate_track(track)
    try:
        result = await brain.strike.evaluate_race(track_clean, race_number)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": "Failed to analyze race"}


@router.get("/racing/market-movers")
async def get_market_movers():
    """Return latest market movers from ATR disk snapshot."""
    p = ATR_MOVERS_PATH
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("movers", [])
    return []


@router.get("/racing/predictor")
async def get_predictor():
    """Return latest AI predictions from ATR disk snapshot."""
    p = ATR_PREDICTOR_PATH
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("predictions", [])
    return []


@router.get("/racing/results")
async def get_results():
    """Return latest race results from ATR disk snapshot."""
    p = ATR_RESULTS_PATH
    if p.exists():
        data = json.loads(p.read_text())
        return data.get("results", [])
    return []


@router.get("/racing/exotics")
async def get_latest_exotics():
    """Return latest computed exotic plays from exotics_latest.json."""
    path = str(DATA_DIR / "exotics_latest.json")
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return []
