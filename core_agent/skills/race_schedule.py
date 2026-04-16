"""
Race Schedule Service - Dynamic track discovery for today's races.
Fetches today's active tracks from TAB API - always includes all 7 SA tracks
plus international tracks grouped by region.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

logger = logging.getLogger("race-schedule")

# All 7 SA tracks always included
SA_TRACKS_ALWAYS = {
    "turffontein": {"region": "SA", "code": "XTD", "location": "Johannesburg"},
    "vaal":        {"region": "SA", "code": "XVA", "location": "Vereeniging"},
    "fairview":    {"region": "SA", "code": "XFA", "location": "Gqeberha"},
    "scottsville": {"region": "SA", "code": "XED", "location": "Pietermaritzburg"},
    "kenilworth":  {"region": "SA", "code": "XCP", "location": "Cape Town"},
    "greyville":   {"region": "SA", "code": "XGR", "location": "Durban"},
    "durbanville": {"region": "SA", "code": "XDU", "location": "Cape Town"},
}

# International tracks by region
INTERNATIONAL_TRACKS = {
    "UK": ["cheltenham", "ascot", "newmarket", "goodwood", "epsom", "york"],
    "Australia": ["flemington", "randwick", "caulfield", "moonee_valley", "rosehill"],
    "USA": ["churchill_downs", "santa_anita", "belmont_park", "saratoga"],
    "Ireland": ["leopardstown", "curragh", "fairyhouse"],
    "France": ["longchamp", "chantilly", "deauville"],
    "Hong Kong": ["sha_tin", "happy_valley"],
    "Japan": ["tokyo", "nakayama", "kyoto"],
}


class RaceScheduleService:
    """
    Dynamically fetches today's racing schedule from TAB API.
    Always returns all 7 SA tracks + any live international tracks.
    """

    TAB_SCHEDULE_URL = "https://www.tab.co.za/api/racing/schedule?date={date}"

    def __init__(self):
        self._today_cache: Optional[Dict] = None
        self._cache_date: Optional[str] = None

    async def get_todays_tracks(self) -> Dict[str, Dict]:
        """
        Return all tracks racing today.
        SA tracks always included; international tracks fetched from API.
        """
        today = date.today().isoformat()

        # Use cache if same day
        if self._cache_date == today and self._today_cache is not None:
            return self._today_cache

        tracks = dict(SA_TRACKS_ALWAYS)  # Always include all SA tracks

        # Try to fetch international tracks
        international = await self._fetch_international_schedule(today)
        tracks.update(international)

        self._today_cache = tracks
        self._cache_date = today

        logger.info(f"[SCHEDULE] Today's tracks: {', '.join(tracks.keys())} ({len(tracks)} total)")
        return tracks

    async def get_tomorrows_tracks(self) -> Dict[str, Dict]:
        """
        Fetch racing schedules for tomorrow.
        """
        from datetime import timedelta
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        
        tracks = dict(SA_TRACKS_ALWAYS)
        international = await self._fetch_international_schedule(tomorrow)
        tracks.update(international)
        
        logger.info(f"[SCHEDULE] Tomorrow's tracks: {', '.join(tracks.keys())} ({len(tracks)} total)")
        return tracks

    async def _fetch_international_schedule(self, date_str: str) -> Dict[str, Dict]:
        """Fetch live international racing schedule from TAB API"""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                url = self.TAB_SCHEDULE_URL.format(date=date_str.replace("-", ""))
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    return self._parse_schedule_response(data)
        except Exception as e:
            logger.debug(f"International schedule fetch failed: {e}")

        # Fallback: return empty (SA tracks still included)
        return {}

    def _parse_schedule_response(self, data: dict) -> Dict[str, Dict]:
        """Parse TAB API schedule response into track dict"""
        tracks = {}
        for meeting in data.get("meetings", []):
            venue = meeting.get("venue", "").lower().replace(" ", "_")
            country = meeting.get("country", "International")
            if venue and country != "South Africa":
                tracks[venue] = {
                    "region": country,
                    "code": meeting.get("code", venue[:3].upper()),
                    "location": meeting.get("location", country),
                }
        return tracks

    def get_sa_tracks(self) -> List[str]:
        """Return list of SA track names"""
        return list(SA_TRACKS_ALWAYS.keys())

    def get_tracks_by_region(self, region: str) -> List[str]:
        """Return international track names for a region"""
        return INTERNATIONAL_TRACKS.get(region, [])
