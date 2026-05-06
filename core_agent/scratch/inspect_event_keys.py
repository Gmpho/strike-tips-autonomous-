import httpx
import json
import asyncio

async def inspect():
    eid = 16693385
    url = f"https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds={eid}&marketGroupName=&countryCode=ZA"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        data = resp.json()
        
        # Result contains events list
        events = data.get('result', {}).get('events', [])
        if events:
            det = events[0]
            print(f"--- Raw Event {eid} Keys ---")
            print(json.dumps(list(det.keys()), indent=2))
            print("\n--- Raw Event Structure ---")
            print(json.dumps(det, indent=2))

if __name__ == "__main__":
    asyncio.run(inspect())
