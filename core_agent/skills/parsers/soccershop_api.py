"""SoccerShop (Ambernet) Racing API Client.

Fetches racecards, runners, and live fixed odds from SoccerShop's Ambernet
backend (https://90addc26743700ecf47f71f3a4cdb556.ambernet.eu).

Architecture & Anti-Ban Rules:
1. Pinned TLS profile: IMPERSONATE = 'chrome131'. Never rotate randomly.
2. Consistent headers: Origin, Referer, X-Website-ID: 4000166.
3. Ambernet REST endpoints are Cloudflare-WAF invariant and do not block datacenter IPs.
4. Odds Normalization:
   SoccerShop/Ambernet prices may appear as European decimal (e.g. 5.0, 1.80)
   or net profit/Hong Kong style decimals (e.g. 0.80 for 4/5, 0.25 for 1/4).
   Any raw price between 0.0 and 1.0 represents net profit per 1 unit stake,
   so it is converted to standard European decimal via `round(raw_price + 1.0, 4)`.
   Zero or negative prices represent unpriced / SP.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from .tab4racing import ScrapedRace, ScrapedRunner

logger = logging.getLogger(__name__)


def normalize_soccershop_odds(raw: Any) -> Any:
    """Normalize raw SoccerShop / Ambernet price into standard decimal odds (>= 1.0) or 'SP'.

    Rules:
    - None, 0, or <= 0 -> 'SP'
    - 0.0 < raw < 1.0 (e.g. 0.80, 0.25) -> net profit format: returns raw + 1.0 (1.80, 1.25)
    - raw >= 1.0 (e.g. 1.80, 5.0) -> standard European decimal odds
    """
    if raw is None:
        return "SP"
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return "SP"

    if val <= 0:
        return "SP"
    if 0.0 < val < 1.0:
        return round(val + 1.0, 4)
    return round(val, 4)


class SoccerShopAPI:
    """Parser for SoccerShop's Ambernet European backend."""

    BASE_URL = "https://90addc26743700ecf47f71f3a4cdb556.ambernet.eu"
    GAME_ID = 1603
    WEBSITE_ID = "4000166"
    IMPERSONATE = "chrome131"

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Origin": "https://bookabet.soccershop.bet",
        "Referer": "https://bookabet.soccershop.bet/",
        "X-Website-ID": WEBSITE_ID,
        "Accept": "application/json, text/plain, */*",
    }

    BATCH_CHUNK_SIZE = 50
    REQUEST_TIMEOUT = 12.0

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session
        self._owns_session = False
        if self._session is None:
            self._session = requests.Session(impersonate=self.IMPERSONATE)
            self._owns_session = True

    def close(self) -> None:
        """Close underlying curl_cffi session if owned."""
        if self._owns_session and self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None

    def __del__(self) -> None:
        self.close()

    def _get(self, path: str, params: Optional[dict] = None) -> requests.Response:
        url = f"{self.BASE_URL}{path}" if path.startswith("/") else path
        return self._session.get(
            url,
            headers=self.DEFAULT_HEADERS,
            params=params,
            timeout=self.REQUEST_TIMEOUT,
        )

    def _post(self, path: str, json_data: Any) -> requests.Response:
        url = f"{self.BASE_URL}{path}" if path.startswith("/") else path
        return self._session.post(
            url,
            headers=self.DEFAULT_HEADERS,
            json=json_data,
            timeout=self.REQUEST_TIMEOUT,
        )

    def fetch_all_events_sync(self) -> List[Dict[str, Any]]:
        """Fetch all active events from Ambernet game events catalog."""
        try:
            r = self._get(f"/v1/web-backend/game/{self.GAME_ID}/events")
            if r.status_code != 200:
                logger.warning(
                    "SoccerShop events endpoint returned HTTP %d: %s",
                    r.status_code,
                    r.text[:200],
                )
                return []
            data = r.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("events", [])
            return []
        except Exception as e:
            logger.error("SoccerShop fetch_all_events failed: %s", e)
            return []

    def fetch_event_batch_sync(self, event_uuids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Fetch detailed racecards and live odds for a list of event UUIDs."""
        if not event_uuids:
            return {}

        results: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(event_uuids), self.BATCH_CHUNK_SIZE):
            chunk = event_uuids[i : i + self.BATCH_CHUNK_SIZE]
            try:
                r = self._post(
                    f"/v1/web-backend/game/{self.GAME_ID}/module/horses/event/batch",
                    json_data=chunk,
                )
                if r.status_code == 200:
                    batch_res = r.json()
                    if isinstance(batch_res, dict):
                        results.update(batch_res)
                else:
                    logger.warning(
                        "SoccerShop batch endpoint returned HTTP %d for chunk %d",
                        r.status_code,
                        i,
                    )
            except Exception as e:
                logger.error("SoccerShop batch chunk %d failed: %s", i, e)

        return results

    # Pool/bet-type "meetings" ride the same feed as races but are not races:
    # "Bipot - 1 R6", "Pick 6", "Jackpot". Merging them would mint phantom
    # races onto the card, so they are dropped at the source.
    POOL_NAME_MARKERS = (
        "bipot", "pick 6", "pick6", "jackpot", "place accumulator",
        "swinger", "exacta", "trifecta", "quartet", "daily double",
    )

    @classmethod
    def _is_pool_entry(cls, event: Dict[str, Any]) -> bool:
        name = str(
            event.get("meetingCode")
            or event.get("meetingName")
            or event.get("name")
            or ""
        ).lower()
        return any(marker in name for marker in cls.POOL_NAME_MARKERS)

    async def fetch_racing_data(
        self,
        country_code: Optional[str] = None,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Async worker to fetch and filter SoccerShop events and racecards.

        ``country_code`` defaults to None (all countries): this is a fallback
        source, so narrowing to ZA discarded 11 of 14 usable events on a day
        when Betway was blocked.
        """
        loop = asyncio.get_running_loop()
        events_list = await loop.run_in_executor(None, self.fetch_all_events_sync)
        if not events_list:
            return {"status": "error", "error": "No events returned from SoccerShop", "details": []}

        filtered_events = []
        for ev in events_list:
            if country_code and ev.get("countryCode") != country_code:
                continue
            if self._is_pool_entry(ev):
                continue

            # Check target date if specified
            if target_date:
                close_time = ev.get("bettingCloseTime") or ev.get("startTime") or ""
                if close_time and not close_time.startswith("0001"):
                    try:
                        dt = datetime.fromisoformat(close_time.replace("Z", "+00:00"))
                        local_d = dt.strftime("%Y-%m-%d")
                        if local_d != target_date:
                            continue
                    except Exception:
                        pass

            filtered_events.append(ev)

        if not filtered_events:
            logger.info("SoccerShop: no events matching country=%s, date=%s", country_code, target_date)
            return {"status": "ok", "details": []}

        uuids = [e["uuid"] for e in filtered_events if "uuid" in e]
        batch_details = await loop.run_in_executor(None, self.fetch_event_batch_sync, uuids)

        details = []
        for ev in filtered_events:
            uid = ev.get("uuid")
            if uid and uid in batch_details:
                item = batch_details[uid]
                item["eventMeta"] = ev
                details.append(item)
            else:
                # Include skeleton event
                details.append({"uuid": uid, "eventMeta": ev})

        return {"status": "ok", "details": details}

    async def get_snapshot_format(
        self,
        country_code: Optional[str] = None,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns racing data in the flat 'market_snapshot' format."""
        raw = await self.fetch_racing_data(country_code=country_code, target_date=target_date)
        if raw.get("status") == "error":
            return {
                "events": {},
                "count": 0,
                "fetch_ok": False,
                "fetch_error": str(raw.get("error", "unknown")),
            }

        events: Dict[str, Any] = {}
        for det in raw.get("details", []):
            try:
                uid = det.get("uuid") or det.get("meetingUUID")
                if not uid:
                    continue

                track = det.get("track") or (det.get("eventMeta") or {}).get("track") or "Unknown"
                country = det.get("countryCode") or (det.get("eventMeta") or {}).get("countryCode") or "ZA"
                race_num = int(det.get("raceNumber") or 0)

                # Parse race time
                close_ts = det.get("bettingCloseTime") or (det.get("eventMeta") or {}).get("bettingCloseTime")
                race_time = "00:00"
                if close_ts and not close_ts.startswith("0001"):
                    try:
                        dt = datetime.fromisoformat(close_ts.replace("Z", "+00:00"))
                        race_time = dt.strftime("%H:%M")
                    except Exception:
                        pass

                runners = []
                for h in det.get("horses", []):
                    r_name = (h.get("name") or "Unknown").strip()
                    raw_p = h.get("price")
                    normalized_p = normalize_soccershop_odds(raw_p)
                    place_p = normalize_soccershop_odds(h.get("placePrice"))

                    runners.append({
                        "outcomeId": str(h.get("id") or ""),
                        "name": r_name,
                        "outcomeName": r_name,
                        "non_runner": h.get("status") == "Withdrawn",
                        "jockeyName": h.get("jockey") or "TBA",
                        "trainerName": h.get("trainer") or "TBA",
                        "age": "U",
                        "weight": "0",
                        "form": "",
                        "number": str(h.get("clothNumber") or "0"),
                        "draw": int(h.get("clothNumber") or 0),
                        "timeForm": "",
                        "imageLocation": "",
                        "starRating": 0,
                        "odds": normalized_p,
                        "place_odds": place_p,
                    })

                eid = f"soccershop_{uid}"
                events[eid] = {
                    "id": eid,
                    "en": f"{country}: {track}",
                    "course": track,
                    "name": f"Race {race_num}",
                    "t": race_time,
                    "st": race_time,
                    "raceNumber": race_num,
                    "isFinished": det.get("status") in ("Resulted", "Closed", "Finished"),
                    "runners": runners,
                    "price_source": "soccershop",
                }
            except Exception as e:
                logger.error("Error formatting SoccerShop event %s: %s", det.get("uuid", "?"), e)

        return {"events": events, "count": len(events), "fetch_ok": True}

    async def get_races(
        self,
        country_code: Optional[str] = None,
        target_date: Optional[str] = None,
    ) -> List[ScrapedRace]:
        """Convert snapshot into typed ScrapedRace objects."""
        snapshot = await self.get_snapshot_format(country_code=country_code, target_date=target_date)
        races: List[ScrapedRace] = []
        for eid, ev in snapshot.get("events", {}).items():
            runners: List[ScrapedRunner] = []
            for r in ev.get("runners", []):
                odds_val = r.get("odds")
                decimal_odds = float(odds_val) if isinstance(odds_val, (int, float)) and odds_val > 1.0 else 0.0
                runners.append(
                    ScrapedRunner(
                        horse_name=r.get("name", "Unknown"),
                        odds_decimal=decimal_odds,
                        jockey=r.get("jockeyName"),
                        trainer=r.get("trainerName"),
                        barrier=int(r.get("number") or 0),
                    )
                )
            races.append(
                ScrapedRace(
                    track=ev.get("course", "Unknown"),
                    race_number=ev.get("raceNumber", 0),
                    race_time=ev.get("t", "00:00"),
                    distance=None,
                    track_condition="Good",
                    runners=runners,
                )
            )
        return races
