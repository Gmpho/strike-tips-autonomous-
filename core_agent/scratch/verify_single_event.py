import asyncio
import json
import httpx
from core_agent.skills.parsers.betway_api import BetwayAPI


async def test_single():
    api = BetwayAPI()
    async with httpx.AsyncClient(headers=api.HEADERS, timeout=30.0) as client:
        # Test event from user's output
        eid = 16681978
        reg_name = "UK and Ireland"
        league = "Cork"

        print(f"Fetching event {eid}...")
        det = await api._fetch_event_safe(client, eid, reg_name, league)

        if not det:
            print("Failed to fetch event detail.")
            return

        # Now simulate get_snapshot_format processing for this one event
        raw = {"status": "success", "details": [det]}

        # We can't easily call get_snapshot_format without it fetching EVERYTHING
        # So we just inspect the parsing logic here or copy-paste it

        # Or better, let's just mock the fetch_racing_data to return only this event
        original_fetch = api.fetch_racing_data

        async def mock_fetch():
            return raw

        api.fetch_racing_data = mock_fetch

        snapshot = await api.get_snapshot_format()

        events = snapshot.get("events", {})
        if str(eid) in events:
            e = events[str(eid)]
            print(f"Success! Event: {e.get('en')}")
            print(f"Time detected: {e.get('t')}")
            print(f"Runners found: {len(e.get('runners'))}")
            for r in e.get("runners")[:3]:
                print(f"  - {r['name']} (Odds: {r['odds']})")
        else:
            print("Event not found in snapshot events map.")


if __name__ == "__main__":
    asyncio.run(test_single())
