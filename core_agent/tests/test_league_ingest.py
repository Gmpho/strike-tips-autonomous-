"""Tests for operator race results ingestion and CLI settlement trigger."""
import json
import os
import pytest

from core_agent.skills.league.ingest_card import ingest_single_race, ingest_from_file
from core_agent.skills.league.results_feed import load_confirmed_results
from core_agent.skills.league.settlement import settle_open_picks


def _write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def test_ingest_single_race_and_settle(tmp_path):
    picks_path = tmp_path / "league_picks.jsonl"
    _write_jsonl(str(picks_path), [
        {
            "user_id": "u1",
            "course": "Doncaster",
            "date": "2026-11-06",
            "race_number": "1",
            "runner_name": "Silver Chariot",
            "runner_number": 3,
            "settled": False,
        },
        {
            "user_id": "u2",
            "course": "Doncaster",
            "date": "2026-11-06",
            "race_number": "1",
            "runner_name": "Bronze Runner",
            "runner_number": 5,
            "settled": False,
        },
        {
            "user_id": "u3",
            "course": "Doncaster",
            "date": "2026-11-06",
            "race_number": "1",
            "runner_name": "Unplaced Horse",
            "runner_number": 9,
            "settled": False,
        },
    ])

    result = ingest_single_race(
        data_dir=str(tmp_path),
        course="doncaster",
        date="2026-11-06",
        race_number="1",
        winner="Silver Chariot",
        sp=4.5,
        place2="Second Horse",
        place3="Bronze Runner",
    )

    assert result["ok"] is True
    assert result["races_ingested"] == 1
    assert result["settlement"]["settled"] == 3
    # Top 4 score points (Silver Chariot 1st, Bronze Runner 3rd) -> 2 scored, Unplaced Horse lost
    assert result["settlement"]["won"] == 2

    # Check confirmed_results.jsonl content
    confirmed = load_confirmed_results(str(tmp_path))
    assert len(confirmed) == 1
    assert confirmed[0]["course"] == "doncaster"
    assert confirmed[0]["runners"][0]["name"] == "Silver Chariot"
    assert confirmed[0]["runners"][0]["position"] == 1
    assert confirmed[0]["runners"][0]["odds_decimal"] == 4.5
    assert confirmed[0]["runners"][2]["name"] == "Bronze Runner"
    assert confirmed[0]["runners"][2]["position"] == 3


def test_ingest_from_file(tmp_path):
    json_path = tmp_path / "incoming_results.json"
    with open(json_path, "w") as f:
        json.dump([
            {
                "course": "Aintree",
                "date": "2026-11-06",
                "race_number": 2,
                "runners": [
                    {"name": "Winner Horse", "position": 1, "odds_decimal": 2.5},
                    {"name": "Loser Horse", "position": 5, "odds_decimal": 10.0},
                ],
            }
        ], f)

    result = ingest_from_file(str(tmp_path), str(json_path))
    assert result["ok"] is True
    assert result["races_ingested"] == 1

    confirmed = load_confirmed_results(str(tmp_path))
    assert len(confirmed) == 1
    assert confirmed[0]["course"] == "Aintree"


def test_league_ingest_route(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    import asyncio
    from core_agent.routes.league import ingest_results, IngestResultsIn, RaceResultIn, ResultRunnerIn
    import core_agent.routes.league as league_module

    monkeypatch.setattr(league_module, "DATA_DIR", tmp_path)
    # mock _commit_volume
    monkeypatch.setattr(league_module, "_commit_volume", lambda: None)

    body = IngestResultsIn(
        races=[
            RaceResultIn(
                date="2026-11-06",
                course="Doncaster",
                race_number=1,
                runners=[
                    ResultRunnerIn(name="Winner Horse", position=1, odds_decimal=3.0),
                    ResultRunnerIn(name="Second Horse", position=2, odds_decimal=4.0),
                ],
            )
        ]
    )
    res = asyncio.run(ingest_results(body))
    assert res["ok"] is True
    assert res["races_ingested"] == 1
    assert "settlement" in res

