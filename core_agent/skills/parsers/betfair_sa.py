"""
Betfair Form-Data Parser -- enriched runner fields per market.

Public JSON API (no auth cookies needed):
    GET /api/horse-racing/7/all?timeRange=TODAY|TOMORROW   -> regional groups -> events -> markets
    GET /api/market/{marketId}                             -> runners[].metadata (gear, days, comments, rating, pedigree, owner, verdict...)

Integration:
    api = BetfairSA()
    form = await api.get_form_format()
    # form["events"] returns the same (course,time)->runners shape the merge expects,
    # so _merge_bf_into() can fuzzy-match horses and attach enriched fields.
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
_COUNTRY_FILTER = None

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


def _clean_str(raw: Any) -> Optional[str]:
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip()
    return s if s else None


def _parse_int_field(raw: Any) -> Optional[int]:
    if raw is None:
        return None
    try:
        s = str(raw).strip()
        if not s:
            return None
        n = int(float(s))
        return n
    except (ValueError, TypeError, AttributeError):
        return None


def _normalise(name: str) -> str:
    return "".join(c for c in name.lower() if c.isalnum())


class BetfairSA:
    """Betfair form-data source: enriched runner fields (gear, days, comments, rating...)."""

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
        market_ids: List[str] = []
        market_info: Dict[str, Dict[str, str]] = {}
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
                        mid = str(market.get("marketId") or market.get("id") or "")
                        if mid and mid not in seen:
                            seen.add(mid)
                            market_ids.append(mid)
                            # Store course/time for later (avoids relying on market payload)
                            market_info[mid] = {
                                "course": (event.get("name") or grp.get("name") or "Unknown").strip(),
                                "t": (market.get("timeLabel") or market.get("time") or "").strip(),
                                "raceName": (market.get("name") or "").strip(),
                            }

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
                # Override with stored info from /all (more reliable than market payload inference)
                info = market_info.get(mid, {})
                if info.get("course") and info["course"] != "Unknown":
                    event["course"] = info["course"]
                if info.get("t"):
                    event["t"] = info["t"]
                if info.get("raceName"):
                    event["raceName"] = info["raceName"]
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
        """Convert a market response into the flat event shape (enriched)."""
        if not data:
            return None
        runners_raw = data.get("runners", []) or []
        runners: List[Dict] = []
        for r in runners_raw:
            meta = r.get("metadata", {}) or {}
            # Normalize keys to lower for case-insensitive lookup (Betfair uses UPPER)
            meta_low = {str(k).lower(): v for k, v in meta.items()} if isinstance(meta, dict) else {}
            r_low = {str(k).lower(): v for k, v in r.items()} if isinstance(r, dict) else {}

            def _get(*keys):
                for k in keys:
                    lk = k.lower()
                    if lk in meta_low and meta_low[lk] not in (None, ""):
                        return meta_low[lk]
                    if lk in r_low and r_low[lk] not in (None, ""):
                        return r_low[lk]
                return None

            name = _get("runnerName", "runnername", "name") or r.get("runnerName") or r.get("runnername")
            if not name:
                continue
            gear = _normalize_gear(_get("wearing"))
            days = _parse_days(_get("days_since_last_run"))
            comments = _clean_str(_get("runner_comments", "comments", "runnercomments"))
            claim = _clean_str(_get("jockey_claim", "jockeyclaim"))
            rating = _parse_int_field(_get("official_rating", "officialrating"))
            # Pedigree: construct from sire/dam if not explicit
            pedigree = _clean_str(_get("pedigree"))
            if not pedigree:
                sire = _clean_str(_get("sire_name", "sirename"))
                dam = _clean_str(_get("dam_name", "damname"))
                damsire = _clean_str(_get("damsire_name", "damsirename"))
                if sire or dam:
                    parts = []
                    if sire:
                        parts.append(sire)
                    if dam:
                        parts.append(f"x {dam}")
                    if damsire:
                        parts.append(f"({damsire})")
                    pedigree = " ".join(parts) if parts else None
            owner = _clean_str(_get("owner_name", "owner"))
            verdict = _clean_str(_get("verdict"))
            trainer = _clean_str(_get("trainer_name", "trainer"))
            age = _parse_int_field(_get("age"))
            weight_val = _get("weight_value", "weight")
            weight_units = _get("weight_units")
            weight = None
            if weight_val is not None and str(weight_val).strip() not in ("", "null", "None"):
                w = str(weight_val).strip()
                # Betfair weight in pounds, keep as is; HUD expects string
                weight = f"{w} {weight_units}" if weight_units else w
                weight = weight.strip()
            form = _clean_str(_get("form"))

            runner: Dict[str, Any] = {"name": name}
            if gear:
                runner["gear"] = gear
            if days is not None:
                runner["daysSinceRun"] = days
            if comments:
                runner["runner_comments"] = comments
            if claim:
                runner["jockey_claim"] = claim
            if rating is not None:
                runner["official_rating"] = rating
            if pedigree:
                runner["pedigree"] = pedigree
            if owner:
                runner["owner"] = owner
            if verdict:
                runner["verdict"] = verdict
            if trainer:
                runner["trainer"] = trainer
            if age is not None:
                runner["age"] = age
            if weight:
                runner["weight"] = weight
            if form:
                runner["form"] = form
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
