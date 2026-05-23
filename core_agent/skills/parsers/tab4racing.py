"""
TAB4Racing Scraper - South African Horse Racing Data Ingestion
Scrapes race cards from tab.co.za with retry logic and self-healing fallbacks.
Now with real-time odds injection from market snapshots.
"""

import asyncio
import logging
import os
import re
import json
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict

logger = logging.getLogger("tab4racing-scraper")

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

try:
    import httpx
    from bs4 import BeautifulSoup

    HAS_SCRAPER_DEPS = True
except ImportError:
    HAS_SCRAPER_DEPS = False
    logger.warning("httpx/bs4 not installed - scraper in stub mode")


@dataclass
class ScrapedRunner:
    """A single horse scraped from a race card"""

    horse_name: str
    odds_decimal: float
    odds_fractional: Optional[str] = None
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    barrier: Optional[int] = None
    weight: Optional[float] = None
    form: Optional[str] = None
    age: Optional[int] = None
    sex: Optional[str] = None


@dataclass
class ScrapedRace:
    """A scraped race - all runners in one race at one track"""

    track: str
    race_number: int
    race_time: str
    distance: int  # metres, default 1600 if not found
    track_condition: str  # Good, Soft, Heavy
    runners: List[ScrapedRunner] = field(default_factory=list)
    race_class: Optional[str] = None
    prize_money: Optional[float] = None


def get_live_odds(
    track: str, horse_name: str, snapshot: Optional[Dict] = None
) -> float:
    """Lookup live odds from market_snapshot_latest.json or provided snapshot."""
    try:
        if snapshot is None:
            from core_agent.core.snapshot_cache import get_snapshot
            snapshot = get_snapshot()
            if not snapshot.get("events"):
                return 5.0

        # Flatten events to find the horse
        for event_id, event in snapshot.get("events", {}).items():
            # Fuzzy match track name (e.g. "Fairview" in "Fairview South Africa")
            if track.lower() in event.get("en", "").lower():
                for runner in event.get("runners", []):
                    if runner["name"].lower() == horse_name.lower():
                        try:
                            return float(runner["odds"])
                        except (ValueError, KeyError):
                            return 5.0
    except Exception as e:
        logger.debug(f"Odds lookup failed for {horse_name}: {e}")
        return 5.0
    return 5.0


