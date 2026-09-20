"""Tests for odds-monitor resilience (fix-monitor-stall-resurrection).

Covers:
- closer prefers bf_off_time (SAST wall -> UTC) over Betway display times
- unparseable-off-time races are first_seen-stamped and TTL-dropped
- Betway base-feed failure reuses the last-good snapshot stamped stale
- MONITOR_STALL healing event fires only past the threshold
"""

import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.core.adaptive_odds_monitor import (
    MONITOR_STALL_SECS,
    UNPARSEABLE_RACE_TTL_SECS,
    AdaptiveOddsMonitor,
    _close_overdue_races,
    _sast_to_utc,
)


# ── Closer: bf_off_time preference ───────────────────────────────────────────


def test_sast_to_utc_shifts_two_hours():
    sast = datetime(2026, 9, 19, 14, 40)
    utc = _sast_to_utc(sast)
    assert (utc.hour, utc.minute) == (12, 40)


def test_sast_to_utc_handles_midnight_wrap():
    sast = datetime(2026, 9, 19, 1, 10)
    utc = _sast_to_utc(sast)
    assert (utc.hour, utc.minute) == (23, 10)
    assert utc.day == 18


def test_sast_to_utc_none_safe():
    assert _sast_to_utc(None) is None


def test_parse_race_off_time_rolls_far_future_back_to_yesterday():
    """23:44 seen at 00:14 belongs to yesterday's card, not tonight's."""
    from core_agent.core.adaptive_odds_monitor import _parse_race_off_time

    base = datetime(2026, 9, 20, 0, 14)
    assert _parse_race_off_time("23:44", race_date=base) == datetime(2026, 9, 19, 23, 44)


def test_parse_race_off_time_keeps_normal_future_time():
    from core_agent.core.adaptive_odds_monitor import _parse_race_off_time

    base = datetime(2026, 9, 20, 0, 14)
    assert _parse_race_off_time("13:00", race_date=base) == datetime(2026, 9, 20, 13, 0)


def test_closer_drops_race_via_bf_off_time_despite_placeholder_betway_time():
    """bf_off_time says the race went off 30 min ago even though Betway's
    display time is a future placeholder."""
    now = datetime.now()
    # SAST wall = UTC now + 2h; back off 30 min => went off 30 min ago (UTC)
    bf_off_sast = (now + timedelta(hours=2, minutes=-30)).strftime("%H:%M")
    events = {
        "r1": {
            "en": "Keeneland",
            "raceNumber": 5,
            "t": "23:59",  # placeholder/future Betway time would keep it alive
            "bf_off_time": bf_off_sast,
        }
    }
    out = _close_overdue_races(events, max_minutes_after_off=5)
    assert "r1" not in out


def test_closer_keeps_fresh_race_with_future_bf_off_time():
    now = datetime.now()
    # SAST wall = UTC now + 3h => 1h in the future once converted
    bf_off_sast = (now + timedelta(hours=3)).strftime("%H:%M")
    events = {"r2": {"en": "Durbanville", "t": "23:59", "bf_off_time": bf_off_sast}}
    out = _close_overdue_races(events, max_minutes_after_off=5)
    assert "r2" in out
    assert "first_seen" not in out["r2"]


def test_closer_still_uses_betway_time_when_no_bf_off_time():
    past = (datetime.now() - timedelta(minutes=30)).strftime("%H:%M")
    events = {"r3": {"en": "Wolverhampton", "t": past}}
    out = _close_overdue_races(events, max_minutes_after_off=5)
    assert "r3" not in out


def test_closer_keeps_race_inside_grace_window():
    recent = (datetime.now() - timedelta(minutes=2)).strftime("%H:%M")
    events = {"r4": {"en": "Vaal", "t": recent}}
    out = _close_overdue_races(events, max_minutes_after_off=5)
    assert "r4" in out


# ── Closer: first_seen TTL for unparseable races ─────────────────────────────


