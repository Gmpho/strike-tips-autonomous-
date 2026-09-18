"""Abandoned-meeting detection + snapshot disk refresh (Sep-2026).

Greyville was abandoned with zero results posted: singles sat PENDING with
no path to a refund (EXPIRED pays nothing). Declaration needs a fully dark
board — never a slow feed.
"""

import asyncio
import json
from datetime import datetime, timedelta, timezone

import pytest

from core_agent.skills.result_tracker import _meeting_is_abandoned
from core_agent.core import snapshot_cache

_SAST = timezone(timedelta(hours=2))


def _off(minutes_ago):
    return datetime.now(_SAST) - timedelta(minutes=minutes_ago)


def test_abandoned_dark_board():
    assert _meeting_is_abandoned(
        [_off(200), _off(150)], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is True


def test_live_race_vetoes():
    assert _meeting_is_abandoned(
        [_off(200), datetime.now(_SAST) + timedelta(minutes=30)],
        atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is False


def test_track_results_veto():
    assert _meeting_is_abandoned(
        [_off(200)], atr_track_empty=False, atr_day_ok=True,
        now=datetime.now(_SAST)) is False


def test_day_fetch_failure_vetoes():
    """ATR down globally must never read as abandonment."""
    assert _meeting_is_abandoned(
        [_off(200)], atr_track_empty=True, atr_day_ok=False,
        now=datetime.now(_SAST)) is False


def test_no_known_offs_never_declares():
    assert _meeting_is_abandoned(
        [None, None], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is False
    assert _meeting_is_abandoned(
        [], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is False


def test_grace_boundary():
    assert _meeting_is_abandoned(
        [_off(89)], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is False
    assert _meeting_is_abandoned(
        [_off(91)], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is True


def test_naive_off_treated_as_sast():
    naive = (datetime.now(_SAST) - timedelta(minutes=200)).replace(tzinfo=None)
    assert _meeting_is_abandoned(
        [naive], atr_track_empty=True, atr_day_ok=True,
        now=datetime.now(_SAST)) is True


@pytest.mark.asyncio
async def test_disk_refresh_picks_up_new_file(tmp_path, monkeypatch):
    snap_file = tmp_path / "market_snapshot_latest.json"
    snap_file.write_text(json.dumps({"events": {"a": {"course": "vaal"}}}))
    monkeypatch.setattr(snapshot_cache, "MARKET_SNAPSHOT_PATH", str(snap_file))
    monkeypatch.setattr(snapshot_cache, "_last_disk_mtime", 0.0)
    snapshot_cache.set_snapshot({"events": {}})
    task = asyncio.create_task(snapshot_cache.disk_refresh_loop(interval=1))
    try:
        await asyncio.wait_for(_wait_for_events(), timeout=10)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    assert "a" in snapshot_cache.get_snapshot().get("events", {})


async def _wait_for_events():
    while "a" not in snapshot_cache.get_snapshot().get("events", {}):
        await asyncio.sleep(0.2)
