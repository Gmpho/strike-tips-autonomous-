import httpx
import json
import asyncio


async def debug_betway_event(event_id):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za",
    }
    url = f"https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds={event_id}&marketGroupName=&countryCode=ZA"
    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            outcomes = data.get("result", {}).get("outcomes", [])
            if outcomes:
                print("First outcome keys:", outcomes[0].keys())
                print("First outcome full content:")
                print(json.dumps(outcomes[0], indent=2))

                # Check if there are other interesting fields in 'result'
                result = data.get("result", {})
                print("Result keys:", result.keys())
        else:
            print(f"Error: {resp.status_code}")


if __name__ == "__main__":
    asyncio.run(debug_betway_event(16681998))
