"""ATR refresh gate: the per-feed 45-minute throttle must hold.

Nov-2026 regression: the odds monitor never reloaded or committed the data
volume, so every 5-min cron container mounted stale mtimes, the freshness gate
said "stale", and results were re-fetched three times in ten minutes. That
burned the hourly browser allowance and tripped the 6h circuit breaker, which
froze every ATR snapshot for the rest of the evening card.

These tests pin the gate contract: fresh feeds cost nothing, a stale feed
fetches alone, and any write is committed so sibling containers see it.
"""
import asyncio
import json
from datetime import datetime, timedelta

import pytest

from core_agent.core import adaptive_odds_monitor as mon


class _FakeATR:
    def __init__(self):
        self.calls = []
        self.bursts = []

    def open_stealth_burst(self, pages):
        self.bursts.append(pages)

    async def get_results(self, day):
        self.calls.append(("results", day))
        return [{"course": "Greyville (RSA)", "runners": []}]

    async def get_market_movers(self):
        self.calls.append(("movers",))
        return [{"horse": "Eagle Has Landed"}]

    async def get_predictor(self):
        self.calls.append(("predictor",))
        return [{"horse": "Eagle Has Landed"}]


@pytest.fixture
def harness(monkeypatch):
    atr = _FakeATR()
    monitor = object.__new__(mon.AdaptiveOddsMonitor)
    monitor.at_races = atr

    state = {"reloads": 0, "commits": 0, "writes": []}

    monkeypatch.setattr(monitor, "_volume_reload", lambda: state.__setitem__("reloads", state["reloads"] + 1))
    monkeypatch.setattr(monitor, "_volume_commit", lambda: state.__setitem__("commits", state["commits"] + 1))
    monkeypatch.setattr(mon, "_atomic_write_json", lambda path, data, indent=2: state["writes"].append(path))

    return atr, monitor, state


def _gate(monkeypatch, *, snapshot_fresh, fresh_paths):
    monkeypatch.setattr(mon, "_atr_snapshot_fresh", lambda *a, **k: snapshot_fresh)
    monkeypatch.setattr(mon, "_atr_file_fresh", lambda p, *a, **k: p in fresh_paths)
    monkeypatch.setattr(
        mon, "_atr_predictor_fresh", lambda *a, **k: mon.ATR_PREDICTOR_PATH in fresh_paths
    )


def test_all_snapshots_fresh_fetch_nothing(harness, monkeypatch):
    atr, monitor, state = harness
    _gate(monkeypatch, snapshot_fresh=True, fresh_paths=set())

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert atr.calls == []
    assert state["writes"] == []
    assert state["commits"] == 0


def test_only_stale_results_fetch_and_commit(harness, monkeypatch):
    atr, monitor, state = harness
    _gate(
        monkeypatch,
        snapshot_fresh=False,
        fresh_paths={mon.ATR_MOVERS_PATH, mon.ATR_PREDICTOR_PATH},
    )

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    # Results day-loop only: today first, then yesterday (no snapshot on disk
    # yet). Movers/predictor stay untouched. The order is load-bearing: the
    # browser allowance is ~1/hour, so "yesterday" first starved "today" and
    # the HUD only ever showed yesterday's card (Nov-2026).
    assert atr.calls == [("results", "today"), ("results", "yesterday")]
    assert state["writes"] == [mon.ATR_RESULTS_PATH]
    assert state["commits"] == 1
    # The mount must be refreshed before the gate is trusted.
    assert state["reloads"] == 1


def test_stale_feed_with_empty_result_does_not_commit(harness, monkeypatch):
    atr, monitor, state = harness
    _gate(
        monkeypatch,
        snapshot_fresh=False,
        fresh_paths={mon.ATR_MOVERS_PATH, mon.ATR_PREDICTOR_PATH},
    )

    async def empty(day):
        atr.calls.append(("results", day))
        return []

    monkeypatch.setattr(atr, "get_results", empty)

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert state["writes"] == []
    assert state["commits"] == 0


# --- Predictor freshness contract (Nov-2026) -------------------------------
# A failed attempt rewrites the snapshot to record last_error and keeps the
# previous success timestamp. Gating on mtime made every failure look fresh, so
# the predictor stayed 18.8h stale and never got a browser slot in the burst.


def _predictor_snapshot(tmp_path, *, timestamp, mtime_age_secs=0.0):
    import os
    import time as _time

    snap = tmp_path / "atr_predictor_snapshot.json"
    snap.write_text(
        json.dumps(
            {
                "predictions": [{"horse": "Old Pick"}],
                "timestamp": timestamp,
                "last_attempt": datetime.now().isoformat(),
                "last_error": "empty scrape (0 predictions parsed)",
            }
        )
    )
    when = _time.time() - mtime_age_secs
    os.utime(snap, (when, when))
    return snap


def test_failed_predictor_attempt_with_fresh_mtime_is_stale(tmp_path, monkeypatch):
    old = (datetime.now() - timedelta(hours=19)).isoformat()
    snap = _predictor_snapshot(tmp_path, timestamp=old)
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(snap))

    # mtime is "now": the pre-fix gate called this fresh and skipped forever.
    assert mon._atr_file_fresh(snap) is True
    assert mon._atr_predictor_fresh() is False


def test_predictor_fresh_after_successful_refresh(tmp_path, monkeypatch):
    snap = _predictor_snapshot(tmp_path, timestamp=datetime.now().isoformat())
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(snap))

    assert mon._atr_predictor_fresh() is True


def test_predictor_without_timestamp_falls_back_to_mtime(tmp_path, monkeypatch):
    snap = _predictor_snapshot(tmp_path, timestamp=None)
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(snap))

    assert mon._atr_predictor_fresh() is True

    snap = _predictor_snapshot(
        tmp_path, timestamp=None, mtime_age_secs=mon.ATR_REFRESH_MIN_GAP_SECS + 60
    )
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(snap))

    assert mon._atr_predictor_fresh() is False


def test_predictor_stale_by_timestamp_is_refetched_next_cycle(
    harness, monkeypatch, tmp_path
):
    atr, monitor, state = harness
    old = (datetime.now() - timedelta(hours=19)).isoformat()
    snap = _predictor_snapshot(tmp_path, timestamp=old)
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(snap))

    monkeypatch.setattr(mon, "_atr_snapshot_fresh", lambda *a, **k: False)
    # Results and movers are current; only the predictor needs work.
    monkeypatch.setattr(mon, "_atr_file_fresh", lambda p, *a, **k: True)

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert atr.calls == [("predictor",)]
    # The stale predictor must claim a page in the one hourly burst.
    assert atr.bursts == [1]
    assert state["writes"] == [str(snap)]
    assert state["commits"] == 1

