import asyncio
import httpx
import json

async def check_markets(event_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za"
    }
    url = f"https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventId={event_id}&isVirtual=false&countryCode=ZA"
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        data = resp.json()
        
        # Save for deep inspection
        with open("data/debug_event_raw.json", "w") as f:
            json.dump(data, f, indent=2)
            
        result = data.get("result", {})
        print(f"--- Response Structure for Event {event_id} ---")
        print(f"Keys in root: {list(data.keys())}")
        print(f"Keys in result: {list(result.keys())}")
        
        events = result.get("events", [])
        if events:
            print(f"Number of events in result: {len(events)}")
            print(f"Keys in first event: {list(events[0].keys())}")
            if "sportSpecificProperties" in events[0]:
                print(f"Sport props: {events[0]['sportSpecificProperties']}")
            if "markets" in events[0]:
                print(f"Number of markets in events[0]: {len(events[0]['markets'])}")
            if "outcomes" in events[0]:
                print(f"Number of outcomes in events[0]: {len(events[0]['outcomes'])}")
        
        markets = result.get("markets", [])
        outcomes = result.get("outcomes", [])
        
        print(f"Number of root markets: {len(markets)}")
        print(f"Number of root outcomes: {len(outcomes)}")

if __name__ == "__main__":
    import sys
    event_id = int(sys.argv[1]) if len(sys.argv) > 1 else 16686516
    asyncio.run(check_markets(event_id))
