import httpx
import json
import asyncio


async def test_betway_plural():
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
        "Referer": "https://www.betway.co.za/sport/horse-racing",
        "Origin": "https://www.betway.co.za",
    }

    # Plural eventIds
    url_plural = "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventIds=16684374&marketGroupName=&countryCode=ZA"
    # Singular eventId (current code)
    url_singular = "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventId=16684374&isVirtual=false&countryCode=ZA"

    async with httpx.AsyncClient(headers=headers) as client:
        print(f"Testing Plural: {url_plural}")
        resp_p = await client.get(url_plural)
        data_p = resp_p.json()
        print(
            f"Plural Markets Count: {len(data_p.get('result', {}).get('markets', []))}"
        )

        print(f"\nTesting Singular: {url_singular}")
        resp_s = await client.get(url_singular)
        data_s = resp_s.json()
        print(
            f"Singular Markets Count: {len(data_s.get('result', {}).get('markets', []))}"
        )


if __name__ == "__main__":
    asyncio.run(test_betway_plural())
