import httpx
import logging
import asyncio
import json
import re
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .tab4racing import ScrapedRace, ScrapedRunner
from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("betway-api")

class BetwayAPI:
    BASE_URL = "https://www.betway.co.za/sportsapi/v1/TrackRacing"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za"
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
                    ALLOWED = ["South Africa", "UK and Ireland", "Australia", "New Zealand", "USA", "Hong Kong", "Japan", "France"]
                    
                    for reg in data.get('regions', []):
                        if not any(a in reg.get('name', '') for a in ALLOWED):
                            continue
                        for e in reg.get('sportEvents', []):
                            if not e.get('isFinished', True):
                                event_ids.append((e['eventId'], reg.get('name'), e.get('league')))
                    
                    # Fetch all unfinished event details in parallel
                    tasks = []
                    for eid, reg_name, league in event_ids:
                        tasks.append(self._fetch_event_safe(client, eid, reg_name, league))

                    events_details = await asyncio.gather(*tasks)
                    # Filter out None values from failed fetches
                    events_details = [e for e in events_details if e]
                    
                    return {"status": "success", "details": events_details}
                except Exception as e:
                    logger.warning(f"Betway fetch attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
            return {"status": "error", "error": "Max retries reached"}

    async def _fetch_event_safe(self, client, eid, reg_name, league) -> Optional[Dict]:
        try:
            # Browser network trace shows plural 'eventIds' and no 'isVirtual' parameter
            url = f"{self.BASE_URL}/GetEvent?eventIds={eid}&marketGroupName=&countryCode=ZA"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                data['eventId'] = eid
                data['regionName'] = reg_name
                data['leagueName'] = league
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
                # Initialize variables early for scope safety
                eid = det.get('eventId')
                reg_name = det.get('regionName', 'Unknown')
                league = det.get('leagueName', 'Unknown')
                name_text = det.get("name") or det.get("displayName") or ""
                race_time = "00:00"
                start_time_str = det.get('advertisedStartTime')
                if start_time_str:
                    try:
                        race_time = start_time_str.split('T')[1][:5]
                    except:
                        pass
                race_num = det.get('sportSpecificProperties', {}).get('raceNumber', 0)
                
                # Metadata extraction
                res = det.get("result", det)
                price_map = {str(p.get("outcomeId")): p.get("priceDecimal", 5.0) for p in res.get("prices", [])}

                runners = []
                seen_outcome_ids = set()
                for outcome in res.get("outcomes", []):
                    outcome_id = str(outcome.get("outcomeId") or outcome.get("id"))
                    if outcome_id in seen_outcome_ids:
                runners = []
                seen_horse_names = set()
                for outcome in res.get("outcomes", []):
                    horse_name = outcome.get("outcomeName") or outcome.get("name") or "Unknown"
                    if horse_name in seen_horse_names:
                        continue
                    seen_horse_names.add(horse_name)
                    outcome_id = str(outcome.get("outcomeId") or outcome.get("id"))
                    info = outcome.get("additionalInfo", {})
                    odds = float(price_map.get(outcome_id, 5.0))
                    runner_obj = {
                        "outcomeId": outcome_id,
                        "name": horse_name,
                        "outcomeName": horse_name,
                        "jockeyName": info.get("JockeyName") or "TBA",
                        "trainerName": info.get("TrainerName") or "TBA",
                        "age": info.get("Age") or "U",
                        "weight": info.get("Weight") or "0",
                        "form": info.get("Form") or "",
                        "number": info.get("Number") or "0",
                        "draw": info.get("Draw") or 0,
                        "timeForm": info.get("TimeForm") or "",
                        "imageLocation": info.get("ImageLocation") or "",
                        "odds": odds
                    }
                    if "StarRating" in info:
                        runner_obj["starRating"] = info.get("StarRating")
                    runners.append(runner_obj)
                    "st": race_time,
                    "raceNumber": int(race_num),
                    "isFinished": False,
                    "runners": runners
                }
            except Exception as e:
                logger.error(f"Error parsing event detail for {det.get('eventId', 'Unknown')}: {e}")

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
                track = track_raw.split(":")[-1].strip() if ":" in track_raw else track_raw
                runners = []
                for r in e.get("runners", []):
                    odds_val = r.get("odds", "SP")
                    try:
                        odds_decimal = float(odds_val) if odds_val != "SP" else 5.0
                    except (ValueError, TypeError):
                        odds_decimal = 5.0
                    runners.append(ScrapedRunner(
                        horse_name=r.get("outcomeName") or r.get("name") or "Unknown",
                        odds_decimal=odds_decimal,
                        jockey=r.get("jockeyName") or "TBA",
                        trainer=r.get("trainerName") or "TBA",
                        barrier=int(r.get("draw", 0)),
                        form=r.get("form") or "",
                        age=r.get("age") or "U",
                        weight=r.get("weight") or "0",
                        number=r.get("number") or "0"
                    ))
                
                if runners:
                    scraped_races.append(ScrapedRace(
                        track=track,
                        race_number=int(e.get("raceNumber", 1)),
                        race_time=e.get("t", "12:00"),
                        distance=1600,
                        track_condition="Good",
                        runners=runners
                    ))
            except Exception as ex:
                logger.debug(f"Error parsing snapshot event {eid}: {ex}")
                continue
                
        return scraped_races
    