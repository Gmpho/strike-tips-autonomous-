"""Corrupt-wipe guard: a malformed ledger file must never be overwritten
by its empty in-memory interpretation (Oct-2026 review finding)."""
import json


def _gov(tmp_path, monkeypatch=None):
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor
    return BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)


def test_corrupt_history_blocks_save(tmp_path):
    (tmp_path / "bet_history.json").write_text("{not valid json")
    g = _gov(tmp_path)
    assert g._state_corrupt is True
    assert g._bets == []
    before = (tmp_path / "bet_history.json").read_text()
    g._save_state()  # must refuse
    assert (tmp_path / "bet_history.json").read_text() == before


def test_corrupt_state_blocks_save(tmp_path):
    (tmp_path / "bankroll_state.json").write_text("garbage{{{")
    (tmp_path / "bet_history.json").write_text("[]")
    g = _gov(tmp_path)
    assert g._state_corrupt is True
    assert g.current_bankroll == 1000.0
    g._save_state()
    assert not (tmp_path / "bankroll_state.json").exists() or \
        (tmp_path / "bankroll_state.json").read_text() == "garbage{{{"
    assert "garbage" in (tmp_path / "bankroll_state.json").read_text()


def test_repair_recovers_without_restart(tmp_path):
    (tmp_path / "bet_history.json").write_text("{broken")
    g = _gov(tmp_path)
    assert g._state_corrupt is True
    # operator restores the file; next load clears the flag, saves resume
    (tmp_path / "bet_history.json").write_text("[]")
    g._load_state(1000.0)
    assert g._state_corrupt is False
    g._save_state()
    data = json.loads((tmp_path / "bet_history.json").read_text())
    assert data == []


def test_healthy_files_save_normally(tmp_path):
    (tmp_path / "bet_history.json").write_text("[]")
    (tmp_path / "bankroll_state.json").write_text(
        json.dumps({"current_bankroll": 1500.0, "peak_bankroll": 1500.0,
                    "total_profit_loss": 500.0, "paper_balance": 1000.0}))
    g = _gov(tmp_path)
    assert g._state_corrupt is False
    assert g.current_bankroll == 1500.0
    g._save_state()
    assert json.loads((tmp_path / "bet_history.json").read_text()) == []
