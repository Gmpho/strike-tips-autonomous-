import httpx
import logging
import asyncio
import json
import re
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from .tab4racing import ScrapedRace, ScrapedRunner
from .oddschecker_scraper import OddscheckerScraper
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
        async with httpx.AsyncClient(headers=self.HEADERS, timeout=30.0) as client:
            for attempt in range(3):
                try:
                    daily_resp = await client.get(f"{self.BASE_URL}/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2")
                    data = daily_resp.json()
                    
                    event_ids = []
                    for reg in data.get('regions', []):
                        for e in reg.get('sportEvents', []):
                            if not e.get('isFinished', True):
                                event_ids.append(e['eventId'])
                    
                    events_details = []
                    # Limit to 30 events for performance
                    for eid in event_ids[:30]: 
                        det_resp = await client.get(f"{self.BASE_URL}/GetEvent?eventId={eid}&marketType=Race%20Winner&marketGroupname=Race%20Winner&isVirtual=false&countryCode=ZA")
                        events_details.append(det_resp.json())
                    
                    return {"daily": data, "details": events_details}
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
            return {"status": "error", "error": "Max retries reached"}

    async def get_races(self) -> List[ScrapedRace]:
        """Fetch races. Primary: Market Snapshot (from Playwright), Fallback: Direct API."""
        
        # 1. Try Market Snapshot First (Most robust, includes OC fusion)
        if os.path.exists(MARKET_SNAPSHOT_PATH):
            try:
                with open(MARKET_SNAPSHOT_PATH, 'r') as f:
                    snapshot = json.load(f)
                    
                timestamp_str = snapshot.get("timestamp")
                if timestamp_str:
                    ts = datetime.fromisoformat(timestamp_str)
                    # If snapshot is fresh (last 10 mins), use it
                    if datetime.now() - ts < timedelta(minutes=10):
                        logger.info(f"🔄 Using fresh market snapshot from {timestamp_str}")
                        return self._parse_snapshot(snapshot)
            except Exception as e:
                logger.warning(f"Failed to read market snapshot: {e}")

        # 2. Fallback to direct API fetch if snapshot is missing or stale
        logger.info("🌐 Snapshot stale or missing, falling back to direct Betway API fetch")
        raw_data = await self.fetch_racing_data()
        if raw_data.get("status") == "error":
            return []

        # Get live odds from Oddschecker
        oc_scraper = OddscheckerScraper()
        oc_odds = await oc_scraper.get_latest_odds()

        scraped_races = []
        for det in raw_data.get("details", []):
            try:
                event = det.get("event", {})
                if not event: continue

                track = event.get("regionName", "Unknown")
                race_num_match = re.search(r"Race (\d+)", event.get("eventName", ""))
                race_number = int(race_num_match.group(1)) if race_num_match else 1
                
                # Parse time
                start_time_raw = event.get("eventStartDate", "")
                race_time = "12:00"
                if start_time_raw:
                    dt = datetime.fromisoformat(start_time_raw.replace('Z', '+00:00'))
                    race_time = dt.strftime("%H:%M")

                runners = []
                # Find the 'Race Winner' market
                markets = det.get("markets", [])
                winner_market = next((m for m in markets if m.get("name") == "Race Winner"), None)
                
                if winner_market:
                    for outcome in winner_market.get("outcomes", []):
                        horse_name = outcome.get("name", "Unknown")
                        # Try to get odds from Oddschecker first
                        odds = 5.0 # Default
                        
                        # Fuzzy match odds from Oddschecker
                        matched_odds = False
                        for oc_race, oc_horses in oc_odds.items():
                            if horse_name in oc_horses:
                                odds = oc_horses[horse_name]
                                matched_odds = True
                                break
                        
                        # Fallback to Betway's own odds if OC failed
                        if not matched_odds:
                            odds = float(outcome.get("price", 5.0))

                        runners.append(ScrapedRunner(
                            horse_name=horse_name,
                            odds_decimal=odds,
                            jockey=outcome.get("jockeyName"),
                            trainer=outcome.get("trainerName"),
                            barrier=outcome.get("draw")
                        ))

                if runners:
                    scraped_races.append(ScrapedRace(
                        track=track,
                        race_number=race_number,
                        race_time=race_time,
                        distance=event.get("distance", 1600),
                        track_condition=event.get("going", "Good"),
                        runners=runners
                    ))
            except Exception as e:
                logger.error(f"Error parsing Betway event: {e}")
                continue

        return scraped_races

    def _parse_snapshot(self, snapshot: Dict) -> List[ScrapedRace]:
        """Convert AdaptiveMonitor snapshot format to ScrapedRace objects."""
        scraped_races = []
        # Handle cases where events is a list or dict
        events = snapshot.get("events", {})
        event_items = events.items() if isinstance(events, dict) else enumerate(events)
        
        for eid, e in event_items:
            try:
                # Handle cases where e might be a list item if events was a list
                if isinstance(e, list): e = e[1]
                
                # 'en' format is often 'Region: Course'
                track = e.get("course", "Unknown")
                runners = []
                for r in e.get("runners", []):
                    runners.append(ScrapedRunner(
                        horse_name=r.get("name", "Unknown"),
                        odds_decimal=float(r.get("odds", 5.0)),
                        jockey=r.get("jockeyName"),
                        trainer=r.get("trainerName"),
                        barrier=r.get("draw"),
                        form=r.get("form")
                    ))
                
                if runners:
                    scraped_races.append(ScrapedRace(
                        track=track,
                        race_number=int(e.get("raceNumber", 1)),
                        race_time=e.get("t", "12:00"),
                        distance=1600, # Default if not in snapshot
                        track_condition="Good",
                        runners=runners
                    ))
            except Exception as ex:
                logger.debug(f"Error parsing snapshot event {eid}: {ex}")
                continue
                
        return scraped_races
