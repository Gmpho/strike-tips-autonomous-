"""Sep-2026 audit remediation: fail-closed auth, PIN lockout, Chroma $and."""
import asyncio
import sys
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def _run(coro):
    return asyncio.run(coro)


def _req(path, headers=None, scope="http"):
    return SimpleNamespace(
        url=SimpleNamespace(path=path),
        headers=headers or {},
        scope={"type": scope},
        query_params={},
        receive=None,
    )


@pytest.fixture()
def security_mod(monkeypatch):
    import core_agent.core.security as sec
    monkeypatch.setattr(sec, "API_KEY", "test-key-123")
    return sec


async def _ok_next(request):
    class R:
        status_code = 200
    return R()


def test_v1_requires_key(security_mod):
    async def go(headers):
        return await security_mod.auth_middleware(_req("/v1/chat/completions", headers), _ok_next)

    # keyless /v1 must 401
    r = _run(go({}))
    assert getattr(r, "status_code", 200) == 401
    # wrong key must 401
    r = _run(go({"X-API-KEY": "nope"}))
    assert getattr(r, "status_code", 200) == 401


def test_v1_accepts_key_and_bearer(security_mod):
    async def go(path, headers):
        return await security_mod.auth_middleware(_req(path, headers), _ok_next)

    r = _run(go("/v1/chat/completions", {"X-API-KEY": "test-key-123"}))
    assert getattr(r, "status_code", None) == 200
    r = _run(go("/api/betting/open", {"Authorization": "Bearer test-key-123"}))
    assert getattr(r, "status_code", None) == 200


def test_safe_paths_stay_open(security_mod):
    for path in ["/", "/api/system/health", "/api/monitoring/stream", "/api/racing/exotics"]:
        r = _run(security_mod.auth_middleware(_req(path), _ok_next))
        assert getattr(r, "status_code", None) == 200, path


def test_fail_closed_without_server_key(monkeypatch):
    import core_agent.core.security as sec
    monkeypatch.setattr(sec, "API_KEY", "")

    r = _run(sec.auth_middleware(_req("/api/betting/open", {"X-API-KEY": "anything"}), _ok_next))
    assert getattr(r, "status_code", None) == 401


def test_pin_lockout(tmp_path, monkeypatch):
    import core_agent.core.access_control as ac
    monkeypatch.setattr(ac, "DATA_DIR", tmp_path)
    chat = 999001
    assert ac.pin_locked(chat) is False
    for _ in range(4):
        assert ac.record_pin_attempt(chat, False) is False
    assert ac.record_pin_attempt(chat, False) is True  # 5th trips lockout
    assert ac.pin_locked(chat) is True
    assert ac.record_pin_attempt(chat, True) is False  # success clears
    assert ac.pin_locked(chat) is False


def test_swarm_uses_and_filter():
    import core_agent.skills.swarm_researcher as sw
    import core_agent.skills.dreamer as _dm  # noqa - ensures sibling imports fine

    got = {}

    class FakeMem:
        _is_ready = True

        def search_form_insights(self, query, n_results=3, where=None):
            got["where"] = where
            return []

    fake_brain = SimpleNamespace(strike=None, memory=FakeMem())
    with patch.dict(sys.modules, {"core_agent.core.strike_brain": SimpleNamespace(brain=fake_brain)}):
        assert sw._fresh_insight_exists("Some Horse", "Vaal", "South Africa") is False
    where = got.get("where") or {}
    assert "$and" in where
    flat_keys = [k for k in where.keys() if not k.startswith("$")]
    assert flat_keys == []
