"""Snapshot integrity + Betfair rolling cache (fix-stale-race-resurrection).

Regression cover for the Sep-2026 dashboard faults:

- two scan-side writers (scheduler + daily scan) dumped the RAW Betway bundle
  over the monitor's pruned card → the HUD oscillated between 58 live races
  and the 126-race morning card, with finished races "coming back";
- Betfair's last-good cache was an all-or-nothing 1h file: a failed fetch
  either blanked gear/days off the card or re-injected finished markets.

Covered here:
- ``sanitize_snapshot`` drops finished + overdue races and stamps metadata
- ``_close_overdue_races`` stamps ``expires_at`` on survivors
- ``write_market_snapshot`` prunes the file AND refreshes the memory cache
- ``snapshot_cache.set_snapshot`` sanitizes a raw (unpruned) bundle
- Betfair rolling cache: upsert, per-race expiry, cache replay on failure
"""

import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core_agent.core import snapshot_cache, snapshot_writer
import core_agent.core.adaptive_odds_monitor as adaptive_odds_monitor
from core_agent.core.adaptive_odds_monitor import (
    AdaptiveOddsMonitor,
    _close_overdue_races,
)

FROZEN_NOW = datetime(2026, 9, 20, 12, 0, 0)  # mid-day: no midnight rollover


class _FrozenDatetime(datetime):
    """datetime stub so HH:MM off-time maths is deterministic in tests."""

    @classmethod
    def now(cls, tz=None):  # noqa: D102 - test double
        return cls(2026, 9, 20, 12, 0, 0)


def _sample_state():
    """One live race, one finished race, one that went off two hours ago."""
    return {
        "events": {
            "live": {"en": "  Vaal  ", "raceNumber": 1, "t": "13:00"},
            "finished": {"en": "Vaal", "raceNumber": 2, "t": "13:00", "isFinished": True},
            "overdue": {"en": "Vaal", "raceNumber": 3, "t": "10:00"},
        }
    }


# ── sanitize_snapshot ────────────────────────────────────────────────────────


def test_sanitize_snapshot_drops_finished_and_overdue():
    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        out = snapshot_writer.sanitize_snapshot(_sample_state(), source="daily_scan")

    assert set(out["events"]) == {"live"}
    assert out["events"]["live"]["en"] == "Vaal"  # whitespace normalised
    assert out["count"] == 1
    assert out["snapshot_source"] == "daily_scan"
    assert datetime.fromisoformat(out["timestamp"])  # stamped


def test_sanitize_snapshot_survivor_expires_at_is_future():
    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        out = snapshot_writer.sanitize_snapshot(_sample_state(), source="test")

    expires = out["events"]["live"]["expires_at"]
    assert expires > FROZEN_NOW.timestamp()  # 13:00 + 2 min grace, not yet passed


def test_closer_stamps_expires_at_and_clears_first_seen():
    events = {"r": {"en": "Durbanville", "t": "14:00", "first_seen": 1.0}}
    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        out = _close_overdue_races(events)
    assert "first_seen" not in out["r"]
    assert out["r"]["expires_at"] > FROZEN_NOW.timestamp()


# ── write_market_snapshot (single sanctioned writer) ────────────────────────


def test_write_market_snapshot_prunes_file_and_cache(tmp_path, monkeypatch):
    snap_path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", snap_path)
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", snap_path)
    snapshot_cache.set_snapshot({"events": {}}, source="reset")

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        saved = snapshot_writer.write_market_snapshot(_sample_state(), source="scheduler_scan")

    on_disk = json.loads(snap_path.read_text())
    assert set(on_disk["events"]) == {"live"}
    assert on_disk["snapshot_source"] == "scheduler_scan"
    assert saved["count"] == 1

    # Memory cache agrees with the file (same-container reads).
    cached = snapshot_cache.get_snapshot()
    assert set(cached["events"]) == {"live"}
    assert snapshot_cache.get_snapshot_meta()["source"] == "scheduler_scan"


# ── snapshot_cache ingress sanitisation ─────────────────────────────────────


def test_set_snapshot_sanitizes_raw_betway_bundle(tmp_path, monkeypatch):
    """The regression: a raw scan dump must not leak finished races."""
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", tmp_path / "raw.json")
    snapshot_cache.set_snapshot({"events": {}}, source="reset")

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        snapshot_cache.set_snapshot(_sample_state(), source="scheduler_scan")

    cached = snapshot_cache.get_snapshot()
    assert set(cached["events"]) == {"live"}
    assert cached["count"] == 1


