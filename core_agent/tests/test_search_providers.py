"""Free-tier search cascade: Tavily -> Exa -> DDGS (all network mocked)."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from core_agent.skills import search_service as ss


def _resp(status, payload):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = payload
    return m


def _client_for(resp):
    c = MagicMock()
    c.post = AsyncMock(return_value=resp)
    c.get = AsyncMock(return_value=MagicMock(status_code=404, text=""))
    return c


def _run(coro):
    return asyncio.run(coro)


def test_tavily_first_on_hit(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tv-test")
    monkeypatch.setenv("EXA_API_KEY", "")
    resp = _resp(200, {"results": [
        {"title": "T", "url": "https://a.com/1", "content": "x" * 10},
    ]})
    with patch.object(ss, "get_async_client", return_value=_client_for(resp)):
        with patch.object(ss, "_budget_used", return_value={}):
            with patch.object(ss, "_budget_spend") as spend:
                out = _run(ss.search_racing("kenilworth results", limit=3))
    assert out["provider"] == "tavily"
    assert out["results"][0]["url"] == "https://a.com/1"
    spend.assert_called_once_with("tavily")


def test_exa_fallback_when_tavily_empty(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "")
    monkeypatch.setenv("EXA_API_KEY", "exa-test")
    resp = _resp(200, {"results": [
        {"title": "E", "url": "https://b.com/2", "text": "y" * 10},
    ]})
    with patch.object(ss, "get_async_client", return_value=_client_for(resp)):
        with patch.object(ss, "_budget_used", return_value={}):
            out = _run(ss.search_racing("greyville form", limit=3))
    assert out["provider"] == "exa"
    assert out["results"][0]["url"] == "https://b.com/2"


def test_budget_exhaustion_skips_provider(monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "tv-test")
    monkeypatch.setenv("EXA_API_KEY", "")
    with patch.object(ss, "_budget_used", return_value={"tavily": 1000}):
        with patch.object(ss, "get_async_client") as client:
            out = _run(ss.search_racing("vaal odds", limit=3))
    client.post.assert_not_called()
    assert out["provider"] in ("none", "ddgs")


def test_budget_roundtrip_tmp(tmp_path, monkeypatch):
    import core_agent.skills.search_service as s2

    monkeypatch.setattr(s2, "_budget_path", lambda: str(tmp_path / "b.json"))
    assert s2._budget_used() == {}
    s2._budget_spend("tavily")
    s2._budget_spend("tavily")
    assert s2._budget_used() == {"tavily": 2}
