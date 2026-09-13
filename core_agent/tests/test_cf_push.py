"""Cloudflare push helper: single-key fallback, payload shape, never-raises."""
import asyncio
import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.core import cf_push


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Config modules load_dotenv() the repo .env in full-suite runs — clear
    ambient keys so tests never touch real credentials."""
    for var in ("CLOUDFLARE_MCP_URL", "CLOUDFLARE_API_KEY", "STRIKE_TIPS_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def _run(coro):
    return asyncio.run(coro)


def test_config_prefers_strike_key(monkeypatch):
    """STRIKE key is canonical; a stale legacy CF var must never win."""
    monkeypatch.setenv("CLOUDFLARE_MCP_URL", "https://cf.example")
    monkeypatch.setenv("CLOUDFLARE_API_KEY", "stale-cf-key")
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "strike-key")
    assert cf_push._cf_config() == ("https://cf.example", "strike-key")


def test_config_legacy_cf_key_used_when_strike_missing(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_KEY", "cf-key")
    url, key = cf_push._cf_config()
    assert url == cf_push.CF_WORKER_URL
    assert key == "cf-key"


def test_config_falls_back_to_strike_key(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_KEY", raising=False)
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "strike-key")
    url, key = cf_push._cf_config()
    assert url == cf_push.CF_WORKER_URL
    assert key == "strike-key"


def test_push_snapshot_no_key_no_raise(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_KEY", raising=False)
    monkeypatch.delenv("STRIKE_TIPS_API_KEY", raising=False)
    assert _run(cf_push.push_snapshot({"events": {"1": {}}})) is False


def test_push_snapshot_empty_state(monkeypatch):
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "k")
    assert _run(cf_push.push_snapshot({"events": {}})) is False
    assert _run(cf_push.push_snapshot({})) is False


def test_push_posts_with_key(monkeypatch):
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "strike-key")
    seen = {}

    class FakeResp:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            seen["url"] = url
            seen["headers"] = headers
            seen["json"] = json
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        assert _run(cf_push.push_snapshot({"events": {"1": {"a": 1}}})) is True
    assert seen["url"] == cf_push.CF_WORKER_URL + "/api/ingest-snapshot"
    assert seen["headers"]["x-api-key"] == "strike-key"


def test_push_insight_validates_and_truncates(monkeypatch):
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "k")
    assert _run(cf_push.push_insight("", "h", "c")) is False
    assert _run(cf_push.push_insight("d", "", "c")) is False
    assert _run(cf_push.push_insight("d", "h", "")) is False

    seen = {}

    class FakeResp:
        status_code = 200
        text = "ok"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            seen["json"] = json
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        assert _run(cf_push.push_insight("d" * 300, "h", "c", insight_type="official_card",
                                         track="vaal", race_number=3, date="2026-09-13")) is True
    body = seen["json"]
    assert len(body["doc_id"]) == 200
    assert body["type"] == "official_card"
    assert body["track"] == "vaal"


def test_401_retries_with_alternate_key(monkeypatch):
    """Secret shadowing: 401 on the primary retries once with the legacy key."""
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "primary-key")
    monkeypatch.setenv("CLOUDFLARE_API_KEY", "legacy-key")
    calls = []

    class FakeResp:
        def __init__(self, status_code):
            self.status_code = status_code
            self.text = "unauthorized" if status_code == 401 else "ok"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(headers.get("x-api-key"))
            return FakeResp(401 if len(calls) == 1 else 200)

    with patch("httpx.AsyncClient", FakeClient):
        assert _run(cf_push.push_snapshot({"events": {"1": {}}})) is True
    assert calls == ["primary-key", "legacy-key"]


def test_no_retry_when_keys_identical(monkeypatch):
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "same-key")
    monkeypatch.setenv("CLOUDFLARE_API_KEY", "same-key")
    calls = []

    class FakeResp:
        status_code = 401
        text = "unauthorized"

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, headers=None, json=None):
            calls.append(1)
            return FakeResp()

    with patch("httpx.AsyncClient", FakeClient):
        assert _run(cf_push.push_snapshot({"events": {"1": {}}})) is False
    assert len(calls) == 1


def test_push_failure_returns_false(monkeypatch):
    monkeypatch.setenv("STRIKE_TIPS_API_KEY", "k")

    class BadClient:
        def __init__(self, *a, **k):
            raise RuntimeError("no network")

    with patch("httpx.AsyncClient", BadClient):
        assert _run(cf_push.push_insight("d", "h", "c")) is False