class TAB4RacingScraper:
    """
    Scrapes SA race cards from tab.co.za.
    Uses httpx async client with a 30-second timeout and up to 3 retries.

    SA Track Codes:
      XTD = Turffontein, XVA = Vaal, XFA = Fairview,
      XED = Scottsville, XCP = Kenilworth, XGR = Greyville, XDU = Durbanville
    """

    SA_TRACKS = {
        "turffontein": {
            "code": "XTD",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XTD",
        },
        "vaal": {
            "code": "XVA",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XVA",
        },
        "fairview": {
            "code": "XFA",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XFA",
        },
        "scottsville": {
            "code": "XED",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XED",
        },
        "kenilworth": {
            "code": "XCP",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XCP",
        },
        "greyville": {
            "code": "XGR",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XGR",
        },
        "durbanville": {
            "code": "XDU",
            "url": "https://www.tab.co.za/tabs/horse/all/{date}/XDU",
        },
    }

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-ZA,en;q=0.9",
    }

    def __init__(self, timeout: int = 30, retries: int = 3):
        self.timeout = timeout
        self.retries = retries
        self._client: Optional["httpx.AsyncClient"] = None

    async def _get_client(self) -> "httpx.AsyncClient":
        if self._client is None or self._client.is_closed:
            import httpx

            self._client = httpx.AsyncClient(
                headers=self.HEADERS,
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client

    def get_active_tracks(self) -> List[str]:
        """Return list of active SA track names"""
        return list(self.SA_TRACKS.keys())

    async def scrape_racecard(
        self, track: str, date_str: Optional[str] = None
    ) -> List[ScrapedRace]:
        """Main entry point for scraping - uses API for speed, HTML as fallback."""
        from core_agent.skills.parsers.pdf_harvester import PDFHarvester
        from core_agent.skills.parsers.tab_pdf_mapper import _map_pdf_to_races

        target_date = date_str or date.today().isoformat()
        program_code = self.SA_TRACKS.get(track.lower(), {}).get("code")

        # 1. Try Live API First
        if program_code:
            races = await self._fetch_live_api_races(program_code, track)
            if races:
                logger.info(
                    f"[API] Successfully fetched {len(races)} races for {track}"
                )
                return races

        # 2. Try HTML Scrape if API failed
        url = (
            self.SA_TRACKS.get(track.lower(), {})
            .get("url", "")
            .format(date=target_date)
        )
        if url:
            try:
                client = await self._get_client()
                resp = await client.get(url)
                if resp.status_code == 200:
                    races = self._parse_response(track, resp.text)
                    if races:
                        return races
            except Exception as e:
                logger.warning(f"HTML fallback failed for {track}: {e}")

        # 3. Last Resort: PDF Harvester
        logger.info(f"[API] No runners for {track}, falling back to PDF harvester")
        harvester = PDFHarvester()
        intelligence = await harvester.get_latest_racing_intelligence(
            track=track, intelligence_type="Computaform SA", specific_date=target_date
        )

        if intelligence.get("parsed_tips"):
            logger.info(f"[PDF] Successfully extracted data for {track}")
            return _map_pdf_to_races(intelligence, track)

        logger.warning(f"[ALL] No data found for {track}")
        return []

    async def _fetch_live_api_races(
        self, program_code: str, track_name: str
    ) -> List[ScrapedRace]:
        """Helper to fetch from the 4RACINGWEB_TAB API."""
        url = "https://totex-vasx.4racing.com/PRODUCTS/webservice/phumelelaV4/get/GamePlayRequest/horseracing/4RACINGWEB_TAB"
        params = {"msisdn": "0000", "game": "horseracing", "selectionType": "0"}

        try:
            client = await self._get_client()
            response = await client.get(url, params=params)
            if response.status_code != 200:
                return []

            data = response.json()
            programs = data.get("data", {}).get("option_list", {})

            # Pre-load snapshot once for all runners from in-memory cache
            from core_agent.core.snapshot_cache import get_snapshot
            snapshot = get_snapshot()

            for k, v in programs.items():
                if v.get("ProgramCode") == program_code:
                    race_list = v.get("RaceList", [])
                    if not race_list:
                        continue

                    races = []
                    for r in race_list:
                        # Extract and inject live odds
                        runners = []
                        for name in r.get("LiveRunners", "").split(","):
                            if not name:
                                continue
                            name = name.strip()
                            runners.append(
                                ScrapedRunner(
                                    horse_name=name,
                                    odds_decimal=get_live_odds(
                                        track_name, name, snapshot=snapshot
                                    ),
                                )
                            )

                        if not runners:
                            continue

                        races.append(
                            ScrapedRace(
                                track=track_name,
                                race_number=int(r.get("Race", 0)),
                                race_time=r.get("AdvertisedStartTime", "").split(" ")[
                                    -1
                                ][:5],
                                distance=1600,
                                track_condition="Good",
                                runners=runners,
                            )
                        )
                    return races
        except Exception as e:
            logger.debug(f"API fetch failed: {e}")
        return []

    def _parse_response(self, track: str, html: str) -> List[ScrapedRace]:
        """Parse the TAB HTML response into ScrapedRace objects"""
        from bs4 import BeautifulSoup

        races = []
        try:
            # Pre-load snapshot once for all runners from in-memory cache
            from core_agent.core.snapshot_cache import get_snapshot
            snapshot = get_snapshot()

            soup = BeautifulSoup(html, "html.parser")
            race_containers = soup.select(".race-card, [class*='race'], [data-race]")

            if not race_containers:
                return []

            for i, container in enumerate(race_containers, start=1):
                runners = []
                runner_rows = container.select("tr, .runner, [class*='runner']")

                for row in runner_rows:
                    name_el = row.select_one(
                        ".horse-name, [class*='name'], td:first-child"
                    )
                    if not name_el:
                        continue

                    horse_name = name_el.get_text(strip=True)
                    if not horse_name or len(horse_name) < 2:
                        continue

                    runners.append(
                        ScrapedRunner(
                            horse_name=horse_name,
                            odds_decimal=get_live_odds(
                                track, horse_name, snapshot=snapshot
                            ),
                        )
                    )

                if runners:
                    time_el = container.select_one(".race-time, [class*='time']")
                    race_time = (
                        time_el.get_text(strip=True) if time_el else f"{12 + i}:30"
                    )

                    races.append(
                        ScrapedRace(
                            track=track,
                            race_number=i,
                            race_time=race_time,
                            distance=1600,
                            track_condition="Good",
                            runners=runners,
                        )
                    )

        except Exception as e:
            logger.error(f"Parse error for {track}: {e}")
        return races

    def _stub_races(self, track: str, date_str: Optional[str]) -> List[ScrapedRace]:
        """Stub data for testing."""
        return [
            ScrapedRace(
                track=track,
                race_number=r,
                race_time=f"{11+r}:30",
                distance=1600,
                track_condition="Good",
                runners=[
                    ScrapedRunner(horse_name=f"Stub Horse {i}", odds_decimal=5.0)
                    for i in range(5)
                ],
            )
            for r in range(1, 5)
        ]

    async def close(self):
        """Close the client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
