import httpx
import asyncio
import json


async def test():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za",
    }
    eid = "16681978"
    url = f"https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds={eid}&marketGroupName=&countryCode=ZA"

    async with httpx.AsyncClient(headers=headers) as client:
        resp = await client.get(url)
        data = resp.json()
        result = data.get("result", {})

        print("Keys in result:", result.keys())

        prices = result.get("prices", [])
        print(f"Number of prices: {len(prices)}")
        if prices:
            print("First price sample:", prices[0])

        outcomes = result.get("outcomes", [])
        print(f"Number of outcomes: {len(outcomes)}")
        if outcomes:
            print("First outcome sample keys:", outcomes[0].keys())
            print("First outcome name:", outcomes[0].get("name"))


if __name__ == "__main__":
    asyncio.run(test())
