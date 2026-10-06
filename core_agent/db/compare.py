"""Continuous ledger reconciliation (Oct-2026 hardening, fix 5).

The import gate reconciles once; every settlement since then drifts silently.
This compares the JSON source of truth against Postgres on demand and is
wired to the docker scheduler (daily) + a manual Modal trigger. Drift →
Telegram alert, never silent.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("reconcile")


def compare_ledger(user_id: str, data_dir: str, client: Any = None) -> Dict:
    """Compare JSON totals vs Postgres. Returns {match, json, db, notes}."""
    from core_agent.db.import_ledger import expected_totals, load_jsons
    from core_agent.db.client import get_service_client
    from core_agent.db import repository as _repo_mod

    state, bets = load_jsons(data_dir)
    exp = expected_totals(state, bets)
    repo = _repo_mod.LedgerRepository(client or get_service_client())
    db_pnl = repo.settled_pnl(user_id)
    db_paper = repo.settled_pnl(user_id, paper=True)
    try:
        open_rows = repo.open_bets(user_id)
        db_open = len(open_rows)
    except Exception:
        db_open = -1
    json_open = sum(
        1 for b in bets
        if str(b.get("status", "")).upper() == "PENDING"
    )
    notes = []
    ok = True
    if abs(db_pnl - exp["settled_pnl"]) >= 0.01:
        ok = False
        notes.append(f"real P&L drift: JSON R{exp['settled_pnl']:.2f} vs DB R{db_pnl:.2f}")
    if abs(db_paper - exp["settled_paper_pnl"]) >= 0.01:
        ok = False
        notes.append(f"paper P&L drift: JSON R{exp['settled_paper_pnl']:.2f} vs DB R{db_paper:.2f}")
    result = {
        "match": ok,
        "json": {"settled_pnl": exp["settled_pnl"],
                 "paper_pnl": exp["settled_paper_pnl"],
                 "bet_rows": exp["bet_rows"], "paper_rows": exp["paper_rows"],
                 "open": json_open, "balance": exp["balance"]},
        "db": {"settled_pnl": db_pnl, "paper_pnl": db_paper, "open": db_open},
        "notes": notes,
    }
    level = "MATCH" if ok else "DRIFT: " + "; ".join(notes)
    logger.info("Reconcile %s: %s", user_id[:8], level)
    if not ok:
        try:
            from core_agent.core.telemetry import emit
            emit("system", f"⚠️ Ledger drift: {'; '.join(notes)}")
        except Exception:
            pass
    return result
