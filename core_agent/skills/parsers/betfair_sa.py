"""
Betfair SA Form-Data Parser -- gear + days since last run per runner.

Public JSON API (no auth cookies needed):
    GET /api/horse-racing/7/all?timeRange=TODAY|TOMORROW   -> regional groups -> events -> markets
    GET /api/market/{marketId}                             -> runners[].metadata.wearing + .days_since_last_run

Integration:
    api = BetfairSA()
    form = await api.get_form_format()
    # form["events"] returns the same (course,time)->runners shape the merge expects,
    # so _merge_bf_into() can fuzzy-match horses and attach gear + daysSinceRun.
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from core_agent.config.paths import DATA_DIR
from core_agent.core.http_client import get_async_client

logger = logging.getLogger("betfair-sa")

BASE_URL = "https://exchange.betfairsa.co.za/customer"

# Canonical gear tokens (normalized at parse time, per design.md).
_CANONICAL_GEAR = [
    "Hood",
    "Blinkers",
    "Tongue strap",
    "Visor",
    "Eye shade",
    "Cheek pieces",
    "Cross noseband",
    "Rear looker",
]

# Betfair form data is slow-moving (gear/last-run don't change intra-race), so a
# single monitor cycle covers a couple of timeRange buckets.
_TIME_RANGES = ["TODAY", "TOMORROW"]

# Focus: SA races. Set to None to ingest every region (more API calls).
_COUNTRY_FILTER = {"ZA"}

# Race times are always reported in South African Standard Time (UTC+2, no DST)
# regardless of the host container's TZ, so the HUD shows consistent times.
_SAST = timezone(timedelta(hours=2))


def _normalize_gear(raw: Any) -> Optional[str]:
    """Normalize a raw ``wearing`` string to canonical tokens joined by ' · '.

    Substring-matches each canonical token case-insensitively, preserves the
    canonical casing/order, and drops raw connective words ("and", ",", "/").
    Unknown gear passes through title-cased. ``None``/empty stays absent.
    """
    if not raw or not isinstance(raw, str):
        return None
    text = raw.lower().strip()
    if not text:
        return None
    found = [tok for tok in _CANONICAL_GEAR if tok.lower() in text]
    if found:
        return " · ".join(found)
    return raw.strip().title()


def _parse_days(raw: Any) -> Optional[int]:
    """Parse ``days_since_last_run`` to a non-negative int, or None if absent."""
    if raw is None:
        return None
    try:
        n = int(raw)
        return n if n >= 0 else None
    except (ValueError, TypeError):
        return None


def _normalise(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


class BetfairSA:
    """Betfair SA form-data source: wearing gear + days since last run."""

    def __init__(
        self,
        country_filter: Optional[set] = None,
        time_ranges: Optional[List[str]] = None,
        cache_dir: Optional[Path] = None,
    ):
        self.country_filter = country_filter if country_filter is not None else _COUNTRY_FILTER
        self.time_ranges = time_ranges if time_ranges is not None else _TIME_RANGES
        self.cache_dir = cache_dir or (DATA_DIR / "betfair_form")
        os.makedirs(self.cache_dir, exist_ok=True)

    async def get_form_format(self) -> Dict[str, Any]:
        """Return form data in the flat snapshot shape used by the merge.

        Shape::
            {
              "events": {
                marketId: {
                  "course": "Scottsville",
                  "t": "12:07",
                  "raceName": "R1 1200m Mdn",
                  "runners": [
                    {"name": "Task Force", "gear": "Blinkers · Tongue strap", "daysSinceRun": 16}
                  ]
                }
              },
              "count": N
            }
        """
        client = get_async_client(timeout=30.0, resolve_hosts={"exchange.betfairsa.co.za"})
        headers = {
            "accept": "application/json, text/plain, */*",
            "referer": f"{BASE_URL}/sport/7",
        }

        # 1. Collect marketIds across timeRange buckets + regional groups.
        market_ids: List[str] = [
        ]
        seen: set = set()
        for tr in self.time_ranges:
            try:
                url = f"{BASE_URL}/api/horse-racing/7/all?timeRange={tr}"
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                raw = resp.json()
                if not isinstance(raw, list):
                    logger.debug("Betfair SA timeRange=%s: non-list response, skipping", tr)
                    continue
                groups = raw
            except Exception as e:
                logger.warning("Betfair SA header fetch failed (timeRange=%s): %s", tr, e)
                continue

            for grp in groups:
                if not isinstance(grp, dict):
                    continue
                if self.country_filter and grp.get("countryCode") not in self.country_filter:
                    continue
                for event in grp.get("events", []) or []:
                    for market in event.get("markets", []) or []:
                        mid = str(market.get("marketId", ""))
                        if mid and mid not in seen:
                            seen.add(mid)
                            market_ids.append(mid)

        if not market_ids:
            logger.info("Betfair SA: no markets found for country_filter=%s", self.country_filter)
            return {"events": {}, "count": 0}

        logger.debug("Betfair SA: fetching runner details for %d markets", len(market_ids))

        # 2. Fetch runner details per market (concurrent, bounded).
        sem = asyncio.Semaphore(8)
        tasks = [self._fetch_market(client, mid, headers, sem) for mid in market_ids]
        market_results = await asyncio.gather(*tasks)

        # 3. Assemble the flat events dict + cache raw payload.
        events: Dict[str, Any] = {}
        cache_payload: Dict[str, Any] = {"cached_at": datetime.now().isoformat(), "markets": {}}
        for mid, data in market_results:
            if not data:
                continue
            cache_payload["markets"][mid] = data
            event = self._parse_market(mid, data)
            if event:
                events[mid] = event

        # 4. Cache raw responses for debugging / last-good reuse.
        try:
            cache_file = self.cache_dir / f"betfair_form_{datetime.now().strftime('%Y%m%d')}.json"
            cache_file.write_text(json.dumps(cache_payload, indent=2))
        except Exception as e:
            logger.debug("Betfair SA cache write failed: %s", e)

        logger.info("Betfair SA: parsed %d races with runner details", len(events))
        return {"events": events, "count": len(events)}

    async def _fetch_market(
        self, client, market_id: str, headers: dict, sem: asyncio.Semaphore
    ) -> tuple:
        """Fetch one market's runner details. Returns (market_id, data_dict)."""
        url = f"{BASE_URL}/api/market/{market_id}"
        backoff = [2, 5]
        for attempt in range(3):
            try:
                async with sem:
                    resp = await client.get(url, headers=headers)
                if resp.status_code == 200:
                    return market_id, resp.json()
                logger.debug("Betfair SA market %s -> HTTP %d", market_id, resp.status_code)
            except Exception as e:
                logger.debug("Betfair SA market %s attempt %d failed: %s", market_id, attempt + 1, e)
                if attempt < len(backoff):
                    await asyncio.sleep(backoff[attempt])
        logger.warning("Betfair SA market %s: all attempts failed -- skipping", market_id)
        return market_id, None

    def _parse_market(self, market_id: str, data: Optional[Dict]) -> Optional[Dict]:
        """Convert a market response into the flat event shape."""
        if not data:
            return None
        runners_raw = data.get("runners", []) or []
        runners: List[Dict] = []
        for r in runners_raw:
            meta = r.get("metadata", {}) or {}
            name = r.get("runnername") or meta.get("runnername")
            if not name:
                continue
            gear = _normalize_gear(meta.get("wearing"))
            days = _parse_days(meta.get("days_since_last_run"))
            runner: Dict[str, Any] = {"name": name}
            if gear:
                runner["gear"] = gear
            if days is not None:
                runner["daysSinceRun"] = days
            runners.append(runner)

        if not runners:
            return None

        return {
            "course": self._course_from_market(data),
            "t": self._time_from_market(data),
            "raceName": self._race_name_from_market(data),
            "runners": runners,
        }

    @staticmethod
    def _race_name_from_market(data: Dict) -> Optional[str]:
        markets = data.get("markets", []) or []
        if markets and isinstance(markets[0], dict):
            return markets[0].get("name")
        return None

    @staticmethod
    def _course_from_market(data: Dict) -> str:
        """Best-effort course/track name from a market payload."""
        for path in (("event", "name"), ("eventName",), ("race", "course"), ("course",)):
            obj: Any = data
            for key in path:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    obj = None
                    break
            if isinstance(obj, str) and obj.strip():
                return obj.strip()
        return "Unknown"

    @staticmethod
    def _time_from_market(data: Dict) -> str:
        """Best-effort race time (HH:MM) from a market payload."""
        for path in (("event", "startTime"), ("startTime",), ("race", "time")):
            obj: Any = data
            for key in path:
                if isinstance(obj, dict):
                    obj = obj.get(key)
                else:
                    obj = None
                    break
            if isinstance(obj, (int, float)) and obj > 0:
                try:
                    return datetime.fromtimestamp(obj / 1000, tz=_SAST).strftime("%H:%M")
                except Exception:
                    pass
        return "00:00"
