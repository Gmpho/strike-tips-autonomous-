"""Governor read paths must see bets written by another container.

Oct-2026: the warm web container loaded bet_history.json in __init__ and never
re-read it, so after the 05:00 scan (which runs in a different Modal container)
/api/betting/bankroll reported R9.60 exposure instead of the real R342.60, and
flip-flopped between values depending on which container answered.
"""

import json
import os
import time

import pytest

from core_agent.skills.bankroll_manager.governor import BankrollGovernor


@pytest.fixture
def gov(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return BankrollGovernor(data_dir=str(data), starting_bankroll=1000.0)


def _append_pending(data_dir, bet_id="20261025050900_WIN_R5", stake=120.0, day=None):
    path = os.path.join(data_dir, "bet_history.json")
    try:
        with open(path) as f:
            raw = json.load(f)
    except Exception:
        raw = []
    raw.append({
        "bet_id": bet_id,
        "timestamp": "2026-10-25T05:09:00",
        "date": day or "2026-10-25",
        "track": "greyville",
        "race_number": 5,
        "horse": "Master Bomber",
        "odds": 7.0,
        "stake": stake,
        "potential_return": stake * 7.0,
        "status": "PENDING",
        "edge_percent": 8.0,
        "confidence": "VALUE",
        "notes": "",
        "is_paper": True,
    })
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(raw, f)
    os.replace(tmp, path)


def test_exposure_picks_up_external_write(gov):
    assert gov.get_open_exposure() == 0.0

    _append_pending(gov.data_dir)
    os.utime(os.path.join(gov.data_dir, "bet_history.json"), (time.time() + 1, time.time() + 1))

    assert gov.get_open_exposure() == pytest.approx(120.0)
    assert len(gov.get_open_bets()) == 1


def test_mtime_guard_skips_redundant_reload(gov, monkeypatch):
    gov.get_open_exposure()  # prime the mtime cache
    calls = []
    monkeypatch.setattr(gov, "_load_state", lambda *a, **k: calls.append(1))

    gov.get_open_exposure()
    gov.get_open_exposure()
    assert calls == []


def test_force_reload_bypasses_guard(gov, monkeypatch):
    gov.get_open_exposure()
    calls = []
    monkeypatch.setattr(gov, "_load_state", lambda *a, **k: calls.append(1))

    gov.refresh_from_disk(force=True)
    assert len(calls) == 1


def test_today_stats_sees_external_write(gov):
    from datetime import date

    _append_pending(
        gov.data_dir,
        bet_id="20261025050901_WIN_R6",
        stake=80.0,
        day=date.today().isoformat(),
    )
    path = os.path.join(gov.data_dir, "bet_history.json")
    os.utime(path, (time.time() + 1, time.time() + 1))

    stats = gov.get_today_stats()
    assert stats.bets_placed == 1
    assert stats.total_staked == pytest.approx(80.0)
