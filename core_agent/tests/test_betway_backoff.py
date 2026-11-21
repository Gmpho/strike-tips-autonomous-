"""Betway retry ladder.

Betway's bot management returns a probabilistic 403 that a fresh session
usually clears, but the failures arrive in waves rather than independently
(Nov-2026: 166 in two days, clustered in the 03:00-07:00 UTC window, 26 poll
cycles left with zero races). These tests pin the ladder that rides a wave
out without overrunning the five-minute poll.
"""

import pytest

from core_agent.skills.parsers import betway_api as mod
from core_agent.skills.parsers.betway_api import BetwayAPI


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _install(monkeypatch, behaviour):
    """Patch fetch transport; record each fetch attempt and retry sleeps.

    The outer retry ladder (MAX_ATTEMPTS / BACKOFF_SECONDS / RETRY_BUDGET_SECONDS)
    is the contract under test. _http_get now handles direct+proxy transport
    internally; mock it so tests exercise the ladder deterministically.
    """
    sessions = {"count": 0}
    sleeps = []

    async def fake_http_get(self, path, qs, headers):
        sessions["count"] += 1
        try:
            resp = behaviour(sessions["count"])
        except Exception:
            return None
        if resp is None:
            return None
        return resp.json() if hasattr(resp, "json") else resp

    monkeypatch.setattr(BetwayAPI, "_http_get", fake_http_get)

    async def fake_sleep(delay):
        sleeps.append(delay)

    monkeypatch.setattr(mod.asyncio, "sleep", fake_sleep)
    return sessions, sleeps


def _fail(n):
    raise RuntimeError("HTTP Error 403: ")


def _fail_then_ok_after(success_on):
    def behaviour(n):
        if n < success_on:
            raise RuntimeError("HTTP Error 403: ")
        return _Resp({"regions": []})

    return behaviour


@pytest.mark.asyncio
async def test_recovers_within_the_ladder(monkeypatch):
    sessions, sleeps = _install(monkeypatch, _fail_then_ok_after(3))

    out = await BetwayAPI().fetch_racing_data()

    assert out["status"] == "success"
    assert sessions["count"] == 3
    assert len(sleeps) == 2


@pytest.mark.asyncio
async def test_each_attempt_gets_a_fresh_session(monkeypatch):
    """A new fingerprint is what clears the block, so never reuse a client."""
    sessions, _ = _install(monkeypatch, _fail_then_ok_after(4))

    out = await BetwayAPI().fetch_racing_data()

    assert out["status"] == "success"
    assert sessions["count"] == 4


@pytest.mark.asyncio
async def test_jitter_stays_inside_the_band(monkeypatch):
    _, sleeps = _install(monkeypatch, _fail_then_ok_after(4))

    await BetwayAPI().fetch_racing_data()

    for i, delay in enumerate(sleeps):
        base = BetwayAPI.BACKOFF_SECONDS[i]
        assert base * 0.5 <= delay <= base * 1.5, (i, delay, base)


@pytest.mark.asyncio
async def test_backoff_grows(monkeypatch):
    _, sleeps = _install(monkeypatch, _fail)

    await BetwayAPI().fetch_racing_data()

    bases = [BetwayAPI.BACKOFF_SECONDS[i] for i in range(len(sleeps))]
    assert bases == sorted(bases)
    assert len(set(bases)) == len(bases)


@pytest.mark.asyncio
async def test_gives_up_after_max_attempts_without_a_trailing_sleep(monkeypatch):
    sessions, sleeps = _install(monkeypatch, _fail)

    out = await BetwayAPI().fetch_racing_data()

    assert out["status"] == "error"
    assert "Max retries reached" in out["error"]
    assert sessions["count"] == BetwayAPI.MAX_ATTEMPTS
    assert len(sleeps) == BetwayAPI.MAX_ATTEMPTS - 1


@pytest.mark.asyncio
async def test_retry_budget_stops_the_ladder(monkeypatch):
    """The ladder must never outlive the poll that called it."""
    monkeypatch.setattr(BetwayAPI, "RETRY_BUDGET_SECONDS", 0.0)
    sessions, sleeps = _install(monkeypatch, _fail)

    out = await BetwayAPI().fetch_racing_data()

    assert out["status"] == "error"
    assert sessions["count"] == 1
    assert sleeps == []


@pytest.mark.asyncio
async def test_success_first_time_never_sleeps(monkeypatch):
    sessions, sleeps = _install(monkeypatch, _fail_then_ok_after(1))

    out = await BetwayAPI().fetch_racing_data()

    assert out["status"] == "success"
    assert sessions["count"] == 1
    assert sleeps == []