def test_closer_stamps_first_seen_on_unparseable_race():
    events = {"r5": {"en": "MysteryMeeting"}}  # no t, no st, no bf_off_time
    out = _close_overdue_races(events)
    assert "r5" in out
    assert "first_seen" in out["r5"]


def test_closer_drops_unparseable_race_past_ttl():
    old = (datetime.now() - timedelta(seconds=UNPARSEABLE_RACE_TTL_SECS + 60)).timestamp()
    events = {"r6": {"en": "MysteryMeeting", "first_seen": old}}
    out = _close_overdue_races(events)
    assert "r6" not in out


def test_closer_keeps_unparseable_race_within_ttl():
    recent = (datetime.now() - timedelta(minutes=10)).timestamp()
    events = {"r7": {"en": "MysteryMeeting", "first_seen": recent}}
    out = _close_overdue_races(events)
    assert "r7" in out


def test_closer_corrupt_first_seen_is_restamped_not_dropped():
    events = {"r8": {"en": "MysteryMeeting", "first_seen": "not-a-number"}}
    out = _close_overdue_races(events)
    assert "r8" in out
    assert isinstance(out["r8"]["first_seen"], float)


# ── Cycle tests appended below ────────────────────────────────────────────────


def _make_monitor(betway_side_effect):
    m = object.__new__(AdaptiveOddsMonitor)
    # A plain dict as side_effect is ITERABLE (yields its keys), so wrap the
    # success value in a one-element list to make AsyncMock return it verbatim.
    eff = betway_side_effect if isinstance(betway_side_effect, Exception) else [betway_side_effect]
    m.betway = SimpleNamespace(get_snapshot_format=AsyncMock(side_effect=eff))
    m.racing_odds = SimpleNamespace(
        get_snapshot_format=AsyncMock(return_value={"events": {}, "count": 0})
    )
    m._fetch_betfair_form_safely = AsyncMock(return_value={"events": {}, "count": 0})
    m.intel_cache = MagicMock()
    m.alert_engine = MagicMock()
    m.alert_engine.evaluate_odds_update = AsyncMock()
    m._digester = None
    m._check_atr_staleness = AsyncMock()
    m._cleanup_atr_snapshots = AsyncMock()
    return m


def _run_cycle(monitor, snap_path, healing):
    """Run one cycle with all external touchpoints patched; return its result."""
    from contextlib import ExitStack

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "core_agent.core.adaptive_odds_monitor.MARKET_SNAPSHOT_PATH",
                str(snap_path),
            )
        )
        stack.enter_context(
            patch(
                "core_agent.core.adaptive_odds_monitor._write_healing_event",
                side_effect=lambda action, details, **kw: healing.append(action),
            )
        )
        stack.enter_context(
            patch("core_agent.core.adaptive_odds_monitor._merge_daily_scan_into")
        )
        stack.enter_context(
            patch("core_agent.core.adaptive_odds_monitor.enrich_snapshot_with_insights")
        )
        stack.enter_context(
            patch(
                "core_agent.core.adaptive_odds_monitor._atr_snapshot_fresh",
                return_value=True,
            )
        )
        stack.enter_context(
            patch("core_agent.core.cf_push.push_snapshot", new=AsyncMock())
        )
        return asyncio.run(monitor.run_single_cycle())





@pytest.fixture
def snap_file(tmp_path):
    return tmp_path / "market_snapshot_latest.json"


