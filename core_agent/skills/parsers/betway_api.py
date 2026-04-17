import httpx
import logging
import asyncio
from typing import Dict, Any

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
                    for eid in event_ids[:50]: # Optimized to 50
                        det_resp = await client.get(f"{self.BASE_URL}/GetEvent?eventId={eid}&marketType=Race%20Winner&marketGroupname=Race%20Winner&isVirtual=false&countryCode=ZA")
                        events_details.append(det_resp.json())
                    
                    return {"daily": data, "details": events_details}
                except Exception as e:
                    logger.warning(f"Attempt {attempt+1} failed: {e}")
                    await asyncio.sleep(2 ** attempt)
            return {"status": "error", "error": "Max retries reached"}
