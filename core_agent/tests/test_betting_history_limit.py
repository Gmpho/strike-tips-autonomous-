"""GET /api/betting/history?limit=N — paint-fast window, full count."""
import asyncio
import json

import pytest

pytest.importorskip("fastapi")


def _bets(n):
    return [
        {
            "bet_id": f"2024010{i}_TST",
            "track": "turffontein",
            "race_number": 1,
            "horse": f"H{i}",
            "odds": 2.0,
            "edge_percent": 0.0,
            "stake": 1.0,
            "status": "WON",
            "timestamp": "2024-01-01T00:00:00",
            "actual_return": 2.0,
        }
        for i in range(n)
    ]


def test_history_limit_returns_newest_window_with_full_count(tmp_path, monkeypatch):
    (tmp_path / "bet_history.json").write_text(json.dumps(_bets(5)))
    import core_agent.routes.betting as b

    monkeypatch.setattr(b, "DATA_DIR", tmp_path)
    res = asyncio.run(b.get_bets(limit=2))
    assert [x["id"] for x in res["bets"]] == ["20240103_TST", "20240104_TST"]
    assert res["count"] == 5


def test_history_no_limit_returns_everything(tmp_path, monkeypatch):
    (tmp_path / "bet_history.json").write_text(json.dumps(_bets(5)))
    import core_agent.routes.betting as b

    monkeypatch.setattr(b, "DATA_DIR", tmp_path)
    res = asyncio.run(b.get_bets(limit=None))
    assert len(res["bets"]) == 5
    assert res["count"] == 5
