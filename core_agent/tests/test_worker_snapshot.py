"""Prod HUD must prefer the freshest published card, not a blocked one.

The Modal cron can lose Betway to 403/520 while the home-network monitor
keeps quoting. Both publish to the Worker; the HUD serves whichever snapshot
is genuinely newer, and never lets a half-written or clock-skewed card win.
"""

import json
from types import SimpleNamespace

import pytest

from core_agent.core import worker_snapshot
from core_agent.routes import monitoring


def test_stamp_treats_naive_timestamps_as_utc():
    assert worker_snapshot._stamp("2026-11-21T09:52:05.085565") == pytest.approx(
        worker_snapshot._stamp("2026-11-21T09:52:05.085565Z")
    )
    assert worker_snapshot._stamp("2026-11-21T09:52:05+02:00") == pytest.approx(
        worker_snapshot._stamp("2026-11-21T07:52:05Z")
    )


def test_stamp_of_garbage_is_zero():
    assert worker_snapshot._stamp("") == 0.0
    assert worker_snapshot._stamp(None) == 0.0
    assert worker_snapshot._stamp("not-a-date") == 0.0


@pytest.mark.asyncio
async def test_worker_snapshot_is_memoised(monkeypatch):
    calls = []

    class Resp:
        status_code = 200

        def json(self):
            return {"events": {"a": {}}, "timestamp": "2026-11-21T09:52:05"}

    class Client:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            calls.append(url)
            return Resp()

    import httpx

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    monkeypatch.setattr(worker_snapshot, "_cached", None)
    monkeypatch.setattr(worker_snapshot, "_cached_at", 0.0)

    assert await worker_snapshot.fetch_best_snapshot()
    assert await worker_snapshot.fetch_best_snapshot()
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_effective_snapshot_prefers_newer_worker_card(monkeypatch):
    local = {"events": {"old": {}}, "timestamp": "2026-11-21T08:41:19"}
    remote = {"events": {"new": {}}, "timestamp": "2026-11-21T09:52:05"}
    monkeypatch.setattr(worker_snapshot, "fetch_best_snapshot", lambda: _asleep(remote))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(snapshot_cache=local)))

    out = await monitoring._effective_snapshot(request)

    assert "new" in out["events"]
    assert out["snapshot_source"] == "worker-home"


@pytest.mark.asyncio
async def test_effective_snapshot_keeps_local_when_worker_is_stale(monkeypatch):
    local = {"events": {"fresh": {}}, "timestamp": "2026-11-21T09:55:00"}
    remote = {"events": {"old": {}}, "timestamp": "2026-11-21T09:52:05"}
    monkeypatch.setattr(worker_snapshot, "fetch_best_snapshot", lambda: _asleep(remote))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(snapshot_cache=local)))

    out = await monitoring._effective_snapshot(request)

    assert "fresh" in out["events"]


@pytest.mark.asyncio
async def test_worker_unavailable_falls_back_to_local(monkeypatch):
    async def boom():
        raise RuntimeError("worker down")

    local = {"events": {"a": {}}, "timestamp": "2026-11-21T09:55:00"}
    monkeypatch.setattr(worker_snapshot, "fetch_best_snapshot", boom)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(snapshot_cache=local)))

    out = await monitoring._effective_snapshot(request)
    assert "a" in out["events"]


async def _asleep(value):
    """Async stand-in for the memoised worker fetch."""
    return value
