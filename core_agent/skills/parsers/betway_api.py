import logging
import asyncio
import re
import random
from typing import Dict, Any, List, Optional
from datetime import datetime
from .tab4racing import ScrapedRace, ScrapedRunner
from core_agent.core.http_client import get_async_client

logger = logging.getLogger("betway-api")


class BetwayAPI:
    BASE_URL = "https://www.betway.co.za/sportsapi/v1/TrackRacing"

    async def fetch_racing_data(self) -> Dict[str, Any]:
        """Fetch raw racing data from Betway's TrackRacing (TAB) API."""
        client = get_async_client(timeout=90.0, resolve_hosts={"www.betway.co.za"})
        bw_headers = {
            "Referer": "https://www.betway.co.za/sport/horse-racing",
            "Origin": "https://www.betway.co.za",
        }
        backoff = [5, 15, 30]
        for attempt in range(3):
            try:
                daily_url = f"{self.BASE_URL}/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2"
                daily_resp = await client.get(daily_url, headers=bw_headers)
                daily_resp.raise_for_status()
                data = daily_resp.json()

                event_ids = []
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

                sem = asyncio.Semaphore(10)
                tasks = [
                    self._fetch_event_safe(client, eid, reg_name, league, sem)
                    for eid, reg_name, league in event_ids
                ]

                events_details = await asyncio.gather(*tasks)
                events_details = [e for e in events_details if e]

                return {"status": "success", "details": events_details}
            except Exception as e:
                logger.warning(f"Betway fetch attempt {attempt+1} failed: {e}")
                await asyncio.sleep(backoff[attempt])
        return {"status": "error", "error": "Max retries reached"}

    async def _fetch_event_safe(self, client, eid, reg_name, league, sem=None) -> Optional[Dict]:
        try:
            url = f"{self.BASE_URL}/GetEvent?eventIds={eid}&marketGroupName=&countryCode=ZA"
            bw_headers = {
                "Referer": "https://www.betway.co.za/sport/horse-racing",
                "Origin": "https://www.betway.co.za",
            }
            if sem:
                async with sem:
                    await asyncio.sleep(random.uniform(0.05, 0.3))
                    resp = await client.get(url, headers=bw_headers)
            else:
                resp = await client.get(url, headers=bw_headers)
            if resp.status_code == 200:
                data = resp.json()
                data["eventId"] = eid
                data["regionName"] = reg_name
                data["leagueName"] = league
                return data
        except Exception as e:
            logger.debug(f"Failed to fetch event {eid}: {e}")
        return None

    def _count_priced(self, runners: list) -> int:
        return sum(1 for r in runners if isinstance(r.get("odds"), (int, float)) and r["odds"] > 0)

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
                    str(p["outcomeId"]): float(p.get("priceDecimal", 0))
                    for p in res.get("prices", [])
                    if isinstance(p, dict) and "outcomeId" in p
                }

                # --- Find the Win market ID (varies by region: "Race Winner", "To Win", "Win") ---
                _win_keywords = ("Race Winner", "Win Only", "To Win", "Winner", "Win")
                winner_market_id = next(
                    (str(mkt["marketId"]) for mkt in res.get("markets", [])
                     if any(k in mkt.get("name", "") for k in _win_keywords)),
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
                        odds = price_map.get(outcome_id)
                        if odds is None:
                            horse_name_key = (r.get("outcomeName") or r.get("name") or "").lower()
                            odds = name_price_map.get(horse_name_key, "SP")
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
                        odds = price_map.get(outcome_id, "SP")
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
                            "odds": odds,
                        })

                if not runners:
                    continue

                priced = self._count_priced(runners)
                if priced < len(runners):
                    logger.info("Betway %s R%d: %d/%d runners have odds (rest SP)", league, race_num, priced, len(runners))

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
