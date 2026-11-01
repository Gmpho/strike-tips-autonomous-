"""Dark-day gate + empty-cache recovery (Oct-2026 odds freeze).

Production: ``sanitize_snapshot`` prunes races whose off-time passed, so the
monitor's own file read back as zero events late at night. The cron gate read
that empty snapshot as "dark day" and returned before running the only writer
that could refresh it — the file froze at 21:05Z and no odds moved for 14h.
These tests pin the two halves of the recovery: the gate fails open on a
stale snapshot, and the cache stops serving a pruned-to-zero copy forever.
"""

import json
import os
import time
from datetime import datetime, timedelta

import pytest

from core_agent.core.racing_hours import DARK_DAY_MAX_AGE_SECS, has_meetings_today


def _stamp(age_secs: float) -> str:
    return (datetime.now() - timedelta(seconds=age_secs)).isoformat()


@pytest.fixture(autouse=True)
def _isolate_snapshot_cache():
    """These tests mutate module globals; never leak them into other files."""
    from core_agent.core import snapshot_cache as sc

    snapshot = dict(sc._snapshot)
    written_at = sc._snapshot_written_at
    source = sc._snapshot_source
    try:
        yield sc
    finally:
        sc._snapshot.clear()
        sc._snapshot.update(snapshot)
        sc._snapshot_written_at = written_at
        sc._snapshot_source = source


# ── gate ────────────────────────────────────────────────────────────────

def test_empty_but_stale_snapshot_fails_open():
    """The outage shape: 7 events pruned away, file hours old."""
    snap = {"events": {}, "count": 0, "timestamp": _stamp(14 * 3600)}
    assert has_meetings_today(snap) is True


def test_empty_and_fresh_snapshot_is_a_real_dark_day():
    snap = {"events": {}, "count": 0, "timestamp": _stamp(60)}
    assert has_meetings_today(snap) is False


def test_events_present_always_runs():
    snap = {"events": {"a": {}}, "timestamp": _stamp(14 * 3600)}
    assert has_meetings_today(snap) is True


def test_missing_or_bad_timestamp_keeps_old_behaviour():
    assert has_meetings_today({"events": {}}) is False
    assert has_meetings_today({"events": {}, "timestamp": "not-a-date"}) is False
    assert has_meetings_today({"events": {}, "timestamp": None}) is False


def test_age_guard_is_tunable():
    snap = {"events": {}, "timestamp": _stamp(600)}
    assert has_meetings_today(snap) is False
    assert has_meetings_today(snap, max_age_secs=300) is True
    assert DARK_DAY_MAX_AGE_SECS >= 900


def test_garbage_still_skips():
    assert has_meetings_today(None) is False
    assert has_meetings_today("garbage") is False


# ── restamped payloads must fall back to the cache's writer time ────────

def test_sanitized_payload_uses_cache_age_not_restamped_timestamp(monkeypatch):
    """The sanitizer stamps `timestamp` = now on every read, so a payload
    carrying `snapshot_source` looks fresh even when the file is hours old."""
    from core_agent.core import racing_hours as rh

    snap = {"events": {}, "count": 0, "timestamp": _stamp(0),
            "snapshot_source": "monitor"}
    monkeypatch.setattr(rh, "_cache_age_secs", lambda now: 14 * 3600)
    assert rh.has_meetings_today(snap) is True


def test_sanitized_payload_with_fresh_cache_age_skips(monkeypatch):
    from core_agent.core import racing_hours as rh

    snap = {"events": {}, "count": 0, "timestamp": _stamp(0),
            "snapshot_source": "monitor"}
    monkeypatch.setattr(rh, "_cache_age_secs", lambda now: 30.0)
    assert rh.has_meetings_today(snap) is False


# ── cache recovery ──────────────────────────────────────────────────────

def test_get_snapshot_refreshes_a_pruned_to_zero_cache(tmp_path, monkeypatch):
    from core_agent.core import snapshot_cache as sc

    path = tmp_path / "market_snapshot_latest.json"
    path.write_text(json.dumps({"events": {"r1": {"name": "Vaal R1"}},
                                "timestamp": _stamp(0)}))
    monkeypatch.setattr(sc, "MARKET_SNAPSHOT_PATH", str(path))
    monkeypatch.setattr(sc, "_sanitize", lambda data, source: data)

    # Poison the cache exactly the way the outage did: truthy but empty.
    sc._snapshot.clear()
    sc._snapshot.update({"events": {}, "count": 0, "timestamp": _stamp(0)})
    monkeypatch.setattr(sc, "_snapshot_written_at", time.time() - 600)

    snap = sc.get_snapshot()
    assert snap.get("events"), "empty cache must be re-read from a newer file"
    assert "r1" in snap["events"]


def test_get_snapshot_does_not_thrash_when_disk_unchanged(tmp_path, monkeypatch):
    from core_agent.core import snapshot_cache as sc

    path = tmp_path / "market_snapshot_latest.json"
    path.write_text(json.dumps({"events": {}, "timestamp": _stamp(0)}))
    monkeypatch.setattr(sc, "MARKET_SNAPSHOT_PATH", str(path))
    monkeypatch.setattr(sc, "_sanitize", lambda data, source: data)

    sc._snapshot.clear()
    sc._snapshot.update({"events": {}, "count": 0})
    mtime = os.path.getmtime(path)
    sc._snapshot_written_at = mtime
    monkeypatch.setattr(sc, "_snapshot_written_at", mtime)

    assert sc.get_snapshot().get("events") == {}


def test_get_snapshot_keeps_live_events_from_cache(monkeypatch):
    from core_agent.core import snapshot_cache as sc

    sc._snapshot.clear()
    sc._snapshot.update({"events": {"live": {}}})
    monkeypatch.setattr(sc, "_sanitize", lambda data, source: data)
    # No file access needed: a populated cache short-circuits.
    monkeypatch.setattr(sc.os.path, "exists", lambda p: pytest.fail("hit disk"))

    assert "live" in sc.get_snapshot()["events"]