def test_sanitize_preserves_producer_source():
    """A producer that labelled itself keeps its label through re-sanitization."""
    state = {"snapshot_source": "monitor",
             "events": {"r": {"en": "Vaal", "raceNumber": 1, "t": "13:00"}}}
    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime):
        out = snapshot_writer.sanitize_snapshot(state, source="disk-poll")
    assert out["snapshot_source"] == "monitor"


def test_set_snapshot_prefers_producer_source(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", tmp_path / "s.json")
    snapshot_cache.set_snapshot(
        {"events": {}, "snapshot_source": "monitor"}, source="disk-poll"
    )
    assert snapshot_cache.get_snapshot_meta()["source"] == "monitor"


# ── Writer source priority ────────────────────────────────────────────────


def _live_event(offset_minutes: float = 120.0):
    future = datetime.now() + timedelta(minutes=offset_minutes)
    return {"en": "Vaal", "raceNumber": 1, "t": future.strftime("%H:%M")}


def test_scan_write_does_not_clobber_fresher_monitor_file(tmp_path, monkeypatch):
    """The morning race: a scan payload must not overwrite the live monitor file."""
    path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", path)

    monitor_state = {"events": {"m1": _live_event()}, "snapshot_source": "monitor"}
    written = snapshot_writer.write_market_snapshot(monitor_state, source="monitor")
    assert path.exists()
    monitor_ts = json.loads(path.read_text())["timestamp"]

    older_payload = {
        "events": {"s1": _live_event()},
        "timestamp": (datetime.now() - timedelta(minutes=30)).isoformat(),
    }
    out = snapshot_writer.write_market_snapshot(
        older_payload, source="scheduler_scan", path=path
    )
    assert set(out["events"]) == {"s1"}  # payload returned for in-memory use
    current = json.loads(path.read_text())
    assert current["timestamp"] == monitor_ts  # file untouched
    assert current["snapshot_source"] == "monitor"
    assert set(current["events"]) == {"m1"}


def test_scan_write_wins_when_monitor_file_is_stale(tmp_path, monkeypatch):
    """Fallback path: an old monitor file yields to a fresh scan payload."""
    path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", path)

    stale_monitor = {
        "events": {"m1": _live_event()},
        "snapshot_source": "monitor",
        "timestamp": (datetime.now() - timedelta(hours=5)).isoformat(),
    }
    path.write_text(json.dumps(stale_monitor))

    fresh = {"events": {"s1": _live_event()}}
    out = snapshot_writer.write_market_snapshot(
        fresh, source="scheduler_scan", path=path
    )
    current = json.loads(path.read_text())
    assert set(current["events"]) == {"s1"}
    assert set(out["events"]) == {"s1"}


def test_monitor_write_never_blocked(tmp_path, monkeypatch):
    """The live writer always persists, whatever the file holds."""
    path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", path)
    path.write_text(json.dumps({
        "events": {"s1": _live_event()},
        "snapshot_source": "scheduler_scan",
        "timestamp": datetime.now().isoformat(),
    }))
    out = snapshot_writer.write_market_snapshot(
        {"events": {"m1": _live_event()}}, source="monitor", path=path
    )
    current = json.loads(path.read_text())
    assert current["snapshot_source"] == "monitor"
    assert set(current["events"]) == {"m1"}
    assert set(out["events"]) == {"m1"}


# ── Empty-snapshot guard ────────────────────────────────────────────────────


def test_empty_guard_recovers_still_current_previous_races(tmp_path, monkeypatch):
    """A 0-race cycle reuses previous races that are still current."""
    snap = tmp_path / "market_snapshot_latest.json"
    snap.write_text(json.dumps({"events": {"prev1": {"en": "Vaal", "raceNumber": 1}}}))
    monkeypatch.setattr(adaptive_odds_monitor, "MARKET_SNAPSHOT_PATH", snap)

    healing: list = []
    with patch("core_agent.core.adaptive_odds_monitor._write_healing_event",
               side_effect=lambda action, details, **kw: healing.append(action)):
        out = adaptive_odds_monitor._recover_empty_snapshot({"events": {}, "count": 0})

    assert set(out["events"]) == {"prev1"}
    assert out["stale"] is True
    assert "stale_since" in out
    assert "SNAPSHOT_EMPTY_GUARD" in healing


def test_empty_guard_accepts_empty_when_previous_expired(tmp_path, monkeypatch):
    """When the previous card is over, the empty result stands."""
    snap = tmp_path / "market_snapshot_latest.json"
    past = (datetime.now() - timedelta(hours=3)).strftime("%H:%M")
    snap.write_text(json.dumps({"events": {"old": {"en": "Vaal", "t": past}}}))
    monkeypatch.setattr(adaptive_odds_monitor, "MARKET_SNAPSHOT_PATH", snap)

    with patch("core_agent.core.adaptive_odds_monitor._write_healing_event") as heal:
        out = adaptive_odds_monitor._recover_empty_snapshot({"events": {}, "count": 0})

    assert out["events"] == {}
    assert not out.get("stale")
    heal.assert_not_called()


# ── Betfair rolling cache ───────────────────────────────────────────────────


def _bf_off_epoch_ms(hours_from_frozen: float) -> int:
    """Absolute off-time epoch-ms relative to FROZEN_NOW (clock-independent)."""
    return int((FROZEN_NOW + timedelta(hours=hours_from_frozen)).timestamp() * 1000)


def _bf_event(offset_hours, cached_at=None, market_id="1.1"):
    """A Betfair market with an exact off-time (epoch path, no wall-clock)."""
    ev = {"course": "Scottsville",
          "offTimeEpochMs": _bf_off_epoch_ms(offset_hours),
          "runners": [{"name": "A"}]}
    if cached_at is not None:
        ev["_bf_cached_at"] = cached_at
    return market_id, ev


def _make_monitor(cache_path):
    m = object.__new__(AdaptiveOddsMonitor)
    m._bf_cache_path = lambda: str(cache_path)  # type: ignore[assignment]
    return m


def _write_cache(path, events):
    path.write_text(json.dumps({"saved_at": FROZEN_NOW.isoformat(), "events": events}))


# ── Modal volume reload (cross-container visibility, Sep-2026) ───────────────


def _write_snapshot_file(path, source="monitor"):
    # A race ~30 min from now survives the off-time closer's pruning.
    # Naive local (the closer compares against naive datetime.now()).
    t = (datetime.now() + timedelta(minutes=30)).strftime("%H:%M")
    path.write_text(
        json.dumps(
            {
                "events": {"a": {"en": "Vaal", "raceNumber": 1, "t": t}},
                "count": 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "snapshot_source": source,
            }
        )
    )


async def _run_one_refresh_cycle():
    """Drive disk_refresh_loop through exactly one pass, then break.

    The loop sleeps first, so pass the initial sleep through (interval=0)
    and raise on the next one — after the poll body has run once.
    """
    import asyncio

    real_sleep = asyncio.sleep
    passes = {"n": 0}

    async def _sleep(_):
        if passes["n"] >= 1:
            raise KeyboardInterrupt
        passes["n"] += 1
        await real_sleep(0)

    with patch("asyncio.sleep", _sleep):
        with pytest.raises(KeyboardInterrupt):
            await snapshot_cache.disk_refresh_loop(interval=0)


@pytest.mark.asyncio
async def test_disk_refresh_loop_reloads_modal_volume(tmp_path, monkeypatch):
    """The web container's volume mount caches the startup view.

    disk_refresh_loop must call volume.reload() before stat, or the monitor
    cron's writes (Betfair gear, fresh card) stay invisible for the life of
    the web container (Sep-2026: HUD sat on its own scheduler_scan card for
    hours while the volume file carried a fresh monitor snapshot).
    """
    import sys

    reload_calls = []

    class _FakeVolume:
        def reload(self):
            reload_calls.append(True)

    fake_modal = SimpleNamespace(
        Volume=SimpleNamespace(from_name=lambda name, create_if_missing: _FakeVolume())
    )
    monkeypatch.setattr(snapshot_cache, "_volume_obj", None)
    monkeypatch.setattr(snapshot_cache, "_volume_retry_at", 0.0)
    monkeypatch.setattr(snapshot_cache, "_volume_lock", None)
    monkeypatch.setattr(snapshot_cache, "_volume_last_reload", 0.0)
    monkeypatch.setitem(sys.modules, "modal", fake_modal)
    monkeypatch.setenv("MODAL_TASK_ID", "test-task")  # simulate Modal runtime

    snap = tmp_path / "market_snapshot_latest.json"
    _write_snapshot_file(snap)
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", snap)
    monkeypatch.setattr(snapshot_cache, "_last_disk_mtime", 0.0)

    await _run_one_refresh_cycle()

    assert reload_calls == [True]
    cached = snapshot_cache.get_snapshot()
    assert cached.get("events"), "fresh monitor snapshot must enter memory"
    # Producer label survives disk-poll ingress sanitization.
    assert snapshot_cache.get_snapshot_meta()["source"] == "monitor"


@pytest.mark.asyncio
async def test_volume_reload_prefers_async_form(tmp_path, monkeypatch):
    """On Modal, vol.reload.aio() is the event-loop-safe form; the sync
    call must never run when .aio exists."""
    import sys

    sync_calls, aio_calls = [], []

    class _ReloadFn:
        def __call__(self):
            sync_calls.append(True)

        async def aio(self):
            aio_calls.append(True)

    class _FakeVolume:
        reload = _ReloadFn()

    fake_modal = SimpleNamespace(
        Volume=SimpleNamespace(from_name=lambda name, create_if_missing: _FakeVolume())
    )
    for attr, val in (
        ("_volume_obj", None),
        ("_volume_retry_at", 0.0),
        ("_volume_lock", None),
        ("_volume_last_reload", 0.0),
    ):
        monkeypatch.setattr(snapshot_cache, attr, val)
    monkeypatch.setitem(sys.modules, "modal", fake_modal)
    monkeypatch.setenv("MODAL_TASK_ID", "test-task")  # simulate Modal runtime

    snap = tmp_path / "market_snapshot_latest.json"
    _write_snapshot_file(snap)
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", snap)
    monkeypatch.setattr(snapshot_cache, "_last_disk_mtime", 0.0)

    await _run_one_refresh_cycle()

    assert aio_calls == [True]
    assert sync_calls == []


@pytest.mark.asyncio
async def test_disk_refresh_loop_falls_back_to_local_stat(tmp_path, monkeypatch):
    """Outside Modal (no modal module/token) the loop still refreshes from
    the local mount — docker-compose and same-container writers — and the
    volume lookup backs off instead of retrying every cycle."""
    import sys

    monkeypatch.setattr(snapshot_cache, "_volume_obj", None)
    monkeypatch.setattr(snapshot_cache, "_volume_retry_at", 0.0)
    monkeypatch.setattr(snapshot_cache, "_volume_lock", None)
    monkeypatch.setattr(snapshot_cache, "_volume_last_reload", 0.0)
    monkeypatch.setitem(sys.modules, "modal", None)  # `import modal` fails

    snap = tmp_path / "market_snapshot_latest.json"
    _write_snapshot_file(snap)
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", snap)
    monkeypatch.setattr(snapshot_cache, "_last_disk_mtime", 0.0)

    await _run_one_refresh_cycle()

    assert snapshot_cache.get_snapshot().get("events")
    assert snapshot_cache._volume_retry_at > 0.0, "failed lookup must back off"


# ── Betfair pruning (rolling per-race cache) ─────────────────────────────────


def test_bf_prune_drops_finished_market():
    m = _make_monitor("/tmp/unused.json")
    mid, ev = _bf_event(-2, cached_at=FROZEN_NOW.timestamp())
    assert m._prune_bf_events({mid: ev}, now=FROZEN_NOW) == {}


def test_bf_prune_keeps_upcoming_market():
    m = _make_monitor("/tmp/unused.json")
    mid, ev = _bf_event(2, cached_at=FROZEN_NOW.timestamp())
    assert mid in m._prune_bf_events({mid: ev}, now=FROZEN_NOW)


def test_bf_prune_drops_entry_that_stopped_refreshing():
    m = _make_monitor("/tmp/unused.json")
    stale = (FROZEN_NOW - timedelta(hours=7)).timestamp()
    mid, ev = _bf_event(2, cached_at=stale)
    assert m._prune_bf_events({mid: ev}, now=FROZEN_NOW) == {}


@pytest.mark.asyncio
async def test_bf_empty_fetch_replays_pruned_cache(tmp_path):
    """A failed cycle keeps gear/days for live races and drops finished ones."""
    cache_path = tmp_path / "betfair_form_last_good.json"
    live_id, live_ev = _bf_event(2, cached_at=FROZEN_NOW.timestamp())
    dead_id, dead_ev = _bf_event(-2, cached_at=FROZEN_NOW.timestamp(), market_id="1.2")
    _write_cache(cache_path, {live_id: live_ev, dead_id: dead_ev})

    m = _make_monitor(cache_path)
    m.betfair = SimpleNamespace(
        get_form_format=AsyncMock(return_value={"events": {}, "count": 0})
    )

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime), \
         patch("core_agent.core.adaptive_odds_monitor._write_healing_event"):
        result = await m._fetch_betfair_form_safely()

    assert result["cached"] is True
    assert set(result["events"]) == {live_id}
    saved = json.loads(cache_path.read_text())
    assert set(saved["events"]) == {live_id}  # finished market pruned on disk too


