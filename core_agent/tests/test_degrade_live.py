"""Edge-case robustness tests for the Betfair SA parser when Betfair returns
non-JSON / error / partial responses (cookie wall, rate limit, etc.)."""
import pytest
from unittest.mock import MagicMock, patch

from core_agent.skills.parsers.betfair_sa import BetfairSA


def _resp(status: int, body=None, raise_status: bool = False):
    r = MagicMock()
    r.status_code = status
    if raise_status:
        r.raise_for_status = MagicMock(side_effect=Exception(f"HTTP {status}"))
    else:
        r.raise_for_status = MagicMock()
    r.json = MagicMock(return_value=body)
    return r


@pytest.mark.asyncio
async def test_null_json_body_returns_empty():
    """Betfair returns null (cookie wall) -> parser must not raise, returns empty."""
    async def mock_get(url, headers=None, **kw):
        return _resp(200, None)
    class FakeClient:
        async def get(self, *a, **k): return await mock_get(*a, **k)
    with patch("core_agent.skills.parsers.betfair_sa.get_async_client", return_value=FakeClient()):
        api = BetfairSA(time_ranges=["TODAY", "TOMORROW"])
        out = await api.get_form_format()
    assert out == {"events": {}, "count": 0}


@pytest.mark.asyncio
async def test_non_list_json_returns_empty():
    """Betfair returns {} (HTML/login page) -> parser must skip that range."""
    async def mock_get(url, headers=None, **kw):
        return _resp(200, {"error": "unauthorized"})
    class FakeClient:
        async def get(self, *a, **k): return await mock_get(*a, **k)
    with patch("core_agent.skills.parsers.betfair_sa.get_async_client", return_value=FakeClient()):
        api = BetfairSA(time_ranges=["TODAY", "TOMORROW"])
        out = await api.get_form_format()
    assert out == {"events": {}, "count": 0}


@pytest.mark.asyncio
async def test_401_unauthorized_returns_empty():
    async def mock_get(url, headers=None, **kw):
        return _resp(401, None, raise_status=True)
    class FakeClient:
        async def get(self, *a, **k): return await mock_get(*a, **k)
    with patch("core_agent.skills.parsers.betfair_sa.get_async_client", return_value=FakeClient()):
        api = BetfairSA(time_ranges=["TODAY", "TOMORROW"])
        out = await api.get_form_format()
    assert out == {"events": {}, "count": 0}


@pytest.mark.asyncio
async def test_list_with_none_entries_handled():
    """Betfair returns a list that contains None entries (defensive)."""
    async def mock_get(url, headers=None, **kw):
        return _resp(200, [None, {"id": "x", "name": "RSA", "countryCode": "ZA",
                                     "events": [], "walletGroupId": 1}])
    class FakeClient:
        async def get(self, *a, **k): return await mock_get(*a, **k)
    with patch("core_agent.skills.parsers.betfair_sa.get_async_client", return_value=FakeClient()):
        api = BetfairSA(time_ranges=["TODAY"])
        out = await api.get_form_format()
    assert out == {"events": {}, "count": 0}  # no markets -> empty
