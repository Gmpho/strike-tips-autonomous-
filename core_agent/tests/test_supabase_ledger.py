"""Supabase ledger layer: mapping, passcodes, import reconciliation.

All PostgREST I/O runs against an in-memory fake — no live DB, no creds.
"""
import json

import pytest

from core_agent.db.repository import (
    LedgerRepository,
    bet_to_row,
    hash_code,
    map_status,
    new_passcode,
)
from core_agent.db import import_ledger


class FakeResult:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, store, name):
        self._store = store
        self._name = name
        self._filters = []
        self._op = None
        self._payload = None

    # chainable query builders
    def select(self, *a, **k):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self._op = "upsert"
        self._payload = payload
        self._conflict = on_conflict
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def gt(self, col, val):
        self._filters.append(("gt", col, val))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def _match(self, row):
        for kind, col, val in self._filters:
            if kind == "eq" and row.get(col) != val:
                return False
            if kind == "gt" and not (row.get(col) and row[col] > val):
                return False
        return True

    def execute(self):
        rows = self._store.setdefault(self._name, [])
        if self._op == "select":
            return FakeResult([r for r in rows if self._match(r)])
        if self._op == "insert":
            row = dict(self._payload)
            row.setdefault("id", len(rows) + 1)
            rows.append(row)
            return FakeResult([row])
        if self._op == "upsert":
            row = dict(self._payload)
            for i, r in enumerate(rows):
                if r.get("user_id") == row.get("user_id") and r.get("ref") == row.get("ref"):
                    rows[i] = {**r, **row}
                    if "id" not in rows[i]:
                        rows[i]["id"] = i + 1
                    return FakeResult([rows[i]])
            row.setdefault("id", len(rows) + 1)
            rows.append(row)
            return FakeResult([row])
        if self._op == "update":
            out = []
            for r in rows:
                if self._match(r):
                    r.update(self._payload)
                    out.append(r)
            return FakeResult(out)
        raise AssertionError(f"unknown op {self._op}")


class FakeClient:
    def __init__(self):
        self.store = {}

    def table(self, name):
        return FakeTable(self.store, name)


# ── mapping ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("gov,pg", [
    ("PENDING", "OPEN"), ("WON", "WON"), ("LOST", "LOST"),
    ("VOID", "VOID"), ("EXPIRED", "VOID"), ("weird", "OPEN"), ("", "OPEN"),
])
def test_status_map(gov, pg):
    assert map_status(gov) == pg


def test_bet_to_row_skips_paper():
    assert bet_to_row({"is_paper": True, "bet_id": "x"}, "u") is None


def test_bet_to_row_settled_gets_settled_at():
    row = bet_to_row({
        "bet_id": "BET-1", "track": "vaal", "race_number": 4, "horse": "Fly",
        "odds": 4.5, "stake": 100.0, "edge_percent": 12.4, "confidence": "VALUE",
        "status": "WON", "timestamp": "2026-10-01T10:00:00",
        "actual_return": 450.0, "profit_loss": 350.0,
    }, "u-1")
    assert row["ref"] == "BET-1"
    assert row["status"] == "WON"
    assert row["settled_at"] == "2026-10-01T10:00:00"
    assert row["returned"] == 450.0


def test_bet_to_row_open_has_no_settled_at():
    row = bet_to_row({
        "bet_id": "BET-2", "track": "vaal", "race_number": 5, "horse": "Run",
        "odds": 3.0, "stake": 50.0, "status": "PENDING",
        "timestamp": "2026-10-01T10:00:00",
    }, "u-1")
    assert row["status"] == "OPEN"
    assert row["settled_at"] is None


# ── passcodes ───────────────────────────────────────────────────────────

def test_passcode_format_and_hash():
    code = new_passcode()
    assert code.startswith("ST-") and len(code) == 8
    assert hash_code(code) == hash_code(code.lower())  # case-insensitive
    assert len(hash_code(code)) == 64


def test_redeem_and_status_roundtrip():
    repo = LedgerRepository(FakeClient())
    code = repo.create_link_code("u-1")
    assert repo.link_status("u-1") is None  # still PENDING
    linked = repo.redeem_link_code(code, 12345, "@punter")
    assert linked and linked["status"] == "LINKED"
    assert linked["telegram_chat_id"] == 12345
    # single-use: second redeem fails
    assert repo.redeem_link_code(code, 999, "@other") is None
    st = repo.link_status("u-1")
    assert st["telegram_username"] == "@punter"
    assert repo.revoke_link("u-1") == 1
    assert repo.link_status("u-1") is None


# ── import reconciliation ───────────────────────────────────────────────

def _write_source(tmp_path):
    state = {"current_bankroll": 3799.56, "peak_bankroll": 3799.56,
             "total_profit_loss": 2799.56, "paper_balance": 1000.0}
    bets = [
        {"bet_id": "A1", "track": "vaal", "race_number": 1, "horse": "H1",
         "odds": 4.5, "stake": 100.0, "status": "WON",
         "timestamp": "2026-10-01T09:00:00", "actual_return": 450.0,
         "profit_loss": 350.0},
        {"bet_id": "A2", "track": "vaal", "race_number": 2, "horse": "H2",
         "odds": 2.0, "stake": 50.0, "status": "LOST",
         "timestamp": "2026-10-01T09:30:00", "actual_return": 0.0,
         "profit_loss": -50.0},
        {"bet_id": "P1", "track": "vaal", "race_number": 3, "horse": "HP",
         "odds": 5.0, "stake": 10.0, "status": "WON", "is_paper": True,
         "timestamp": "2026-10-01T10:00:00", "actual_return": 50.0,
         "profit_loss": 40.0},
    ]
    (tmp_path / "bankroll_state.json").write_text(json.dumps(state))
    (tmp_path / "bet_history.json").write_text(json.dumps(bets))
    return str(tmp_path)


def test_expected_totals_exclude_paper(tmp_path):
    d = _write_source(tmp_path)
    state, bets = import_ledger.load_jsons(d)
    exp = import_ledger.expected_totals(state, bets)
    assert exp["bet_rows"] == 2          # paper excluded
    assert exp["settled_rows"] == 2
    assert exp["settled_pnl"] == 300.00  # 350 - 50 (paper 40 excluded)
    assert exp["balance"] == 3799.56


def test_dry_run_writes_nothing(tmp_path):
    d = _write_source(tmp_path)
    assert import_ledger.run("u-1", d, live=False) == 0
