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


@pytest.fixture(autouse=True)
def _isolated_egress_state(tmp_path, monkeypatch):
    """Each test gets its own egress-state file — never touch the real one."""
    monkeypatch.setattr(mod, "_EGRESS_STATE_PATH", tmp_path / "egress.json")
    monkeypatch.setattr(mod, "_DAILY_CACHE_PATH", tmp_path / "daily.json")


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


def _install(monkeypatch, tmp_path, events, fail_ids=(), flaky_ids=()):
    """Serve GetDaily/GetEvent from memory and record each GetEvent."""

    attempts: dict = {}

    class API(BetwayAPI):
        async def _http_get(self, path, qs, headers):
            if path == "GetDaily":
                return _daily_payload(events)
            eid = int(qs.split("eventIds=")[1].split("&")[0])
            calls.append(eid)
            if eid in fail_ids:
                return None
            if eid in flaky_ids:
                attempts[eid] = attempts.get(eid, 0) + 1
                if attempts[eid] == 1:
                    return None  # first call in the wave 520s
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


@pytest.mark.asyncio
async def test_flaky_events_are_recovered_in_one_second_pass(monkeypatch, tmp_path):
    """A race that 520s once must not vanish while its stable neighbours win."""
    monkeypatch.setattr(mod.BetwayAPI, "EVENT_RETRY_DELAY_SECONDS", 0)
    api, calls = _install(
        monkeypatch, tmp_path, [(1, 1800), (2, 1800), (3, 1800)], flaky_ids={2, 3}
    )

    out = await api.fetch_racing_data()

    assert out["status"] == "success"
    assert {d["eventId"] for d in out["details"]} == {1, 2, 3}
    # One initial call + one bounded second pass for each flaky race.
    assert calls.count(2) == 2 and calls.count(3) == 2
    assert calls.count(1) == 1, "stable races must not be re-fetched"


@pytest.mark.asyncio
async def test_total_outage_is_not_doubled_by_the_second_pass(monkeypatch, tmp_path):
    """When every call fails, retrying all of them just feeds the bot score."""
    monkeypatch.setattr(mod.BetwayAPI, "EVENT_RETRY_DELAY_SECONDS", 0)
    api, calls = _install(
        monkeypatch, tmp_path, [(1, 1800), (2, 1800)], fail_ids={1, 2}
    )

    out = await api.fetch_racing_data()

    # 5 ladder attempts x 2 events, with no second pass on top.
    assert out["status"] == "error"
    assert len(calls) == BetwayAPI.MAX_ATTEMPTS * 2


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


# ── Bounded direct -> Worker switch ─────────────────────────────────────────


def test_two_daily_failures_switch_events_to_worker_only():
    """Two blocked GetDaily attempts must spare the other ~200 GetEvents."""
    api = BetwayAPI()
    api.start_cycle()

    assert api._should_try_direct("GetEvent") is True
    api._note_direct_result("GetDaily", False)
    assert api._should_try_direct("GetEvent") is True  # one failure may be noise
    api._note_direct_result("GetDaily", False)

    assert api._direct_blocked is True
    assert api._should_try_direct("GetEvent") is False
    assert api._should_try_direct("GetDaily") is False  # no more this cycle


def test_blocked_egress_stays_proxy_only_until_the_hourly_probe():
    """One direct probe an hour — not a fresh blocked request per event."""
    api = BetwayAPI()
    api.start_cycle()
    api._note_direct_result("GetDaily", False)
    api._note_direct_result("GetDaily", False)

    for _ in range(BetwayAPI.DIRECT_PROBE_EVERY_CYCLES):
        api.start_cycle()
        assert api._should_try_direct("GetDaily") is False
        assert api._should_try_direct("GetEvent") is False

    api.start_cycle()
    assert api._should_try_direct("GetDaily") is True   # probe
    assert api._should_try_direct("GetEvent") is False  # still proxy-only


def test_direct_success_clears_the_block():
    """A successful probe must restore direct fetches completely."""
    api = BetwayAPI()
    api.start_cycle()
    api._note_direct_result("GetDaily", False)
    api._note_direct_result("GetDaily", False)
    api.start_cycle()

    api._note_direct_result("GetDaily", True)

    assert api._direct_blocked is False
    assert api._cycles_since_probe == 0
    assert api._should_try_direct("GetEvent") is True


def test_per_event_failures_do_not_switch_the_egress():
    """A Betway origin 520 on one race is not evidence our IP is blocked."""
    api = BetwayAPI()
    api.start_cycle()
    for _ in range(10):
        api._note_direct_result("GetEvent", False)

    assert api._direct_blocked is False
    assert api._should_try_direct("GetEvent") is True


def test_egress_block_survives_a_fresh_container():
    """Two failed probes must spare every following cycle's events."""
    first = BetwayAPI()
    first.start_cycle()
    first._note_direct_result("GetDaily", False)
    first._note_direct_result("GetDaily", False)

    # Modal cron = new container + new BetwayAPI each cycle.
    second = BetwayAPI()
    second.start_cycle()
    assert second._should_try_direct("GetDaily") is False
    assert second._should_try_direct("GetEvent") is False


def test_hourly_probe_happens_across_fresh_containers():
    """The probe interval is real, not just an in-memory counter."""
    api = BetwayAPI()
    api.start_cycle()
    api._note_direct_result("GetDaily", False)
    api._note_direct_result("GetDaily", False)

    for _ in range(BetwayAPI.DIRECT_PROBE_EVERY_CYCLES):
        fresh = BetwayAPI()
        fresh.start_cycle()
        assert fresh._should_try_direct("GetDaily") is False

    prober = BetwayAPI()
    prober.start_cycle()
    assert prober._should_try_direct("GetDaily") is True   # hourly probe
    assert prober._should_try_direct("GetEvent") is False  # events still proxy-only


