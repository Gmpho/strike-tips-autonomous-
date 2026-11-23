"""KV-cached prices + GetDaily's full field (2026-11-23).

The edge KV cache holds only races whose GetEvent once answered. While Betway
403s, that was 45 races while GetDaily listed 64 — the rest were absent from
the HUD. Augmenting the KV result with today's price-less GetDaily rows fixes
the gap without another Betway request.
"""

from core_agent.skills.parsers import betway_api as mod
from core_agent.skills.parsers.betway_api import BetwayAPI


def _daily_payload(events):
    return {
        "regions": [{
            "name": "USA",
            "sportEvents": [{
                "eventId": eid,
                "isFinished": False,
                "league": "Zia Park",
                "expectedStartEpoch": 9999999999,
                "sportSpecificProperties": {"raceNumber": "1"},
                "raceEventDetails": {"racers": [
                    {"outcomeIds": [eid], "outcomeName": "Runner A", "number": "1"}
                ]},
            } for eid in events],
        }]
    }


def test_edge_result_gets_unpriced_rows_and_daily_ids(tmp_path, monkeypatch):
    path = tmp_path / "daily.json"
    monkeypatch.setattr(mod, "_DAILY_CACHE_PATH", str(path))
    mod._save_daily_cache(_daily_payload([101, 102, 103]))

    edge = {
        "status": "success",
        "details": [{
            "eventId": 101,
            "regionName": "USA",
            "leagueName": "Zia Park",
            "result": {"events": [{"eventId": 101}], "prices": [{"priceDecimal": 3.0}]},
        }],
    }
    api = BetwayAPI()
    api._augment_edge_with_daily(edge)

    assert [d["eventId"] for d in edge["details"]] == [101, 102, 103]
    assert edge["daily_unpriced"] == 2
    assert edge["daily_ids"] == [101, 102, 103]
    assert edge["details"][1]["price_source"] == "daily"
    assert edge["details"][0].get("price_source") is None


def test_no_fresh_daily_cache_leaves_edge_result_untouched(tmp_path, monkeypatch):
    monkeypatch.setattr(mod, "_DAILY_CACHE_PATH", str(tmp_path / "missing.json"))
    edge = {"status": "success", "details": []}
    BetwayAPI()._augment_edge_with_daily(edge)
    assert edge == {"status": "success", "details": []}


def test_no_duplicate_of_a_race_already_in_the_kv_cache(tmp_path, monkeypatch):
    path = tmp_path / "daily.json"
    monkeypatch.setattr(mod, "_DAILY_CACHE_PATH", str(path))
    mod._save_daily_cache(_daily_payload([101, 102]))
    edge = {
        "status": "success",
        "details": [{
            "eventId": 101,
            "regionName": "USA",
            "leagueName": "Zia Park",
            "result": {"events": [{"eventId": 101}], "prices": []},
        }],
    }
    BetwayAPI()._augment_edge_with_daily(edge)
    assert [d["eventId"] for d in edge["details"]] == [101, 102]
