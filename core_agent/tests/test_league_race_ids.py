"""A race_id of 'None' must never leak one pick onto every race.

On 2026-11-25 the snapshot's events have no ``id`` field, so the league races
endpoint built every race_id from ``str(event["id"])`` -> "None". One pick
submitted during that window appeared on all 109 races on the card.
"""

import asyncio
import json
import os
import tempfile
from pathlib import Path

import core_agent.routes.league as league


SNAP = {
    "timestamp": "2026-11-25T07:00:00",
    "events": {
        "bf:1.1": {
            "course": "Kenilworth",
            "raceNumber": 1,
            "runners": [{"name": "One Dawn", "number": 3}],
        },
        "bf:1.2": {
            "course": "Kenilworth",
            "raceNumber": 2,
            "runners": [{"name": "Mosaic World", "number": 12}],
        },
    },
}


def _harness():
    tmp = tempfile.mkdtemp()
    league.DATA_DIR = Path(tmp)
    league._sync_volume = lambda: None
    with open(Path(tmp) / "market_snapshot_latest.json", "w") as f:
        json.dump(SNAP, f)
    league.PICKS_LOG = os.path.join(tmp, "league_picks.jsonl")
    return tmp


def test_race_ids_come_from_snapshot_keys_not_missing_id_field():
    _harness()
    out = asyncio.run(league.races(date=None, region=None))

    races = out["races"]
    assert [r["race_id"] for r in races] == ["bf:1.1", "bf:1.2"]


def test_orphaned_none_pick_is_repaired_to_its_own_race():
    _harness()
    with open(league.PICKS_LOG, "w") as f:
        f.write(
            json.dumps(
                {
                    "race_id": "None",
                    "course": "Kenilworth",
                    "race_number": 1,
                    "runner_number": 3,
                    "runner_name": "One Dawn",
                    "user_id": "u1",
                    "entity_name": "A",
                }
            )
            + "\n"
        )

    races = asyncio.run(league.races(date=None, region=None))["races"]

    assert races[0]["crowd"] == {3: 1}
    assert len(races[0]["backers"]) == 1
    assert races[1]["crowd"] == {}
    assert races[1]["backers"] == []
