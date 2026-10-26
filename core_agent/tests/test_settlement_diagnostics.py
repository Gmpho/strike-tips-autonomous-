"""Pending-reason diagnostics: recorded, rotated, never breaks settlement."""

import json

import pytest

from core_agent.skills import settlement_diagnostics as diag


@pytest.fixture
def diag_file(tmp_path, monkeypatch):
    path = tmp_path / diag.FILENAME
    monkeypatch.setattr(diag, "_path", lambda: path)
    return path


def test_record_pending_writes_one_jsonl_row(diag_file):
    diag.record_pending("BET_1", "no_dividend", "Quadrella not published", "Greyville", "QUARTELLA")
    rows = [json.loads(line) for line in diag_file.read_text().splitlines()]
    assert len(rows) == 1
    assert rows[0]["bet_id"] == "BET_1"
    assert rows[0]["reason"] == "no_dividend"
    assert rows[0]["track"] == "Greyville"
    assert rows[0]["ts"].endswith("Z")


def test_unknown_reason_is_coerced(diag_file):
    diag.record_pending("BET_2", "made_up_reason")
    assert json.loads(diag_file.read_text().splitlines()[0])["reason"] == "unknown_legs"


def test_recent_is_newest_first(diag_file):
    diag.record_pending("A", "no_results")
    diag.record_pending("B", "no_dividend")
    assert [r["bet_id"] for r in diag.recent()] == ["B", "A"]


def test_latest_by_bet_keeps_last_reason(diag_file):
    diag.record_pending("A", "no_results")
    diag.record_pending("A", "no_dividend")
    latest = diag.latest_by_bet()
    assert latest["A"]["reason"] == "no_dividend"


def test_rotation_keeps_one_backup(diag_file, monkeypatch):
    monkeypatch.setattr(diag, "MAX_BYTES", 10)
    diag_file.write_text("x" * 20)
    diag.record_pending("A", "no_dividend")
    backup = diag_file.with_suffix(diag_file.suffix + ".1")
    assert backup.exists()
    assert diag_file.exists()


def test_write_failure_is_swallowed(monkeypatch):
    def boom():
        raise OSError("read-only volume")

    monkeypatch.setattr(diag, "_path", boom)
    diag.record_pending("A", "no_dividend")  # must not raise
    assert diag.recent() == []


def test_all_settlement_reasons_are_declared():
    assert {
        "age_expired",
        "unparseable",
        "no_results",
        "before_off_time",
        "unknown_legs",
        "no_dividend",
        "settle_failed",
    } == set(diag.REASONS)
