import httpx
import logging
import asyncio
import re
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from .tab4racing import ScrapedRace, ScrapedRunner

logger = logging.getLogger("betway-api")


class BetwayAPI:
    BASE_URL = "https://www.betway.co.za/sportsapi/v1/TrackRacing"
    _USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    ]

    @property
    def HEADERS(self):
        return {
            "User-Agent": random.choice(self._USER_AGENTS),
            "Referer": "https://www.betway.co.za/sport/horse-racing",
            "Origin": "https://www.betway.co.za",
        }

    async def fetch_racing_data(self) -> Dict[str, Any]:
        """Fetch raw racing data from Betway's TrackRacing (TAB) API."""
        async with httpx.AsyncClient(headers=self.HEADERS, timeout=30.0) as client:
            for attempt in range(3):
                try:
                    daily_url = f"{self.BASE_URL}/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2"
                    daily_resp = await client.get(daily_url)
                    daily_resp.raise_for_status()
                    data = daily_resp.json()

                    event_ids = []
                    # Allowed regions to filter noise
                    ALLOWED = [
                        "South Africa",
                        "UK and Ireland",
                        "Australia",
                        "New Zealand",
                        "USA",
                        "Hong Kong",
                        "Japan",
                        "France",
                    ]

                    for reg in data.get("regions", []):
                        if not any(a in reg.get("name", "") for a in ALLOWED):
                            continue
                        for e in reg.get("sportEvents", []):
                            if not e.get("isFinished", True):
                                event_ids.append(
                                    (e["eventId"], reg.get("name"), (e.get("league") or "").strip())
                                )

                    # Fetch all unfinished event details with concurrency limit (reduces CPU burst)
                    sem = asyncio.Semaphore(10)
                    tasks = [
                        self._fetch_event_safe(client, eid, reg_name, league, sem)
                        for eid, reg_name, league in event_ids
                    ]

                    events_details = await asyncio.gather(*tasks)
                    # Filter out None values from failed fetches
                    events_details = [e for e in events_details if e]

                    return {"status": "success", "details": events_details}
                except Exception as e:
                    logger.warning(f"Betway fetch attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2**attempt)
            return {"status": "error", "error": "Max retries reached"}

    async def _fetch_event_safe(self, client, eid, reg_name, league, sem=None) -> Optional[Dict]:
        try:
            url = f"{self.BASE_URL}/GetEvent?eventIds={eid}&marketGroupName=&countryCode=ZA"
            if sem:
                async with sem:
                    await asyncio.sleep(random.uniform(0.05, 0.3))  # jitter
                    resp = await client.get(url)
            else:
                resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                data["eventId"] = eid
                data["regionName"] = reg_name
                data["leagueName"] = league
                return data
        except Exception as e:
            logger.debug(f"Failed to fetch event {eid}: {e}")
        return None

    async def get_snapshot_format(self) -> Dict[str, Any]:
        """Returns racing data in the flat 'market_snapshot' format used by the HUD and AlertEngine."""
        raw = await self.fetch_racing_data()
        if raw.get("status") == "error":
            return {"events": {}, "count": 0}

        events = {}
        for det in raw.get("details", []):
            try:
                eid = det.get("eventId")
                reg_name = det.get("regionName", "Unknown")
                league = det.get("leagueName", "Unknown")

                # GetEvent response: { result: { events: [...], outcomes: [...], prices: [...] } }
                res = det.get("result", det)
                event_obj = (res.get("events") or [{}])[0]

                # Skip finished races
                if event_obj.get("isFinished"):
                    continue

                # --- Race time from epoch on the event object ---
                race_time = "00:00"
                start_epoch = event_obj.get("expectedStartEpoch")
                if start_epoch:
                    try:
                        race_time = datetime.fromtimestamp(start_epoch).strftime("%H:%M")
                    except Exception:
                        pass

                # --- Race number from sportSpecificProperties ---
                race_num_prop = event_obj.get("sportSpecificProperties", {}).get("raceNumber")
                race_num = int(race_num_prop) if race_num_prop else 0
                if race_num == 0:
                    m = re.search(r"Race\s+(\d+)", event_obj.get("name", ""), re.IGNORECASE)
                    if m:
                        race_num = int(m.group(1))

                # --- Prices map: outcomeId (str) -> priceDecimal ---
                price_map = {
                    str(p["outcomeId"]): float(p.get("priceDecimal", 5.0))
                    for p in res.get("prices", [])
                    if isinstance(p, dict) and "outcomeId" in p
                }

                # --- Name-keyed price map for SA-style events where racer outcomeIds
                #     don't match price outcomeIds (prices belong to a different market's outcomes) ---
                # Build: horse_name (lower) -> best price from Race Winner market outcomes
                winner_market_id = next(
                    (str(mkt["marketId"]) for mkt in res.get("markets", [])
                     if "Race Winner" in mkt.get("name", "") or "Win Only" in mkt.get("name", "")),
                    None
                )
                name_price_map: dict = {}
                for outcome in res.get("outcomes", []):
                    if winner_market_id and str(outcome.get("marketId")) != winner_market_id:
                        continue
                    if outcome.get("nonRunner"):
                        continue
                    oid = str(outcome.get("outcomeId") or "")
                    price = price_map.get(oid)
                    if price:
                        name_key = (outcome.get("outcomeName") or outcome.get("name") or "").lower()
                        if name_key and name_key not in name_price_map:
                            name_price_map[name_key] = price

                # --- Build runners from raceEventDetails.racers (canonical source) ---
                # Fall back to outcomes filtered to Race Winner market if racers unavailable
                racers = (event_obj.get("raceEventDetails") or {}).get("racers") or []

                if racers:
                    runners = []
                    for r in racers:
                        outcome_id = str((r.get("outcomeIds") or [None])[0] or "")
                        # Try outcomeId first, then name-based lookup (SA-style events)
                        odds = price_map.get(outcome_id)
                        if odds is None:
                            horse_name_key = (r.get("outcomeName") or r.get("name") or "").lower()
                            odds = name_price_map.get(horse_name_key, 5.0)
                        runners.append({
                            "outcomeId": outcome_id,
                            "name": r.get("outcomeName") or r.get("name") or "Unknown",
                            "outcomeName": r.get("outcomeName") or r.get("name") or "Unknown",
                            "jockeyName": r.get("jockeyName") or "TBA",
                            "trainerName": r.get("trainerName") or "TBA",
                            "age": r.get("age") or "U",
                            "weight": r.get("weight") or "0",
                            "form": r.get("form") or "",
                            "number": str(r.get("number") or "0"),
                            "draw": int(r.get("draw") or 0),
                            "timeForm": r.get("timeForm") or "",
                            "imageLocation": r.get("imageLocation") or "",
                            "starRating": int(r.get("starRating") or 0),
                            "odds": odds,
                        })
                else:
                    # Fallback: outcomes filtered to Race Winner market, skip non-runners
                    winner_market_id = next(
                        (str(mkt["marketId"]) for mkt in res.get("markets", [])
                         if "Race Winner" in mkt.get("name", "") or "Win Only" in mkt.get("name", "")),
                        None
                    )
                    seen = set()
                    runners = []
                    for outcome in res.get("outcomes", []):
                        if winner_market_id and str(outcome.get("marketId")) != winner_market_id:
                            continue
                        if outcome.get("nonRunner"):
                            continue
                        name = outcome.get("outcomeName") or outcome.get("name") or "Unknown"
                        if name in seen:
                            continue
                        seen.add(name)
                        outcome_id = str(outcome.get("outcomeId") or "")
                        info = outcome.get("additionalInfo") or {}
                        runners.append({
                            "outcomeId": outcome_id,
                            "name": name,
                            "outcomeName": name,
                            "jockeyName": info.get("JockeyName") or "TBA",
                            "trainerName": info.get("TrainerName") or "TBA",
                            "age": info.get("Age") or "U",
                            "weight": info.get("Weight") or "0",
                            "form": info.get("Form") or "",
                            "number": str(info.get("Number") or "0"),
                            "draw": int(info.get("Draw") or 0),
                            "timeForm": info.get("TimeForm") or "",
                            "imageLocation": info.get("ImageLocation") or "",
                            "starRating": int(info.get("StarRating") or 0),
                            "odds": price_map.get(outcome_id, 5.0),
                        })

                if not runners:
                    continue

                name_text = event_obj.get("name") or event_obj.get("displayName") or ""

                events[str(eid)] = {
                    "id": eid,
                    "en": f"{reg_name}: {league}",
                    "course": league,
                    "name": name_text,
                    "t": race_time,
                    "st": race_time,
                    "raceNumber": race_num,
                    "isFinished": False,
                    "runners": runners,
                }
            except Exception as e:
                logger.error(f"Error parsing event {det.get('eventId', '?')}: {e}")

        return {"events": events, "count": len(events)}

    async def get_races(self) -> List[ScrapedRace]:
        """Legacy compatibility wrapper for ScrapedRace objects."""
        snapshot = await self.get_snapshot_format()
        return self._parse_snapshot(snapshot)

    def _parse_snapshot(self, snapshot: Dict) -> List[ScrapedRace]:
        """Convert AdaptiveMonitor snapshot format (flat schema) to ScrapedRace objects."""
        scraped_races = []
        events = snapshot.get("events", {})

        for eid, e in events.items():
            try:
                track_raw = e.get("en", "Unknown")
                # Strip region prefix e.g. "South Africa: Turffontein" → "Turffontein"
                track = (
                    track_raw.split(":")[-1].strip() if ":" in track_raw else track_raw
                )
                runners = []
                for r in e.get("runners", []):
                    odds_val = r.get("odds", "SP")
                    try:
                        odds_decimal = float(odds_val) if odds_val != "SP" else 5.0
                    except (ValueError, TypeError):
                        odds_decimal = 5.0
                    runners.append(
                        ScrapedRunner(
                            horse_name=r.get("outcomeName") or r.get("name") or "Unknown",
                            odds_decimal=odds_decimal,
                            jockey=r.get("jockeyName") or "TBA",
                            trainer=r.get("trainerName") or "TBA",
                            barrier=int(r.get("draw") or 0),
                            form=r.get("form") or "",
                        )
                    )

                if runners:
                    scraped_races.append(
                        ScrapedRace(
                            track=track,
                            race_number=int(e.get("raceNumber", 1)),
                            race_time=e.get("t", "12:00"),
                            distance=1600,
                            track_condition="Good",
                            runners=runners,
                        )
                    )
            except Exception as ex:
                logger.debug(f"Error parsing snapshot event {eid}: {ex}")
                continue

        return scraped_races
