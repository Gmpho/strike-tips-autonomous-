"""Duplicate track+race-number collapsing (2026-11-23 prod flip).

A stale local image published a 420-race card to prod KV that contained 101
pairs of (course, raceNumber) — e.g. two Turffontein R8s, one of them from an
earlier day. Carry-forward and the durable registry restore by event id, so
nothing collapsed them. These tests pin the dedupe contract.
"""

from core_agent.core import snapshot_writer as sw


def _future(seconds: int = 3600) -> float:
    import time

    return time.time() + seconds


def test_duplicate_track_and_race_number_keeps_the_live_one():
    events = {
        # stale leftover: already expired, no prices
        "111": {
            "en": "South Africa: Turffontein",
            "course": "Turffontein",
            "raceNumber": 8,
            "t": "14:30",
            "expires_at": _future(-7200),
            "runners": [{"name": "Old Horse", "odds": "SP"}],
        },
        # today's race: still live, has prices
        "999": {
            "en": "South Africa: Turffontein",
            "course": "Turffontein",
            "raceNumber": 8,
            "t": "14:30",
            "expires_at": _future(),
            "runners": [{"name": "New Horse", "odds": 3.5}],
        },
    }
    out = sw._dedupe_races(events)
    assert list(out) == ["999"]
    assert out["999"]["runners"][0]["name"] == "New Horse"


def test_different_tracks_keep_their_own_race_numbers():
    events = {
        "1": {"course": "Turffontein", "raceNumber": 1, "expires_at": _future()},
        "2": {"course": "Vaal", "raceNumber": 1, "expires_at": _future()},
    }
    assert len(sw._dedupe_races(events)) == 2


def test_events_without_a_race_number_are_never_collapsed():
    events = {
        "1": {"en": "USA: Gulfstream", "t": "18:00"},
        "2": {"en": "USA: Gulfstream", "t": "18:30"},
    }
    assert len(sw._dedupe_races(events)) == 2


def test_identity_falls_back_to_the_display_name_track():
    events = {
        "1": {"en": "South Africa: Scottsville", "raceNumber": 4, "expires_at": _future()},
        "2": {"en": "South Africa:  Scottsville ", "raceNumber": 4, "expires_at": _future()},
    }
    out = sw._dedupe_races(events)
    assert len(out) == 1
    # Tie on every rank except the event id: the higher (newer) id wins.
    assert list(out) == ["2"]


def test_sanitize_snapshot_applies_dedupe():
    import datetime as _dt

    off_t = (_dt.datetime.now(_dt.UTC) + _dt.timedelta(hours=2)).strftime("%H:%M")
    state = {
        "events": {
            "111": {
                "course": "Cork",
                "raceNumber": 3,
                "t": off_t,
                "expires_at": _future(-3600),
            },
            "999": {
                "course": "Cork",
                "raceNumber": 3,
                "t": off_t,
                "expires_at": _future(),
                "runners": [{"odds": 2.4}],
            },
        }
    }
    out = sw.sanitize_snapshot(state, source="probe")
    assert out["count"] == 1
    assert "999" in out["events"]