@pytest.mark.asyncio
async def test_bf_empty_fetch_with_only_finished_cache_returns_empty(tmp_path):
    cache_path = tmp_path / "betfair_form_last_good.json"
    dead_id, dead_ev = _bf_event(-2, cached_at=FROZEN_NOW.timestamp())
    _write_cache(cache_path, {dead_id: dead_ev})

    m = _make_monitor(cache_path)
    m.betfair = SimpleNamespace(
        get_form_format=AsyncMock(return_value={"events": {}, "count": 0})
    )
    healing: list = []

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime), \
         patch("core_agent.core.adaptive_odds_monitor._write_healing_event",
               side_effect=lambda action, details, **kw: healing.append(action)):
        result = await m._fetch_betfair_form_safely()

    assert result == {"events": {}, "count": 0}
    assert "BETFAIR_CACHE_STALE" in healing


@pytest.mark.asyncio
async def test_bf_success_upserts_cache(tmp_path):
    cache_path = tmp_path / "betfair_form_last_good.json"
    live_id, live_ev = _bf_event(2, cached_at=FROZEN_NOW.timestamp())
    _write_cache(cache_path, {live_id: live_ev})

    m = _make_monitor(cache_path)
    fresh_id, fresh_ev = _bf_event(3, market_id="1.9")
    m.betfair = SimpleNamespace(
        get_form_format=AsyncMock(return_value={"events": {fresh_id: fresh_ev}, "count": 1})
    )

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime), \
         patch("core_agent.core.adaptive_odds_monitor._write_healing_event"):
        result = await m._fetch_betfair_form_safely()

    assert set(result["events"]) == {fresh_id}
    saved = json.loads(cache_path.read_text())
    # Rolling cache keeps the older live race and the freshly fetched one.
    assert set(saved["events"]) == {live_id, fresh_id}
    assert saved["events"][fresh_id]["_bf_cached_at"] == FROZEN_NOW.timestamp()


