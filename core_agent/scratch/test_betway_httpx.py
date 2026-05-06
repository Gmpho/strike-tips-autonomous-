import httpx
import json

BASE_URL = "https://www.betway.co.za/sportsapi/v1/TrackRacing"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Referer": "https://www.betway.co.za/sport/horse-racing",
    "Origin": "https://www.betway.co.za"
}

async def test_fetch():
    async with httpx.AsyncClient(headers=HEADERS, timeout=10.0) as client:
        # Try to get daily first to get an event ID
        url = f"{BASE_URL}/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2"
        print(f"Fetching: {url}")
        r = await client.get(url)
        print(f"Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            events = []
            for reg in data.get('regions', []):
                for e in reg.get('sportEvents', []):
                    events.append(e)
            
            if events:
                eid = events[0]['eventId']
                print(f"Found Event ID: {eid} ({events[0].get('name')})")
                url_event = f"{BASE_URL}/GetEvent?eventId={eid}&isVirtual=false&countryCode=ZA"
                print(f"Fetching Event: {url_event}")
                r_e = await client.get(url_event)
                print(f"Status: {r_e.status_code}")
                if r_e.status_code == 200:
                    print("SUCCESS! Data received.")
                    # print(json.dumps(r_e.json(), indent=2)[:500])
                else:
                    print(f"FAILED to fetch event: {r_e.text[:200]}")
            else:
                print("No events found in GetDaily")
        else:
            print(f"FAILED to fetch daily: {r.text[:200]}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_fetch())
