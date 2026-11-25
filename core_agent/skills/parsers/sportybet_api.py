"""SportyBet (BetMakers Apollo) Racing API Client.

Fetches racecards, runners, and live fixed odds from SportyBet's BetMakers
Apollo GraphQL backend (https://racing.sporty.bmapollo.com/query).

Architecture & Anti-Ban Rules:
1. Transport is stdlib ``urllib``, deliberately NOT curl_cffi/httpx.
   Measured 2026-11-25 from the same host, same headers, same payload:
       urllib      -> HTTP 200, 23 meetings
       curl_cffi (with and without impersonate) -> HTTP 403
       httpx       -> HTTP 403
   SportyBet's edge fingerprints the TLS stack, and the Chrome-131
   impersonation profile is exactly what it rejects. Do not "improve" this
   back to curl_cffi to match the other parsers.
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
import gzip
import json
import logging
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

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

    # The backend throttles by query cost and answers a too-large batch with
    # "not authorized to perform this action" (not a 403, and not a hard cap:
    # the same batch succeeds moments later). 30 ids failed intermittently,
    # 24 passed, so keep chunks small and retry rather than lose a whole cycle.
    BATCH_CHUNK_SIZE = 15
    REQUEST_TIMEOUT = 20.0
    MAX_RETRIES = 3
    RETRY_BACKOFF_SECONDS = 2.0

    def __init__(self) -> None:
        # No pooled client on purpose: see the module docstring. urllib has no
        # session to leak, and opening one connection per query keeps us off
        # the connection-reuse heuristics that curl_cffi's session tripped.
        pass

    def close(self) -> None:
        """No-op: kept so callers can close parsers uniformly."""

    def __del__(self) -> None:  # pragma: no cover - defensive only
        self.close()

    def _query(self, query: str, variables: Optional[dict] = None, operation_name: Optional[str] = None) -> dict:
        payload: dict = {"query": query}
        if variables:
            payload["variables"] = variables
        if operation_name:
            payload["operationName"] = operation_name

        request = urllib.request.Request(
            self.GRAPHQL_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers=self.DEFAULT_HEADERS,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.REQUEST_TIMEOUT) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            body = ""
            try:
                body = exc.read()[:200].decode("utf-8", "replace")
            except Exception:
                pass
            logger.warning("SportyBet GraphQL query failed with HTTP %d: %s", exc.code, body)
            return {}
        except Exception as exc:
            logger.warning("SportyBet GraphQL query failed: %s", exc)
            return {}

        if raw[:2] == b"\x1f\x8b":
            raw = gzip.decompress(raw)
        try:
            data = json.loads(raw)
        except ValueError:
            logger.warning("SportyBet GraphQL returned non-JSON body (%d bytes)", len(raw))
            return {}

        # A GraphQL error arrives with HTTP 200. Returning it silently is what
        # hid three separate faults (bad date format, 32h window cap, throttled
        # batches) behind a "0 meetings" that looked like an empty race day.
        errors = data.get("errors")
        if errors:
            logger.warning(
                "SportyBet GraphQL error%s: %s",
                f" on {operation_name}" if operation_name else "",
                "; ".join(str(e.get("message")) for e in errors if isinstance(e, dict))[:200],
            )
        return data

    # SportyBet rejects any window wider than 32h:
    #   "duration between start and end date cannot be more than 32h0m0s"
    # The parser used to ask for 48h (now-12h .. now+36h), so every cycle got
    # a GraphQL error, which was swallowed into an empty list. A full calendar
    # day is 24h and always fits.
    MAX_WINDOW_HOURS = 32

    @classmethod
    def _query_window(cls, target_date: Optional[str] = None) -> tuple:
        """Return (start, end) RFC3339 stamps that fit inside the 32h cap."""
        if target_date:
            try:
                day = datetime.strptime(target_date[:10], "%Y-%m-%d").replace(
                    tzinfo=timezone.utc
                )
                return (
                    day.strftime("%Y-%m-%dT00:00:00Z"),
                    day.strftime("%Y-%m-%dT23:59:59Z"),
                )
            except ValueError:
                pass

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=8)
        end = start + timedelta(hours=cls.MAX_WINDOW_HOURS - 1)
        return (
            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    @staticmethod
    def _rfc3339(value: str, end_of_day: bool = False) -> str:
        """Coerce a date to the RFC3339 form Apollo's ``Date!`` scalar requires.

        Apollo rejected the bare ``2026-11-25`` with:
            parsing time "2026-11-25" as "2006-01-02T15:04:05Z":
            cannot parse "" as "T"
        That error was swallowed into an empty list, so every cycle reported
        "0 meetings" and the whole source looked dead. Accept either a date or
        an already-formed timestamp.
        """
        text = (value or "").strip()
        if "T" in text:
            return text
        return f"{text}T{'23:59:59' if end_of_day else '00:00:00'}Z"

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
        data = self._query(
            q,
            {
                "startDate": self._rfc3339(start_date),
                "endDate": self._rfc3339(end_date, end_of_day=True),
            },
            "meetingsBetween",
        )
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
        failed_chunks = 0
        for i in range(0, len(race_ids), self.BATCH_CHUNK_SIZE):
            chunk = race_ids[i : i + self.BATCH_CHUNK_SIZE]
            meetings = []
            for attempt in range(self.MAX_RETRIES):
                data = self._query(q, {"race_ids": chunk}, "raceCard")
                if not data.get("errors"):
                    meetings = (data.get("data") or {}).get("meetingRaces") or []
                    break
                # Throttled: back off and try the same chunk again.
                time.sleep(self.RETRY_BACKOFF_SECONDS * (attempt + 1))
            if not meetings and chunk:
                failed_chunks += 1
            all_meetings.extend(meetings)

        if failed_chunks:
            logger.warning(
                "SportyBet: %d of %d racecard batches failed after %d attempts",
                failed_chunks,
                (len(race_ids) + self.BATCH_CHUNK_SIZE - 1) // self.BATCH_CHUNK_SIZE,
                self.MAX_RETRIES,
            )
        return all_meetings

    async def get_snapshot_format(
        self,
        country: Optional[str] = None,
        target_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        # country=None by default: this is a *fallback* source, and Betway is
        # often blocked entirely. Filtering to South Africa threw away most of
        # a 23-meeting day for the sake of a handful of ZA races.
        """Returns racing data in flat market_snapshot format."""
        loop = asyncio.get_running_loop()

        start_date, end_date = self._query_window(target_date)

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
                    # Find the fixed WIN price. Apollo names it
                    # "racingFutureWin" (not "WIN"), so an exact match on "WIN"
                    # silently produced "SP" for every runner on a live feed.
                    fixed_win = next(
                        (
                            p.get("price")
                            for p in prices
                            if (p.get("product") or {}).get("is_fixed")
                            and "win" in str(p.get("bet_type") or "").lower()
                        ),
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
