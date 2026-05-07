"""
Strike Tips - Racing Routes
API endpoints for scanning tracks and gathering racing intelligence.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional
from core_agent.services.racing_service import RacingService
from core_agent.config.settings import TRACKS
from core_agent.core.strike_brain import brain
from datetime import date, timedelta

router = APIRouter(prefix="/api", tags=["racing"])
racing_service = RacingService()


@router.get("/tracks")
async def get_tracks():
    """Get all supported tracks and dynamic today's schedule"""
    try:
        active_tracks = []
        if brain.strike and brain.strike.scraper:
            active = brain.strike.scraper.get_active_tracks()
            # active is a list of track names like ['turffontein', 'vaal']
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

    # 1. Dynamically discover which tracks are actually racing today/tomorrow
    try:
        active_tracks = brain.strike.scraper.get_active_tracks()
        print(
            f"[SCAN] Found {len(active_tracks)} active tracks for {target_date}: {active_tracks}"
        )
    except Exception as e:
        print(f"[ERR] Dynamic track discovery failed: {e}")
        active_tracks = list(TRACKS.keys())  # Fallback to static config

    # 2. Iterate ONLY through discovered active tracks
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
    try:
        results = await racing_service.scan_and_analyze(track)
        return {"track": track, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/racing/intelligence")
async def get_racing_intelligence(
    track: str = "Turffontein",
    intelligence_type: str = "Computaform SA",
    date: Optional[str] = None,
):
    """Get PDF racing intelligence directly."""
    try:
        data = await racing_service.get_intelligence(track, intelligence_type, date)
        return {"success": True, "data": data}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/racing/analyze/{track}/{race_number}")
async def analyze_specific_race(track: str, race_number: int):
    """Trigger the AI Agent to evaluate a specific race for value."""
    try:
        # Ensure name consistency (backend expects lowercase usually)
        track_clean = track.lower().replace(" ", "")
        result = await brain.strike.evaluate_race(track_clean, race_number)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}
