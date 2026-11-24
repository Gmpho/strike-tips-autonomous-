"""SportyBet (BetMakers Apollo) Racing API Client.

Fetches racecards, runners, and live fixed odds from SportyBet's BetMakers
Apollo GraphQL backend (https://racing.sporty.bmapollo.com/query).

Architecture & Anti-Ban Rules:
1. Pinned TLS profile: IMPERSONATE = 'chrome131'.
2. Required headers:
   - x-api-key: "5kl1sj4d97mj623p1f04djhi1r"
   - Origin: "https://www.sportybet.co.za"
   - Referer: "https://www.sportybet.co.za/"
   - sec-ch-ua: '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
3. Uses GraphQL queries:
   - `meetingsBetween(startDate, endDate)`: Discovers all meetings and race IDs.
   - `raceCard(race_ids)`: Batched runner details and fixed odds.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
import logging
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from .tab4racing import ScrapedRace, ScrapedRunner

logger = logging.getLogger(__name__)


def normalize_sportybet_odds(raw: Any) -> Any:
    """Normalize raw SportyBet / BetMakers odds into standard decimal odds (>= 1.0) or 'SP'."""
    if raw is None:
        return "SP"
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return "SP"
    if val <= 1.0:
        return "SP"
    return round(val, 4)


class SportyBetAPI:
    """Parser for SportyBet's BetMakers Apollo GraphQL backend."""

    GRAPHQL_URL = "https://racing.sporty.bmapollo.com/query"
    API_KEY = "5kl1sj4d97mj623p1f04djhi1r"
    IMPERSONATE = "chrome131"

    DEFAULT_HEADERS = {
        "accept": "application/graphql-response+json, application/json",
        "content-type": "application/json",
        "origin": "https://www.sportybet.co.za",
        "referer": "https://www.sportybet.co.za/",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "cross-site",
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "x-api-key": API_KEY,
    }

    BATCH_CHUNK_SIZE = 30
    REQUEST_TIMEOUT = 15.0

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

    def _query(self, query: str, variables: Optional[dict] = None, operation_name: Optional[str] = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name
        r = self._session.post(
            self.GRAPHQL_URL,
            headers=self.DEFAULT_HEADERS,
            json=payload,
            timeout=self.REQUEST_TIMEOUT,
        )
        if r.status_code != 200:
            logger.warning("SportyBet GraphQL query failed with HTTP %d: %s", r.status_code, r.text[:200])
            return {}
        return r.json()

    def fetch_meetings_sync(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        """Fetch all meetings between start_date and end_date."""
        q = """
        query meetingsBetween($startDate: Date!, $endDate: Date!) {
          meetingsBetween(startDate: $startDate, endDate: $endDate) {
            id
            slug
            name
            start_date
            track {
              name
              country
            }
            races {
              id
              number
              status
              start_at
              fixed_odds_enabled
            }
          }
        }
        """
        data = self._query(q, {"startDate": start_date, "endDate": end_date}, "meetingsBetween")
        return (data.get("data") or {}).get("meetingsBetween") or []

    def fetch_race_cards_sync(self, race_ids: List[str]) -> List[Dict[str, Any]]:
        """Fetch racecards and runners for given race IDs."""
        if not race_ids:
            return []

        q = """
        query raceCard($race_ids: [ID!]!) {
          meetingRaces(race_ids: $race_ids) {
            name
            track {
              name
              country
            }
            races {
              id
              number
              status
              start_at
              runners {
                id
                tab_no
                name
                barrier
                jockey
                trainer
                status
                prices {
                  bet_type
                  price
                  product {
                    is_fixed
                  }
                }
              }
            }
          }
        }
        """
        all_meetings = []
        for i in range(0, len(race_ids), self.BATCH_CHUNK_SIZE):
            chunk = race_ids[i : i + self.BATCH_CHUNK_SIZE]
            data = self._query(q, {"race_ids": chunk}, "raceCard")
            meetings = (data.get("data") or {}).get("meetingRaces") or []
            all_meetings.extend(meetings)
        return all_meetings

    async def get_snapshot_format(
        self,
        country: Optional[str] = "South Africa",
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Returns racing data in flat market_snapshot format."""
        loop = asyncio.get_running_loop()

        now = datetime.now(timezone.utc)
        start_date = (now - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_date = (now + timedelta(hours=36)).strftime("%Y-%m-%dT%H:%M:%S.000Z")

        meetings = await loop.run_in_executor(None, self.fetch_meetings_sync, start_date, end_date)
        if not meetings:
            return {"events": {}, "count": 0, "fetch_ok": True}

        race_ids = []
        for m in meetings:
            m_country = ((m.get("track") or {}).get("country") or "").strip()
            if country and m_country.lower() not in (country.lower(), "za", "rsa"):
                continue

            for r in m.get("races") or []:
                rid = r.get("id")
                if rid:
                    race_ids.append(rid)

        if not race_ids:
            return {"events": {}, "count": 0, "fetch_ok": True}

        card_meetings = await loop.run_in_executor(None, self.fetch_race_cards_sync, race_ids)

        events: Dict[str, Any] = {}
        for m in card_meetings:
            course = (m.get("track") or {}).get("name") or m.get("name") or "Unknown"
            m_country = (m.get("track") or {}).get("country") or "South Africa"

            for r in m.get("races") or []:
                rid = r.get("id")
                if not rid:
                    continue

                r_num = int(r.get("number") or 0)
                start_at = r.get("start_at") or ""
                race_time = "00:00"
                if start_at:
                    try:
                        dt = datetime.fromisoformat(start_at.replace("Z", "+00:00"))
                        race_time = dt.strftime("%H:%M")
                    except Exception:
                        pass

                runners = []
                for runner in r.get("runners") or []:
                    r_name = (runner.get("name") or "Unknown").strip()
                    prices = runner.get("prices") or []
                    # Find fixed win price
                    fixed_win = next(
                        (p.get("price") for p in prices if p.get("bet_type") == "WIN" and (p.get("product") or {}).get("is_fixed")),
                        None,
                    )
                    odds = normalize_sportybet_odds(fixed_win)

                    runners.append({
                        "outcomeId": str(runner.get("id") or ""),
                        "name": r_name,
                        "outcomeName": r_name,
                        "non_runner": runner.get("status") in ("SCRATCHED", "WITHDRAWN"),
                        "jockeyName": runner.get("jockey") or "TBA",
                        "trainerName": runner.get("trainer") or "TBA",
                        "age": "U",
                        "weight": "0",
                        "form": "",
                        "number": str(runner.get("tab_no") or "0"),
                        "draw": int(runner.get("barrier") or 0),
                        "timeForm": "",
                        "imageLocation": "",
                        "starRating": 0,
                        "odds": odds,
                    })

                eid = f"sportybet_{rid}"
                events[eid] = {
                    "id": eid,
                    "en": f"{m_country}: {course}",
                    "course": course,
                    "name": f"Race {r_num}",
                    "t": race_time,
                    "st": race_time,
                    "raceNumber": r_num,
                    "isFinished": r.get("status") in ("CLOSED", "RESULTED", "PAYING"),
                    "runners": runners,
                    "price_source": "sportybet",
                }

        return {"events": events, "count": len(events), "fetch_ok": True}

    async def get_races(
        self,
        country: Optional[str] = "South Africa",
        target_date: Optional[str] = None,
    ) -> List[ScrapedRace]:
        """Convert snapshot into typed ScrapedRace objects."""
        snapshot = await self.get_snapshot_format(country=country, target_date=target_date)
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
