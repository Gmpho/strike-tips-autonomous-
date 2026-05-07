import json


def verify():
    file_path = "data/market_snapshot_latest.json"
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Snapshot file not found at {file_path}")
        return

    events = data.get("events", {})
    if not events:
        print("Snapshot is empty!")
        return

    print(f"Total events found: {len(events)}")
    # Check a few events
    for eid, e in list(events.items())[:5]:
        print(f"Event {eid}: {e.get('en')}")
        print(f"  Race Number: {e.get('raceNumber')}")
        print(f"  Time: {e.get('t')}")
        runners = e.get("runners", [])
        if runners:
            # Check the first runner for metadata
            r = runners[0]
            print(f"  First Runner: {r.get('name')}")
            print(f"  Jockey: {r.get('jockeyName')}")
            print(f"  Star Rating: {r.get('starRating', 'NOT FOUND')}")
        else:
            print("  No runners found.")
        print("-" * 20)


if __name__ == "__main__":
    verify()
