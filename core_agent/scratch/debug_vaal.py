import httpx
import json
import asyncio

async def debug_vaal():
    event_id = 16686516
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za"
    }
    url = f"https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds={event_id}&marketGroupName=&countryCode=ZA"
    
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        data = resp.json()
        
        # Look for raceEventDetails
        events = data.get('result', {}).get('events', [])
        if events:
            print(f"Event keys: {list(events[0].keys())}")
            # Check for details
            details = events[0].get('raceEventDetails')
            if details:
                print(f"RaceEventDetails keys: {list(details.keys())}")
                print(f"Racers count: {len(details.get('racers', []))}")
                if details.get('racers'):
                    print(f"First racer sample: {json.dumps(details['racers'][0], indent=2)}")
            else:
                print("raceEventDetails is null or missing")
        else:
            print("No events in result")

if __name__ == "__main__":
    asyncio.run(debug_vaal())
