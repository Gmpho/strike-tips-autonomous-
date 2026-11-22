"""Edge KV bridge: Worker cron fetches Betway, Modal reads it over REST.

Modal's Azure egress is blocked by Betway on both the API and the racecard
HTML, and Modal -> *.workers.dev is blocked per Cloudflare colo. So the Worker
parks raw GetEvent payloads in KV and the monitor reads them through
api.cloudflare.com, which Modal *can* reach.
"""

from datetime import datetime, timedelta, timezone

import pytest

from core_agent.core import cf_kv
from core_agent.skills.parsers.betway_api import BetwayAPI


def _iso(seconds_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)).isoformat()


@pytest.fixture(autouse=True)
def _kv_env(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct-test")
    monkeypatch.setenv("CF_API_TOKEN", "tok-test")
    monkeypatch.setenv("CF_KV_NAMESPACE_ID", "ns-test")


def test_configured_requires_account_and_token(monkeypatch):
    assert cf_kv.configured() is True
    monkeypatch.delenv("CF_API_TOKEN")
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    assert cf_kv.configured() is False


def test_kv_get_returns_none_when_missing(monkeypatch):
    async def fake_get(self, url, headers=None, **kw):
        class R:
            status_code = 404
            text = "not found"

            def json(self):
                return {}
        return R()

    monkeypatch.setattr(cf_kv.httpx.AsyncClient, "get", fake_get)
    import asyncio
    assert asyncio.run(cf_kv.kv_get_json("betway:raw:slot:0")) is None


def test_kv_get_uses_rest_namespace_url(monkeypatch):
    seen = {}

    async def fake_get(self, url, headers=None, **kw):
        seen["url"] = url
        seen["auth"] = headers.get("Authorization")

        class R:
            status_code = 200

            def json(self):
                return {"ok": True}
        return R()

    monkeypatch.setattr(cf_kv.httpx.AsyncClient, "get", fake_get)
    import asyncio
    assert asyncio.run(cf_kv.kv_get_json("betway:raw:cursor")) == {"ok": True}
    assert seen["url"] == (
        "https://api.cloudflare.com/client/v4/accounts/acct-test/"
        "storage/kv/namespaces/ns-test/values/betway:raw:cursor"
    )
    assert seen["auth"] == "Bearer tok-test"


def _slot(events, age_secs):
    return {"ts": _iso(age_secs), "events": events}


def test_edge_kv_assembles_races_with_region_and_league(monkeypatch):
    """Region/league must survive the KV hop — the parser names courses by them."""
    payload = _slot(
        {
            "17511786": {
                "payload": {"result": {"events": [{"eventId": 17511786}]}},
                "region": "South Africa",
                "league": "Scottsville",
            }
        },
        40,
    )

    async def fake_get(key):
        return payload if key == "betway:raw:slot:0" else None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)

    import asyncio
    result = asyncio.run(BetwayAPI().fetch_from_edge_kv())
    assert result["status"] == "success"
    assert result["edge_kv"] is True
    det = result["details"][0]
    assert det["eventId"] == "17511786"
    assert det["regionName"] == "South Africa"
    assert det["leagueName"] == "Scottsville"
    assert det["_edge_age_secs"] == pytest.approx(40, abs=5)


def test_edge_kv_returns_none_when_cron_batch_is_stale(monkeypatch):
    """A dead cron must not be dressed up as a live feed."""
    async def fake_get(key):
        return _slot({"1": {"payload": {}, "region": "USA", "league": "X"}}, 7200)

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    import asyncio
    assert asyncio.run(BetwayAPI().fetch_from_edge_kv()) is None


def test_45_minute_old_card_is_still_served(monkeypatch):
    """A 45-min-old card stays visible with its age stamped, instead of blanking."""
    async def fake_get(key):
        if key == "betway:raw:modal:0":
            return _slot({"1": {"payload": {"price": 2.0}, "region": "USA", "league": "X"}}, 45 * 60)
        return None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    import asyncio
    result = asyncio.run(BetwayAPI().fetch_from_edge_kv())
    assert result is not None
    assert result["details"][0]["_edge_age_secs"] == pytest.approx(45 * 60, abs=10)


def test_edge_kv_returns_none_when_nothing_parked(monkeypatch):
    async def fake_get(key):
        return None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    import asyncio
    assert asyncio.run(BetwayAPI().fetch_from_edge_kv()) is None


def test_edge_kv_is_skipped_without_credentials(monkeypatch):
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)

    called = {"n": 0}

    async def fake_get(key):
        called["n"] += 1
        return None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    import asyncio
    assert asyncio.run(BetwayAPI().fetch_from_edge_kv()) is None
    assert called["n"] == 0, "no REST calls when unconfigured"


def test_duplicate_event_across_slots_is_kept_once(monkeypatch):
    older = _slot({"1": {"payload": {"a": 1}, "region": "South Africa", "league": "A"}}, 300)
    newer = _slot({"1": {"payload": {"a": 2}, "region": "South Africa", "league": "A"}}, 30)

    async def fake_get(key):
        if key == "betway:raw:slot:0":
            return newer
        if key == "betway:raw:slot:1":
            return older
        return None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    import asyncio
    result = asyncio.run(BetwayAPI().fetch_from_edge_kv())
    assert len(result["details"]) == 1
    assert result["details"][0]["a"] == 2, "the fresher slot wins"