def test_direct_success_unblocks_disk_state_for_the_next_container():
    """A successful probe clears the block for every sibling container."""
    api = BetwayAPI()
    api.start_cycle()
    api._note_direct_result("GetDaily", False)
    api._note_direct_result("GetDaily", False)
    prober = BetwayAPI()
    prober.start_cycle()
    prober._note_direct_result("GetDaily", True)

    assert mod._load_egress_state()["blocked"] is False
    next_cycle = BetwayAPI()
    next_cycle.start_cycle()
    assert next_cycle._should_try_direct("GetEvent") is True


def test_corrupt_egress_state_fails_open_to_direct():
    """Unreadable state must never park the feed behind a dead proxy."""
    path = mod._EGRESS_STATE_PATH
    with open(path, "w") as f:
        f.write("{not json")
    api = BetwayAPI()
    api.start_cycle()

    assert api._should_try_direct("GetDaily") is True
    assert api._should_try_direct("GetEvent") is True


# ── Cached GetDaily fallback ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_getdaily_outage_still_refreshes_near_off_races(monkeypatch, tmp_path):
    """A failed gate must not freeze races that became near-off meanwhile."""
    near, far = 1, 2
    daily_fail = {"value": False}
    calls = []

    class API(BetwayAPI):
        async def _http_get(self, path, qs, headers):
            if path == "GetDaily":
                if daily_fail["value"]:
                    return None
                return _daily_payload([(near, 1800), (far, 18 * 3600)])
            eid = int(qs.split("eventIds=")[1].split("&")[0])
            calls.append(eid)
            return {"eventId": eid, "events": [{"name": "R1"}]}

    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: 0)

    api = API()
    first = await api.fetch_racing_data()
    assert first["status"] == "success"
    assert first.get("daily_from_cache") is False
    calls.clear()

    daily_fail["value"] = True
    second = await api.fetch_racing_data()

    assert second["status"] == "success", "a down GetDaily must not blank the card"
    assert second.get("daily_from_cache") is True
    assert calls == [near], "only the near-off race is fetched from the cached card"


@pytest.mark.asyncio
async def test_getdaily_outage_without_a_cache_is_still_an_error(monkeypatch, tmp_path):
    """Never invent a card: no cached ids means fail loud as before."""
    class API(BetwayAPI):
        async def _http_get(self, path, qs, headers):
            return None

    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: 0)

    out = await API().fetch_racing_data()
    assert out["status"] == "error"
    assert "GetDaily returned no data" in out["error"]


@pytest.mark.asyncio
async def test_stale_daily_cache_is_not_used(monkeypatch, tmp_path):
    """A six-hour-old card is not a valid substitute for today's meetings."""
    path = mod._DAILY_CACHE_PATH
    with open(path, "w") as f:
        json.dump({"ts": time.time() - 7 * 3600,
                   "payload": _daily_payload([(1, 1800)])}, f)
    assert mod._load_daily_cache() is None


@pytest.mark.asyncio
async def test_blocked_cycle_never_calls_the_direct_client(monkeypatch, tmp_path):
    """End-to-end: once blocked, fetch_racing_data goes straight to the Worker."""
    import httpx

    daily = _daily_payload([(1, 1800)])

    class DirectResp:
        status_code = 403

        def raise_for_status(self):
            raise RuntimeError("403")

    class DirectClient:
        def __init__(self, **kwargs):
            pass

        async def get(self, url, headers=None):
            direct_calls.append(url)
            return DirectResp()

    class WorkerResp:
        def __init__(self, path):
            self.status_code = 200
            self._path = path

        @property
        def text(self):
            payload = daily if self._path == "GetDaily" else {"result": {"events": [{"name": "R1"}]}}
            return json.dumps(payload)

        def json(self):
            return json.loads(self.text)

    class WorkerClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, headers=None):
            path = params.get("path")
            worker_calls.append(path)
            return WorkerResp(path)

    direct_calls, worker_calls = [], []
    monkeypatch.setattr(mod, "get_async_client", lambda **kw: DirectClient())
    monkeypatch.setattr(httpx, "AsyncClient", WorkerClient)
    monkeypatch.setattr(mod, "_REFRESH_CACHE", {})
    monkeypatch.setattr(mod, "_REFRESH_STATE_PATH", tmp_path / "budget.json")
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: 0)

    api = BetwayAPI()
    # Cycle 1 and 2 each see one blocked direct GetDaily; the proxy answers,
    # so the failure count carries across cycles until the threshold trips.
    await api.fetch_racing_data()
    await api.fetch_racing_data()
    assert api._direct_blocked is True

    direct_calls.clear()
    worker_calls.clear()
    await api.fetch_racing_data()   # cycle 3: proxy-only

    assert len(direct_calls) < 2 * BetwayAPI.DIRECT_FAILURE_THRESHOLD
    assert "GetDaily" in worker_calls and "GetEvent" in worker_calls

    direct_calls.clear()
    worker_calls.clear()
    await api.fetch_racing_data()   # still proxy-only (no probe yet)

    assert direct_calls == [], "no blocked direct request in a proxy-only cycle"
    assert "GetDaily" in worker_calls and "GetEvent" in worker_calls
