"""Cross-colo last-good cache: Modal parks successful fetches in KV.

The Worker cron writes `betway:raw:slot:*`; Modal writes `betway:raw:modal:*`.
Both are read back so a cycle landing in a colo Betway refuses still has real
races to publish. Tests mock the REST layer — no Cloudflare calls.
"""

import asyncio

from core_agent.core import cf_kv
from core_agent.skills.parsers.betway_api import BetwayAPI


def _detail(i, price=2.0):
    return {
        "eventId": str(1000 + i),
        "regionName": "South Africa",
        "leagueName": "Scottsville",
        "result": {"events": [{"eventId": 1000 + i, "odds": price}]},
    }


def test_put_details_chunks_and_writes(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    writes = {}

    async def fake_put(key, value, ttl_secs=None):
        writes[key] = value
        return True

    monkeypatch.setattr(cf_kv, "kv_put_json", fake_put)
    out = asyncio.run(cf_kv.put_details([_detail(i) for i in range(32)], now_iso="2026-11-22T00:00:00+00:00"))

    assert out == 3, "32 events at 15/slot = 3 KV writes"
    assert set(writes) == {
        f"betway:raw:modal:{i}" for i in range(3)
    }
    assert len(writes["betway:raw:modal:0"]["events"]) == 15
    assert len(writes["betway:raw:modal:2"]["events"]) == 2
    assert writes["betway:raw:modal:0"]["ts"] == "2026-11-22T00:00:00+00:00"
    entry = writes["betway:raw:modal:0"]["events"]["1000"]
    assert entry["region"] == "South Africa"
    assert entry["league"] == "Scottsville"


def test_put_details_noop_without_credentials(monkeypatch):
    monkeypatch.delenv("CF_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CF_API_TOKEN", raising=False)
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    called = []

    async def fake_put(*a, **kw):
        called.append(a)
        return True

    monkeypatch.setattr(cf_kv, "kv_put_json", fake_put)
    assert asyncio.run(cf_kv.put_details([_detail(0)])) == 0
    assert not called


def test_reader_prefers_modal_slots_over_cron_slots(monkeypatch):
    monkeypatch.setenv("CF_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CF_API_TOKEN", "tok")
    from datetime import datetime, timedelta, timezone

    def slot(ts, price):
        return {
            "ts": (datetime.now(timezone.utc) - timedelta(seconds=ts)).isoformat(),
            "events": {
                "1000": {
                    "payload": {"price": price},
                    "region": "South Africa",
                    "league": "Scottsville",
                }
            },
        }

    async def fake_get(key):
        if key == "betway:raw:modal:0":
            return slot(30, 2.5)
        if key == "betway:raw:slot:0":
            return slot(120, 9.0)
        return None

    monkeypatch.setattr(cf_kv, "kv_get_json", fake_get)
    out = asyncio.run(BetwayAPI().fetch_from_edge_kv())

    assert out["status"] == "success"
    assert len(out["details"]) == 1, "same event in both sources must not double"
    assert out["details"][0]["price"] == 2.5, "newer Modal slot must win"
