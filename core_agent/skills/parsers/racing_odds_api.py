"""Racing-Odds.com Scraper -- Alternative Odds Comparison Source

Fully scrapable HTML (no Cloudflare, no SPA). Provides fractional odds
from up to 3 bookmakers (Megapari, Melbet, 1xbet) per horse.

Integration:
    api = RacingOddsAPI()
    snapshot = await api.get_snapshot_format()
    # snapshot["events"] returns same structure as BetwayAPI for drop-in merge.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

try:
    from scrapling.fetchers import Fetcher
    from scrapling.parser import Selector
    _SCRAPLING_AVAILABLE = True
except ImportError:
    _SCRAPLING_AVAILABLE = False

    class Fetcher:
        @staticmethod
        def get(url, **kwargs):
            return type("Page", (), {"status": 200, "body": b""})()

    class Selector:
        def __init__(self, html): pass
        def css(self, sel): return []
        def xpath(self, sel): return type("XPath", (), {"get": lambda *a, **kw: None})()

logger = logging.getLogger("racing-odds")


def _fractional_to_decimal(fractional: str) -> float:
    try:
        parts = fractional.split("/")
        num, den = float(parts[0]), float(parts[1])
        return round((num / den) + 1, 2)
    except (ValueError, IndexError, ZeroDivisionError):
        return 0.0


def _parse_horse_name_from_dataid(data_id: str) -> str:
    name = re.sub(r"^modal", "", data_id)
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
    return name.strip().title()


def _normalise(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", name).lower()


class RacingOddsAPI:
    BASE_URL = "https://www.racing-odds.com"

    def _fetch(self, path: str) -> Optional[bytes]:
        url = f"{self.BASE_URL}{path}"
        if not _SCRAPLING_AVAILABLE:
            logger.warning("Racing-odds scrapling not installed — using stub fallback, will return empty")
        page = Fetcher.get(url, impersonate="chrome131", timeout=30)
        if page.status != 200:
            logger.warning("Racing-odds %s -> %s", path, page.status)
            return None
        body_len = len(page.body) if page.body else 0
        if body_len < 500:
            logger.warning("Racing-odds %s suspiciously small body (%d bytes) — possible blocking", path, body_len)
        return page.body

    # ------------------------------------------------------------------
    # Daily page -- list of today's meetings + per-race detail URLs
    # ------------------------------------------------------------------
    def _parse_daily(self, html: bytes) -> List[Dict]:
        sel = Selector(html, auto_save=True)
        races: List[Dict] = []
        seen: set = set()

        for a in sel.css('a[href*="/daily/"]'):
            href = a.attrib.get("href", "")
            # href: /daily/{course}/{date}/{time}  (race detail)
            parts = href.strip("/").split("/")
            if len(parts) != 4:
                continue
            if href in seen:
                continue
            seen.add(href)
            course, date, time = parts[1], parts[2], parts[3]
            races.append({
                "course": course.replace("-", " ").title(),
                "date": date,
                "time": time,
                "detail_url": href,
                "race_time_display": a.get_all_text(strip=True),
            })

        return races

    async def fetch_daily_meetings(self) -> List[Dict]:
        html = await asyncio.to_thread(self._fetch, "/daily")
        if not html:
            return []
        return self._parse_daily(html)

    # ------------------------------------------------------------------
    # Race detail page -- per-horse, per-bookmaker odds
    # ------------------------------------------------------------------
    def _parse_race_detail(self, html: bytes) -> List[Dict]:
        sel = Selector(html, auto_save=True)
        horses: List[Dict] = []

        for card in sel.css(".ro-runners .ro-racecard"):
            name_el = card.css(".ro-racecard__name")
            if not name_el:
                continue
            raw_name = name_el[0].get_all_text(strip=True)
            # Strip leading number+dot: "1. Arishka's Dream" -> "Arishka's Dream"
            horse_name = re.sub(r"^\d+\.\s*", "", raw_name).strip()
            if not horse_name:
                continue

            detail = card.css(".ro-racecard__detail")
            odds_container = detail[0].css(".ro-racecard__odds") if detail else []

            bookmakers: Dict[str, float] = {}
            if odds_container:
                for odds_btn in odds_container[0].css('a[href*="/go/"]'):
                    href = odds_btn.attrib.get("href", "")
                    text = odds_btn.get_all_text(strip=True)
                    # Extract just the fractional part (ignore arrows/status)
                    frac_match = re.match(r"(\d+/\d+)", text)
                    if not frac_match:
                        continue
                    frac = frac_match.group(1)
                    bm_id = href.split("/go/")[-1].rstrip("/") if "/go/" in href else ""
                    if bm_id:
                        bookmakers[bm_id] = _fractional_to_decimal(frac)

            if not bookmakers:
                continue

            best_odds = min(bookmakers.values())
            horses.append({
                "name": horse_name,
                "odds_decimal": best_odds,
                "bookmakers": bookmakers,
            })

        return horses

    async def fetch_race_detail(self, detail_url: str) -> List[Dict]:
        html = await asyncio.to_thread(self._fetch, detail_url)
        if not html:
            return []
        return self._parse_race_detail(html)

    # ------------------------------------------------------------------
    # Full scan -- all races across all meetings
    # ------------------------------------------------------------------
    async def scan_all(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Scan all meetings, optional ``target_date`` filter (ISO or RO format)."""
        meetings = await self.fetch_daily_meetings()
        if not meetings:
            return {"races": [], "count": 0}

        if target_date:
            try:
                dt = datetime.strptime(target_date, "%Y-%m-%d")
                ro_date_str = dt.strftime("%d-%B-%Y")
            except ValueError:
                ro_date_str = target_date
            filtered = [m for m in meetings if m.get("date", "").lower() == ro_date_str.lower()]
            if not filtered:
                for offset in (1, -1):
                    try:
                        dt = datetime.strptime(ro_date_str, "%d-%B-%Y")
                        alt = (dt + timedelta(days=offset)).strftime("%d-%B-%Y")
                        filtered = [m for m in meetings if m.get("date", "").lower() == alt.lower()]
                        if filtered:
                            break
                    except ValueError:
                        continue
            meetings = filtered

        sem = asyncio.Semaphore(3)
        async def _fetch_one(race: Dict) -> Optional[Dict]:
            async with sem:
                horses = await self.fetch_race_detail(race["detail_url"])
                if not horses:
                    return None
                return {
                    "course": race["course"],
                    "date": race["date"],
                    "time": race["time"],
                    "horses": horses,
                }

        tasks = [_fetch_one(r) for r in meetings]
        results = await asyncio.gather(*tasks)
        races = [r for r in results if r]
        return {"races": races, "count": len(races)}

    # ------------------------------------------------------------------
    # Snapshot format (drop-in compatible with BetwayAPI)
    # ------------------------------------------------------------------
    async def get_snapshot_format(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        scan = await self.scan_all(target_date=target_date)
        events: Dict[str, Dict] = {}
        for idx, race in enumerate(scan.get("races", [])):
            eid = f"ro_{race['course']}_{race['time']}"
            runners = []
            for h in race.get("horses", []):
                runners.append({
                    "outcomeId": f"ro_{_normalise(h['name'])}",
                    "name": h["name"],
                    "outcomeName": h["name"],
                    "odds": h["odds_decimal"],
                    "jockeyName": "TBA",
                    "trainerName": "TBA",
                    "age": "U",
                    "weight": "0",
                    "form": "",
                    "number": "0",
                    "draw": 0,
                    "timeForm": "",
                    "imageLocation": "",
                    "starRating": 0,
                    "ro_odds": h["odds_decimal"],
                    "ro_bookmakers": h["bookmakers"],
                })
            if not runners:
                continue
            events[eid] = {
                "id": eid,
                "en": f"Racing-Odds: {race['course']}",
                "course": race["course"],
                "name": f"{race['course']} {race['time']}",
                "t": race["time"],
                "st": race["time"],
                "date": race["date"],
                "raceNumber": idx + 1,
                "isFinished": False,
                "runners": runners,
                "_source": "racing-odds",
            }
        return {"events": events, "count": len(events)}
