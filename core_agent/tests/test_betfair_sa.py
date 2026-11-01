import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.skills.parsers.betfair_sa import (
    BetfairSA,
    _normalize_gear,
    _parse_days,
)


# ---------------------------------------------------------------------------
# Helper / days normalization (pure functions)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("blinkers and tongue strap", "Blinkers · Tongue strap"),
        ("Hood / Tongue Strap", "Hood · Tongue strap"),
        ("BLINKERS", "Blinkers"),
        ("visor", "Visor"),
        ("tongue strap and hood", "Hood · Tongue strap"),
        ("some unknown gear", "Some Unknown Gear"),  # passthrough title-cased
        ("", None),
        (None, None),
        (123, None),
    ],)
def test_normalize_gear(raw, expected):
    assert _normalize_gear(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("16", 16),
        ("0", 0),
        ("  21 ", 21),
        (None, None),
        ("abc", None),
        ("-3", None),
        (14, 14),
    ],)
def test_parse_days(raw, expected):
    assert _parse_days(raw) == expected


# ---------------------------------------------------------------------------
# _parse_market shape
# ---------------------------------------------------------------------------
def _runner(name, wearing, days):
    return {
        "runnername": name,
        "metadata": {"wearing": wearing, "days_since_last_run": days},
    }


def test_parse_market_shape():
    api = BetfairSA()
    data = {
        "runners": [
            _runner("Task Force", "blinkers and tongue strap", "16"),
            _runner("Diaval", None, "21"),
            _runner("My China", "tongue strap", None),
        ],
        "event": {"name": "Scottsville", "startTime": 1788084420000},
        "markets": [{"name": "R1 1200m Mdn"}],
    }
    ev = api._parse_market("1.261657897", data)
    assert ev is not None
    assert ev["course"] == "Scottsville"
    assert ev["raceName"] == "R1 1200m Mdn"
    assert ev["t"] == "12:07"
    runners = ev["runners"]
    assert len(runners) == 3
    assert runners[0]["name"] == "Task Force"
    assert runners[0]["gear"] == "Blinkers · Tongue strap"
    assert runners[0]["daysSinceRun"] == 16
    # gear absent -> key omitted
    assert "gear" not in runners[1]
    assert runners[1]["daysSinceRun"] == 21
    # days absent -> key omitted
    assert runners[2]["gear"] == "Tongue strap"
    assert "daysSinceRun" not in runners[2]


def test_parse_market_empty_returns_none():
    assert BetfairSA()._parse_market("x", {"runners": []}) is None
    assert BetfairSA()._parse_market("x", None) is None


# ---------------------------------------------------------------------------
# get_form_format with mocked HTTP
# ---------------------------------------------------------------------------
def _mock_client(market_payload):
    """Build a fake async client: /all returns one RSA group, /market returns payload."""
    client = AsyncMock()

    async def fake_get(url, headers=None):
        resp = MagicMock()
        if "/horse-racing/7/all" in url:
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = [
                {
                    "id": "1549417158",
                    "name": "RSA",
                    "countryCode": "ZA",
                    "walletGroupId": 2,
                    "events": [
                        {
                            "id": "35993891",
                            "name": "Scottsville",
                            "markets": [
                                {"marketId": "1.261657897", "name": "R1 1200m Mdn"},
                                {"marketId": "1.261657898", "name": "R2 1200m Mdn"},
                            ],
                        }
                    ],
                }
            ]
        elif "/api/market/" in url:
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = market_payload
        else:
            resp.status_code = 404
            resp.raise_for_status = MagicMock()
        return resp

    client.get = fake_get
    return client


@pytest.mark.asyncio
async def test_get_form_format_end_to_end(tmp_path):
    payload = {
        "runners": [
            _runner("Task Force", "blinkers and tongue strap", "16"),
            _runner("Diaval", None, "21"),
        ],
        "event": {"name": "Scottsville", "startTime": 1788084420000},
        "markets": [{"name": "R1 1200m Mdn"}],
    }
    api = BetfairSA(cache_dir=tmp_path)
    with patch(
        "core_agent.skills.parsers.betfair_sa.get_async_client",
        return_value=_mock_client(payload),
    ):
        result = await api.get_form_format()

    assert result["count"] == 2  # two markets parsed
    for ev in result["events"].values():
        assert ev["course"] == "Scottsville"
        assert len(ev["runners"]) == 2
        names = [r["name"] for r in ev["runners"]]
        assert "Task Force" in names
        assert "Diaval" in names
    # cache file written
    assert list(tmp_path.glob("betfair_form_*.json"))


@pytest.mark.asyncio
async def test_get_form_format_no_markets(tmp_path):
    client = AsyncMock()
    async def fake_get(url, headers=None):
        resp = MagicMock()
        resp.status_code = 200
        resp.raise_for_status = MagicMock()
        resp.json.return_value = []  # no groups
        return resp
    client.get = fake_get
    api = BetfairSA(cache_dir=tmp_path)
    with patch(
        "core_agent.skills.parsers.betfair_sa.get_async_client",
        return_value=client,
    ):
        result = await api.get_form_format()
    assert result == {"events": {}, "count": 0}


@pytest.mark.asyncio
async def test_get_form_format_skips_failed_markets(tmp_path):
    """A market that fails all retries must not break the whole run."""
    client = AsyncMock()
    async def fake_get(url, headers=None):
        resp = MagicMock()
        if "/horse-racing/7/all" in url:
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            resp.json.return_value = [
                {
                    "id": "1549417158",
                    "name": "RSA",
                    "countryCode": "ZA",
                    "walletGroupId": 2,
                    "events": [
                        {
                            "id": "35993891",
                            "name": "Scottsville",
                            "markets": [{"marketId": "1.261657897", "name": "R1"}],
                        }
                    ],
                }
            ]
        else:
            resp.status_code = 500
            resp.raise_for_status = MagicMock()
        return resp
    client.get = fake_get
    api = BetfairSA(cache_dir=tmp_path)
    with patch(
        "core_agent.skills.parsers.betfair_sa.get_async_client",
        return_value=client,
    ):
        result = await api.get_form_format()
    assert result["count"] == 0  # market failed, gracefully skipped
