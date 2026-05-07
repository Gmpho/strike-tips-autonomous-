"""
Race Schedule Service - Dynamic track discovery for today's races.
Fetches today's active tracks from TAB API - always includes all 7 SA tracks
plus international tracks grouped by region.
"""

import logging
from datetime import date
from typing import Dict, List, NamedTuple, Optional

logger = logging.getLogger("race-schedule")

# All 7 SA tracks always included
SA_TRACKS_ALWAYS = {
    "turffontein": {"region": "SA", "code": "XTD", "location": "Johannesburg"},
    "vaal": {"region": "SA", "code": "XVA", "location": "Vereeniging"},
    "fairview": {"region": "SA", "code": "XFA", "location": "Gqeberha"},
    "scottsville": {"region": "SA", "code": "XED", "location": "Pietermaritzburg"},
    "kenilworth": {"region": "SA", "code": "XCP", "location": "Cape Town"},
    "greyville": {"region": "SA", "code": "XGR", "location": "Durban"},
    "durbanville": {"region": "SA", "code": "XDU", "location": "Cape Town"},
}

# International tracks by region
INTERNATIONAL_TRACKS = {
    "UK": [
        "cheltenham",
        "ascot",
        "newmarket",
        "goodwood",
        "epsom",
        "york",
        "southwell",
    ],
    "Australia": ["flemington", "randwick", "caulfield", "moonee_valley", "rosehill"],
    "USA": ["churchill_downs", "santa_anita", "belmont_park", "saratoga"],
    "Ireland": ["leopardstown", "curragh", "fairyhouse"],
    "France": ["longchamp", "chantilly", "deauville"],
    "Hong Kong": ["sha_tin", "happy_valley"],
    "Japan": ["tokyo", "nakayama", "kyoto"],
}

TRACK_ALIASES = {
    "turffontein": ["turf", "turffontein racecourse"],
    "vaal": ["the vaal"],
    "fairview": ["fairview park"],
    "scottsville": ["scottsville racecourse"],
    "kenilworth": ["cape town", "kenilworth racecourse"],
    "greyville": ["greyville racecourse"],
    "durbanville": ["durbanville racecourse"],
}


class TrackResolution(NamedTuple):
    requested: str
    canonical: str
    supported: bool
    region: str


def _normalize_track_text(value: str) -> str:
    return "_".join(value.lower().strip().replace("-", " ").split())


def _build_track_alias_index() -> Dict[str, Dict[str, str]]:
    index: Dict[str, Dict[str, str]] = {}

    for track, metadata in SA_TRACKS_ALWAYS.items():
        region = metadata["region"]
        index[_normalize_track_text(track)] = {"canonical": track, "region": region}
        for alias in TRACK_ALIASES.get(track, []):
            index[_normalize_track_text(alias)] = {"canonical": track, "region": region}

    for region, tracks in INTERNATIONAL_TRACKS.items():
        for track in tracks:
            index[_normalize_track_text(track)] = {"canonical": track, "region": region}
    return index


TRACK_ALIAS_INDEX = _build_track_alias_index()
REGION_ALIASES = {
    "uk": "UK",
    "british": "UK",
    "england": "UK",
}


def resolve_track_request(text: str) -> Optional[TrackResolution]:
    """Resolve a requested track/region token and whether it is currently supported."""
    normalized_text = _normalize_track_text(text)

    for alias, region in REGION_ALIASES.items():
        if alias in normalized_text:
            return TrackResolution(
                requested=alias,
                canonical=region.lower(),
                supported=False,
                region=region,
            )

    for token in normalized_text.split("_"):
        track_meta = TRACK_ALIAS_INDEX.get(token)
        if track_meta:
            canonical = track_meta["canonical"]
            region = track_meta["region"]
            return TrackResolution(
                requested=token,
                canonical=canonical,
                supported=canonical in SA_TRACKS_ALWAYS,
                region=region,
            )

    for alias, track_meta in TRACK_ALIAS_INDEX.items():
        if alias in normalized_text:
            canonical = track_meta["canonical"]
            region = track_meta["region"]
            return TrackResolution(
                requested=alias,
                canonical=canonical,
                supported=canonical in SA_TRACKS_ALWAYS,
                region=region,
            )
    return None


def list_supported_tracks() -> List[str]:
    """Return sorted canonical SA tracks currently supported by tooling."""
    return sorted(SA_TRACKS_ALWAYS.keys())


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

        logger.info(
            f"[SCHEDULE] Today's tracks: {', '.join(tracks.keys())} ({len(tracks)} total)"
        )
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

        logger.info(
            f"[SCHEDULE] Tomorrow's tracks: {', '.join(tracks.keys())} ({len(tracks)} total)"
        )
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