def test_cycle_reuses_last_good_snapshot_when_betway_fails(snap_file):
    snap_file.write_text(
        json.dumps(
            {
                # t one hour in the future: parses as today, stays open
                "events": {
                    "r1": {
                        "en": "Kenilworth",
                        "t": (datetime.now() + timedelta(hours=1)).strftime("%H:%M"),
                    }
                },
                "count": 1,
                "timestamp": datetime.now().isoformat(),
            }
        )
    )
    monitor = _make_monitor(RuntimeError("Betway challenge wall"))
    healing = []
    result = _run_cycle(monitor, snap_file, healing)

    assert result is not None  # no silent early-return
    assert result["stale"] is True
    assert "stale_since" in result
    assert "r1" in result["events"]  # last-good races survived
    assert "BETWAY_FETCH_FAIL" in healing
    written = json.loads(snap_file.read_text())
    assert written["stale"] is True  # stale flag persisted to disk


def test_cycle_synthesizes_empty_state_when_no_previous_file(snap_file):
    monitor = _make_monitor(RuntimeError("Betway down, no file either"))
    healing = []
    result = _run_cycle(monitor, snap_file, healing)  # file does not exist

    assert result is not None
    assert result["events"] == {}
    assert result["stale"] is True
    assert "BETWAY_FETCH_FAIL" in healing


def test_cycle_clears_stale_stamp_on_success(snap_file):
    snap_file.write_text(json.dumps({"events": {}, "count": 0, "stale": True}))
    monitor = _make_monitor({"events": {}, "count": 0})
    result = _run_cycle(monitor, snap_file, [])

    assert result is not None
    assert "stale" not in result
    assert "stale_since" not in result


def test_monitor_stall_fires_past_threshold(snap_file):
    stale_ts = (
        datetime.now() - timedelta(seconds=MONITOR_STALL_SECS + 60)
    ).isoformat()
    snap_file.write_text(json.dumps({"events": {}, "count": 0, "timestamp": stale_ts}))
    monitor = _make_monitor({"events": {}, "count": 0})
    healing = []
    _run_cycle(monitor, snap_file, healing)

    assert "MONITOR_STALL" in healing


def test_monitor_stall_silent_within_threshold(snap_file):
    fresh_ts = (
        datetime.now() - timedelta(seconds=MONITOR_STALL_SECS - 300)
    ).isoformat()
    snap_file.write_text(json.dumps({"events": {}, "count": 0, "timestamp": fresh_ts}))
    monitor = _make_monitor({"events": {}, "count": 0})
    healing = []
    _run_cycle(monitor, snap_file, healing)

    assert "MONITOR_STALL" not in healing


# ── Empty-snapshot guard: a 0-race cycle must not blank the card ─────────────


def test_empty_cycle_keeps_card_via_guard(snap_file):
    """A cycle that prunes to 0 races while prior races are current must reuse
    them (Sep-2026: an upstream hiccup blanked HUD + KV for a whole cycle)."""
    # No parseable off-time: the race survives via the closer's first_seen TTL
    # path, which keeps this assertion independent of the wall clock.
    snap_file.write_text(
        json.dumps({"events": {"prev1": {"en": "Vaal", "raceNumber": 1}}})
    )
    monitor = _make_monitor({"events": {}, "count": 0})
    healing = []
    result = _run_cycle(monitor, snap_file, healing)

    assert result is not None
    assert result["count"] == 1
    assert set(result["events"]) == {"prev1"}
    assert result["stale"] is True
    assert "SNAPSHOT_EMPTY_GUARD" in healing

    written = json.loads(snap_file.read_text())
    assert set(written["events"]) == {"prev1"}  # persisted, not blanked
    assert written["snapshot_source"] == "monitor"  # provenance for readers


def test_empty_cycle_lets_card_end_when_previous_expired(snap_file):
    """When the previous card is genuinely over, an empty snapshot is correct."""
    past = (datetime.now() - timedelta(hours=3)).strftime("%H:%M")
    snap_file.write_text(json.dumps({"events": {"old": {"en": "Vaal", "t": past}}}))
    monitor = _make_monitor({"events": {}, "count": 0})
    healing = []
    result = _run_cycle(monitor, snap_file, healing)

    assert result is not None
    assert result["events"] == {}
    assert "SNAPSHOT_EMPTY_GUARD" not in healing
