import asyncio
import json
from core_agent.skills.parsers.betway_api import BetwayAPI


async def test():
    api = BetwayAPI()
    snapshot = await api.get_snapshot_format()

    print(f"Count: {snapshot.get('count')}")
    events = snapshot.get("events", {})
    for eid, e in list(events.items())[:3]:
        print(f"Event {eid}: {e.get('en')}")
        print(f"  Runners: {len(e.get('runners'))}")
        if e.get("runners"):
            print(
                f"  First runner: {e['runners'][0]['name']} - Odds: {e['runners'][0]['odds']}"
            )


if __name__ == "__main__":
    asyncio.run(test())
