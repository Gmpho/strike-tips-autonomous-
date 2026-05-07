import httpx
import json
import asyncio


async def main():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za",
    }
    url = "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds=16684377&marketGroupName=&countryCode=ZA"

    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        data = resp.json()

        # Focus on outcomes
        outcomes = data.get("result", {}).get("outcomes", [])
        if not outcomes:
            print("No outcomes found")
            return

        print(f"Total outcomes: {len(outcomes)}")

        # Sample one outcome with details
        for o in outcomes:
            name = o.get("name")
            props = o.get("sportSpecificProperties", {})
            jockey = o.get("jockeyName")
            trainer = o.get("trainerName")

            if jockey or trainer or props:
                print(f"Horse: {name}")
                print(f"  Jockey: {jockey}")
                print(f"  Trainer: {trainer}")
                print(f"  Props: {json.dumps(props, indent=2)}")
                break
        else:
            print("No jockey/trainer/props found in ANY outcome")
            if outcomes:
                print("Keys in one outcome:", list(outcomes[0].keys()))


if __name__ == "__main__":
    asyncio.run(main())
