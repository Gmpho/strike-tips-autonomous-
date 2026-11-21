"""Betway refresh budget (Nov-2026).

A full international card is ~90 events, re-fetched every five minutes — over
a thousand `GetEvent` calls an hour from one datacenter IP, most of them for
races that jump twelve hours later. Betway's Cloudflare scoring tightens as
that volume rises, which is what produced the 90%-failure mornings.

The budget keeps near-off races fresh every cycle and lets far-off ones ride
on the price already in the snapshot: cheap for us, invisible to the punter,
and it never starves a race (hourly full sweep, and a failed fetch is retried
next cycle rather than parked).
"""

import json
import time

import pytest

from core_agent.skills.parsers import betway_api as mod
from core_agent.skills.parsers.betway_api import BetwayAPI

DAY = 86400


def _daily_payload(events):
    """GetDaily shape: one SA region holding the given (id, seconds_to_off)."""
    now = time.time()
    return {
        "regions": [
            {
                "name": "South Africa",
                "sportEvents": [
                    {
                        "eventId": eid,
                        "isFinished": False,
                        "league": "Turffontein",
                        "expectedStartEpoch": int(now + offset) if offset is not None else 0,
                    }
                    for eid, offset in events
                ],
            }
        ]
    }


def _install(monkeypatch, tmp_path, events, fail_ids=()):
    """Serve GetDaily/GetEvent from memory and record each GetEvent."""

    class API(BetwayAPI):
        async def _http_get(self, path, qs, headers):
            if path == "GetDaily":
                return _daily_payload(events)
            eid = int(qs.split("eventIds=")[1].split("&")[0])
            calls.append(eid)
            if eid in fail_ids:
                return None
            return {"eventId": eid, "events": [{"name": "R1"}]}

    calls = []
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: 0)
    return API(), calls


@pytest.mark.asyncio
async def test_first_cycle_fetches_everything(monkeypatch, tmp_path):
    """No bookkeeping yet means a full card — never a guessed subset."""
    api, calls = _install(monkeypatch, tmp_path, [(1, 1800), (2, 8 * 3600)])

    out = await api.fetch_racing_data()

    assert out["status"] == "success"
    assert sorted(calls) == [1, 2]


@pytest.mark.asyncio
async def test_second_cycle_skips_far_off_races(monkeypatch, tmp_path):
    """The near-off race is refreshed; the 8-hour-out one rides on the card."""
    api, calls = _install(monkeypatch, tmp_path, [(1, 1800), (2, 8 * 3600)])
    await api.fetch_racing_data()
    calls.clear()

    await api.fetch_racing_data()

    assert calls == [1], "only the near-off race should be re-fetched"


@pytest.mark.asyncio
async def test_far_off_race_is_refreshed_once_its_window_expires(monkeypatch, tmp_path):
    """Nothing is starved: a far-off race refreshes after FAR_REFRESH_SECONDS."""
    api, calls = _install(monkeypatch, tmp_path, [(1, 8 * 3600)])
    await api.fetch_racing_data()

    stale = time.time() - (BetwayAPI.FAR_REFRESH_SECONDS + 60)
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {"1": stale, "_last_sweep": time.time()})
    calls.clear()
    await api.fetch_racing_data()

    assert calls == [1]


@pytest.mark.asyncio
async def test_hourly_full_sweep_refetches_the_whole_card(monkeypatch, tmp_path):
    """The sweep is the safety net that makes the budget safe to ship."""
    api, calls = _install(monkeypatch, tmp_path, [(1, 8 * 3600), (2, 9 * 3600)])
    now = time.time()
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {
        "1": now, "2": now,
        "_last_sweep": now - (BetwayAPI.FULL_SWEEP_SECONDS + 1),
    })

    await api.fetch_racing_data()

    assert sorted(calls) == [1, 2]


@pytest.mark.asyncio
async def test_event_without_a_start_time_is_always_fetched(monkeypatch, tmp_path):
    """Unknown off time is not a licence to skip."""
    api, calls = _install(monkeypatch, tmp_path, [(1, None)])
    now = time.time()
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {"1": now, "_last_sweep": now})

    await api.fetch_racing_data()

    assert calls == [1]


@pytest.mark.asyncio
async def test_failed_event_is_retried_next_cycle(monkeypatch, tmp_path):
    """A 403 must not park the race for 25 minutes."""
    api, calls = _install(
        monkeypatch, tmp_path, [(1, 8 * 3600)], fail_ids={1}
    )
    await api.fetch_racing_data()
    now = time.time()
    state = json.loads((tmp_path / "budget.json").read_text())
    assert "1" not in state, "a failed fetch must not be stamped as fresh"
    calls.clear()

    monkeypatch.setattr(mod, "_REFRESH_CACHE", {**state, "_last_sweep": now})
    out = await api.fetch_racing_data()

    # The retry ladder hammers it inside the cycle (that is its job); the point
    # is that the budget did not park it for FAR_REFRESH_SECONDS afterwards.
    assert set(calls) == {1}
    assert out["status"] == "error"


@pytest.mark.asyncio
async def test_all_skipped_never_reports_a_broken_feed(monkeypatch, tmp_path):
    """A budget-only cycle must not look like a Betway outage."""
    api, calls = _install(monkeypatch, tmp_path, [(1, 18 * 3600)])
    now = time.time()
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {"1": now, "_last_sweep": now})

    out = await api.fetch_racing_data()

    assert out["status"] == "success"
    assert calls == [1], "an empty batch would be indistinguishable from a 403 wave"


def test_state_file_prunes_yesterdays_events(tmp_path, monkeypatch):
    """The state file must not grow across days on a persistent volume."""
    path = tmp_path / "budget.json"
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", path)
    now = time.time()

    mod._save_refresh_state({"old": now - 2 * DAY, "fresh": now}, now)

    assert json.loads(path.read_text()) == {"fresh": now}


def test_unreadable_state_file_means_fetch_everything(tmp_path, monkeypatch):
    """Corrupt bookkeeping must degrade to the safe default, not crash."""
    path = tmp_path / "budget.json"
    path.write_text("{not json")
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", path)

    assert mod._load_refresh_state() == {}
