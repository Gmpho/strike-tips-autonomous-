"""Pick submission must survive a card with no off time (Nov-2026).

The HUD posts /api/league/picks. Betfair's date stamp on a race is
intermittent, so the card sometimes reached the client with off_iso=null and
the pick died on Pydantic's "Input should be a valid string" — the punter
could see the runner, tap it, and get a validation error instead of a pick.

Pinned here:
* the server rebuilds the off time from the snapshot when the client has none;
* /races always hands the client a usable off_iso;
* a runner with no name is a clear 422, never a Pydantic type error.
"""
import json
import os

import pytest
from fastapi import HTTPException

from core_agent.routes import league as lg


def _snap(tmp_path, events, timestamp="2026-11-10T06:30:00"):
    path = os.path.join(str(tmp_path), "market_snapshot_latest.json")
    with open(path, "w") as f:
        json.dump({"events": events, "timestamp": timestamp}, f)
    return path


def test_off_iso_prefers_the_betfair_stamp():
    snap = {"events": {"1": {"id": 1, "course": "Kenilworth", "t": "11:07",
                             "bf_event_date": "2026-11-10", "bf_off_time": "11:07"}},
            "timestamp": "2026-11-10T06:30:00"}
    assert lg._snapshot_off_iso(snap, "1") == "2026-11-10T11:07:00+02:00"


def test_off_iso_falls_back_to_the_card_clock():
    """No Betfair stamp, but the card knows its own race time."""
    snap = {"events": {"1": {"id": 1, "course": "Kenilworth", "t": "11:07"}},
            "timestamp": "2026-11-10T06:30:00"}
    assert lg._snapshot_off_iso(snap, "1") == "2026-11-10T11:07:00+02:00"


def test_snapshot_day_is_sast_not_utc():
    # 23:30 UTC is already the next day in South Africa.
    snap = {"timestamp": "2026-11-09T23:30:00"}
    assert lg._snapshot_sast_day(snap) == "2026-11-10"


def test_off_iso_unknown_race_is_none():
    assert lg._snapshot_off_iso({"events": {}}, "999") is None


def test_pick_without_off_iso_is_accepted(tmp_path, monkeypatch):
    """The punter's pick must land even when the client had no off time."""
    import asyncio

    _snap(tmp_path, {"1": {"id": 1, "course": "Kenilworth", "t": "23:30"}})
    monkeypatch.setattr(lg, "DATA_DIR", tmp_path)
    monkeypatch.setattr(lg, "PICKS_LOG", os.path.join(str(tmp_path), "picks.jsonl"))
    monkeypatch.setattr(lg, "_load_user_picks", lambda: [])
    monkeypatch.setattr(lg, "_resolve_avatar", lambda uid, url: None)
    monkeypatch.setattr(lg, "_user_from_token", lambda token: ("uid-1", "punter", None))
    monkeypatch.setattr(lg, "_commit_volume", lambda: None)

    body = lg.PickIn(race_id="1", course="Kenilworth", race_number=2,
                      runner_number=4, runner_name="Peach Cobbler", odds=2.6)
    out = asyncio.run(lg.submit_pick(body, "Bearer test-token"))

    assert out["ok"] is True
    with open(os.path.join(str(tmp_path), "picks.jsonl")) as f:
        row = json.loads(f.readline())
    # Server rebuilt the missing off time instead of rejecting the pick.
    assert row["off_iso"] == "2026-11-10T23:30:00+02:00"
    assert row["runner_name"] == "Peach Cobbler"


def test_pick_without_a_runner_name_is_a_clear_error(tmp_path, monkeypatch):
    import asyncio

    monkeypatch.setattr(lg, "_user_from_token", lambda token: ("uid-1", "punter", None))
    monkeypatch.setattr(lg, "_load_user_picks", lambda: [])
    body = lg.PickIn(race_id="1", course="Kenilworth", race_number=2,
                      runner_number=4, odds=2.6)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(lg.submit_pick(body, "Bearer test-token"))
    assert exc.value.status_code == 422
    assert "name" in str(exc.value.detail).lower()
