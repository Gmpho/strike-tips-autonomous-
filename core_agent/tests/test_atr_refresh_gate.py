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

import pytest

from core_agent.core import adaptive_odds_monitor as mon


class _FakeATR:
    def __init__(self):
        self.calls = []

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

    # Results day-loop only: yesterday + today. Movers/predictor stay untouched.
    assert atr.calls == [("results", "yesterday"), ("results", "today")]
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
