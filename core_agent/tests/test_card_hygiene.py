"""Card hygiene: no earlier-day races, no duplicate rows (2026-11-23).

The local card swung 349 ↔ 31 ↔ 272 and showed Saturday's Scottsville races on a
Monday with no SA meeting. Two causes:

* ``t`` is a wall clock with no date, so a carried-forward race re-anchors to
  today at the same HH:MM and never expires.
* the monitor wrote its state straight to disk after the id-based carry-forward
  and registry merges, so rows the dedupe had just dropped came straight back.

These tests pin the daily-card gate, the absolute lifetime stamp, and the
sanitise-after-merge composition.
"""

import json
import time
from datetime import datetime, timedelta, timezone

from core_agent.core import adaptive_odds_monitor as mon
from core_agent.core.snapshot_writer import sanitize_snapshot
from core_agent.skills.parsers import betway_api as bw


def _future_t(minutes=90):
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).strftime("%H:%M")


def test_daily_ids_empty_when_cache_is_stale(tmp_path, monkeypatch):
    path = tmp_path / "daily.json"
    monkeypatch.setattr(bw, "_DAILY_CACHE_PATH", str(path))
    bw._save_daily_cache({"regions": [{"name": "USA", "sportEvents": [{"eventId": 7}]}]})
    assert bw.daily_event_ids() == {7}
    # Backdate the stored stamp beyond the parser's own trust window.
    old = time.time() - (bw._DAILY_CACHE_MAX_AGE_SECS + 600)
    path.write_text(json.dumps({"ts": old, "payload": {"regions": [{"sportEvents": [{"eventId": 7}]}]}}))
    assert bw.daily_event_ids() == set(), "a stale list must never empty the card"


def test_yesterdays_daily_list_never_prunes_todays_card(tmp_path, monkeypatch):
    path = tmp_path / "daily.json"
    monkeypatch.setattr(bw, "_DAILY_CACHE_PATH", str(path))
    now = datetime.now(timezone.utc)
    yesterday = now - timedelta(days=1)
    path.write_text(json.dumps({
        "ts": yesterday.timestamp(),
        "payload": {"regions": [{"sportEvents": [{"eventId": 7}]}]},
    }))
    assert bw.daily_event_ids(max_age_seconds=48 * 3600) == set()


def test_daily_ids_missing_cache_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(bw, "_DAILY_CACHE_PATH", str(tmp_path / "nope.json"))
    assert bw.daily_event_ids() == set()


def test_races_absent_from_todays_card_are_dropped(monkeypatch):
    monkeypatch.setattr(bw, "daily_event_ids", lambda *a, **k: {101, 102})
    state = {
        "events": {
            "101": {"en": "UK and Ireland: Huntingdon", "t": _future_t()},
            "102": {"en": "USA: Zia Park", "t": _future_t()},
            # Saturday's Scottsville card — same wall clock, different day.
            "999": {"en": "South Africa: Scottsville", "raceNumber": 2, "t": _future_t()},
        }
    }
    out = mon._drop_stale_card_entries(state)
    assert set(out["events"]) == {"101", "102"}
    assert out["count"] == 2


def test_betfair_spine_rows_survive_the_daily_gate(monkeypatch):
    monkeypatch.setattr(bw, "daily_event_ids", lambda *a, **k: {101})
    state = {
        "events": {
            "101": {"en": "USA: Zia Park", "t": _future_t()},
            "bf:1.265866347": {"en": "GB: Lingfield", "t": _future_t(), "source": "betfair"},
        }
    }
    out = mon._drop_stale_card_entries(state)
    assert "bf:1.265866347" in out["events"]


def test_unavailable_daily_list_never_empties_the_card(monkeypatch):
    monkeypatch.setattr(bw, "daily_event_ids", lambda *a, **k: set())
    state = {"events": {"101": {"en": "USA: Zia Park", "t": _future_t()}}}
    out = mon._drop_stale_card_entries(state)
    assert set(out["events"]) == {"101"}


def test_lifetime_stamp_expires_a_race_whose_clock_looks_upcoming():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    ancient = (now - timedelta(hours=48)).replace(tzinfo=timezone.utc).timestamp()
    events = {
        "old": {
            "en": "South Africa: Scottsville",
            "raceNumber": 2,
            "t": _future_t(120),  # looks like a race later today
            "card_since": ancient,
        }
    }
    out = mon._close_overdue_races(events)
    assert out == {}, "a 48h-old race must not survive on a re-anchored wall clock"


def test_lifetime_stamp_is_set_once_and_preserved():
    events = {"r": {"en": "USA: Zia Park", "raceNumber": 1, "t": _future_t()}}
    first = mon._close_overdue_races(events)
    stamp = first["r"]["card_since"]
    assert stamp > 0
    second = mon._close_overdue_races(first)
    assert second["r"]["card_since"] == stamp, "the stamp must never be refreshed"


def test_recent_race_is_kept():
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent = (now - timedelta(hours=2)).replace(tzinfo=timezone.utc).timestamp()
    events = {
        "r": {
            "en": "USA: Zia Park",
            "raceNumber": 1,
            "t": _future_t(),
            "card_since": recent,
        }
    }
    assert "r" in mon._close_overdue_races(events)


def test_sanitising_after_a_merge_removes_reintroduced_duplicates():
    """The monitor's final gate: carry-forward re-adds rows, sanitize removes them."""
    live = {
        "999": {
            "course": "Huntingdon",
            "raceNumber": 1,
            "t": _future_t(),
            "runners": [{"name": "A", "odds": 3.5}],
            "expires_at": time.time() + 3600,
        }
    }
    # A carry-forward merge brings back the same race under an older id.
    merged = dict(live)
    merged["111"] = {
        "course": "Huntingdon",
        "raceNumber": 1,
        "t": _future_t(),
        "runners": [{"name": "A", "odds": "SP"}],
        "expires_at": time.time() + 3600,
    }
    out = sanitize_snapshot({"events": merged}, source="monitor")
    assert out["count"] == 1
    assert "999" in out["events"], "the priced row wins its slot"