@pytest.mark.asyncio
async def test_bf_fetch_exception_replays_cache(tmp_path):
    cache_path = tmp_path / "betfair_form_last_good.json"
    live_id, live_ev = _bf_event(2, cached_at=FROZEN_NOW.timestamp())
    _write_cache(cache_path, {live_id: live_ev})

    m = _make_monitor(cache_path)
    m.betfair = SimpleNamespace(get_form_format=AsyncMock(side_effect=RuntimeError("boom")))

    with patch("core_agent.core.adaptive_odds_monitor.datetime", _FrozenDatetime), \
         patch("core_agent.core.adaptive_odds_monitor._write_healing_event",
               side_effect=lambda *a, **k: None):
        result = await m._fetch_betfair_form_safely()

    assert set(result["events"]) == {live_id}
    assert result["cached"] is True


def test_bf_event_off_utc_prefers_epoch():
    """offTimeEpochMs wins — wall-clock HH:MM is ambiguous without a date."""
    epoch_ms = int(datetime(2026, 9, 20, 14, 0, tzinfo=timezone.utc).timestamp() * 1000)
    ev = {"offTimeEpochMs": epoch_ms, "t": "99:99"}
    off = AdaptiveOddsMonitor._bf_event_off_utc(ev)
    assert off is not None and off.hour == 14
