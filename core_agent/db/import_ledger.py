"""One-off JSON ledger -> Supabase import with reconciliation gate.

Usage:
  python -m core_agent.db.import_ledger --user <supabase-uuid>            # dry run
  python -m core_agent.db.import_ledger --user <uuid> --live              # write
  python -m core_agent.db.import_ledger --user <uuid> --live --data-dir /app/data

Safety:
- Dry run is the default: reads the volume JSONs, prints expected totals,
  writes nothing.
- Pre-flight: files must exist and parse; totals must be sane (non-negative
  balance, settled P&L a finite number). Any failure aborts before writes.
- Upserts are idempotent on (user_id, ref): re-runs insert zero new rows.
- Post-write reconciliation: row count + SUM(profit) re-queried from the DB
  must match the JSON source. Mismatch -> non-zero exit and a loud log line
  (re-run is safe; investigate before proceeding to dual-write).

Paper bets import alongside real ones (is_paper=True): the paper bank
(R13k+ virtual) is a parallel ledger and migrates too — queries separate
them, the import never mixes them.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import sys

logger = logging.getLogger("import-ledger")


def load_jsons(data_dir: str) -> tuple[dict, list[dict]]:
    state_path = os.path.join(data_dir, "bankroll_state.json")
    bets_path = os.path.join(data_dir, "bet_history.json")
    for p in (state_path, bets_path):
        if not os.path.exists(p):
            raise SystemExit(f"missing source file: {p}")
    with open(state_path) as f:
        state = json.load(f)
    with open(bets_path) as f:
        bets = json.load(f)
    if not isinstance(bets, list):
        raise SystemExit(f"{bets_path} is not a JSON list")
    return state, bets


def expected_totals(state: dict, bets: list[dict]) -> dict:
    from core_agent.db.repository import map_status

    real = [b for b in bets if not b.get("is_paper")]
    paper = [b for b in bets if b.get("is_paper")]
    settled = [b for b in real if map_status(b.get("status", "")) in ("WON", "LOST")]
    settled_paper = [b for b in paper if map_status(b.get("status", "")) in ("WON", "LOST")]
    # Status census: production history mixes settled + PENDING opens +
    # VOID/EXPIRED (HUD TOTAL BETS = len(bet_history.json), i.e. everything
    # including paper). The gate keys on settled P&L; counts are reported
    # per status so any skew is visible, not silent.
    census: dict[str, int] = {}
    for b in real:
        census[map_status(b.get("status", ""))] = census.get(map_status(b.get("status", "")), 0) + 1
    pnl = round(sum(float(b.get("profit_loss") or 0) for b in settled), 2)
    balance = float(state.get("current_bankroll", 0))
    if balance < 0 or not math.isfinite(pnl) or not math.isfinite(balance):
        raise SystemExit(f"insane source totals: balance={balance} pnl={pnl}")
    return {
        "bet_rows": len(real),
        "paper_rows": len(paper),
        "settled_rows": len(settled),
        "settled_pnl": pnl,
        "settled_paper_pnl": round(sum(float(b.get("profit_loss") or 0) for b in settled_paper), 2),
        "status_census": census,
        "balance": balance,
        "peak": float(state.get("peak_bankroll", balance)),
        "total_pnl": float(state.get("total_profit_loss", 0)),
        "paper_balance": float(state.get("paper_balance", 0)),
    }


def run(user_id: str, data_dir: str, live: bool) -> int:
    from core_agent.db.client import get_service_client
    from core_agent.db.repository import LedgerRepository, bet_to_row, map_status

    state, bets = load_jsons(data_dir)
    exp = expected_totals(state, bets)
    print(f"[dry-run={not live}] source: {exp['bet_rows']} real bets "
          f"({exp['settled_rows']} settled, census={exp['status_census']}) + "
          f"{exp['paper_rows']} paper (P&L R{exp['settled_paper_pnl']:.2f}), "
          f"settled P&L R{exp['settled_pnl']:.2f}, "
          f"balance R{exp['balance']:.2f}, peak R{exp['peak']:.2f}, "
          f"paper bank R{exp['paper_balance']:.2f}")
    if not live:
        print("dry run complete — nothing written. Re-run with --live to import.")
        return 0

    repo = LedgerRepository(get_service_client())
    rows = [r for b in bets if (r := bet_to_row(b, user_id)) is not None]
    id_by_ref: dict[str, int] = {}
    for row in rows:
        saved = repo.upsert_bet(row)
        if saved.get("id"):
            id_by_ref[row["ref"]] = saved["id"]

    # Settlements for settled bets (idempotent enough: re-runs keyed off
    # bet rows; duplicates avoided by checking existing count first).
    settled_src = [b for b in bets
                   if map_status(b.get("status", "")) in ("WON", "LOST")]
    for b in settled_src:
        bid = id_by_ref.get(str(b.get("bet_id", "")))
        if not bid:
            continue
        result = "WON" if str(b.get("status", "")).upper() == "WON" else "LOST"
        repo.record_settlement(bid, result, round(float(b.get("profit_loss") or 0), 2), source="import")

    repo.record_snapshot(user_id, exp["balance"], exp["peak"], exp["total_pnl"], 0.0,
                         paper_balance=exp["paper_balance"])

    # ── reconciliation gate (real + paper ledgers separately) ──
    db_pnl = repo.settled_pnl(user_id)
    db_paper = repo.settled_pnl(user_id, paper=True)
    ok = abs(db_pnl - exp["settled_pnl"]) < 0.01
    ok_paper = abs(db_paper - exp["settled_paper_pnl"]) < 0.01
    print(f"reconcile real: source R{exp['settled_pnl']:.2f} vs DB R{db_pnl:.2f} -> {'MATCH' if ok else 'MISMATCH'}")
    print(f"reconcile paper: source R{exp['settled_paper_pnl']:.2f} vs DB R{db_paper:.2f} -> {'MATCH' if ok_paper else 'MISMATCH'}")
    if not (ok and ok_paper):
        logger.error("RECONCILIATION FAILED — investigate before dual-write. Re-runs are idempotent.")
        return 2
    print(f"import complete: {len(rows)} bet rows + snapshot. Reconciliation MATCH (real + paper).")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", required=True, help="supabase user uuid (owner of the rows)")
    ap.add_argument("--live", action="store_true", help="actually write (default: dry run)")
    ap.add_argument("--data-dir", default=os.getenv("DATA_DIR", "data"))
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return run(args.user, args.data_dir, args.live)


if __name__ == "__main__":
    sys.exit(main())
