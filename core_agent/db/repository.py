"""Ledger + link repository over PostgREST.

Status mapping (governor JSON -> Postgres):
  PENDING -> OPEN, WON -> WON, LOST -> LOST, VOID/EXPIRED -> VOID.
Paper bets import WITH is_paper=True: the paper bank is a parallel ledger
and migrates alongside real funds, never mixed in queries.

Passcodes: only sha256(code) is persisted. Generation returns the clear
code once; verification hashes the presented code and compares.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

logger = logging.getLogger("db-repository")

STATUS_MAP = {
    "PENDING": "OPEN",
    "WON": "WON",
    "LOST": "LOST",
    "VOID": "VOID",
    "EXPIRED": "VOID",
}

PASSCODE_PREFIX = "ST-"
PASSCODE_DIGITS = 5
PASSCODE_TTL_MINUTES = 15


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode()).hexdigest()


def new_passcode() -> str:
    return f"{PASSCODE_PREFIX}{secrets.randbelow(10 ** PASSCODE_DIGITS):05d}"


def map_status(governor_status: str) -> str:
    return STATUS_MAP.get((governor_status or "").upper(), "OPEN")


def bet_to_row(bet: dict, user_id: str) -> Optional[dict]:
    """Map a governor BetRecord dict to a bets-table row.

    Paper bets are imported WITH is_paper=True (never skipped): the paper
    bank is a parallel ledger, not second-class data.
    """
    settled = map_status(bet.get("status", "")) in ("WON", "LOST")
    return {
        "user_id": user_id,
        "ref": str(bet.get("bet_id", "")),
        "track": str(bet.get("track", "")),
        "race_number": int(bet.get("race_number") or 0),
        "horse": str(bet.get("horse", "")),
        "odds": float(bet.get("odds") or 0),
        "stake": float(bet.get("stake") or 0),
        "edge": float(bet.get("edge_percent") or 0) if bet.get("edge_percent") is not None else None,
        "confidence": bet.get("confidence"),
        "status": map_status(bet.get("status", "")),
        "placed_at": bet.get("timestamp"),
        "settled_at": bet.get("timestamp") if settled else None,
        "returned": float(bet["actual_return"]) if bet.get("actual_return") is not None else None,
        "is_paper": bool(bet.get("is_paper", False)),
    }


class LedgerRepository:
    """Thin PostgREST wrapper. Constructed with an authenticated client
    (service client for backend jobs, user client for HUD requests)."""

    def __init__(self, client: Any) -> None:
        self._c = client

    # ── bets ──────────────────────────────────────────────────────────
    # Egress diet: list reads project only the columns settlement/display
    # need. Full rows are fetched per-bet when required, never in bulk.
    OPEN_BET_COLS = ("id,ref,track,race_number,horse,odds,stake,edge,"
                     "confidence,status,placed_at,is_paper")

    def upsert_bet(self, row: dict) -> dict:
        res = self._c.table("bets").upsert(row, on_conflict="user_id,ref,is_paper").execute()
        return (res.data or [{}])[0]

    def open_bets(self, user_id: str) -> list[dict]:
        res = (
            self._c.table("bets")
            .select(self.OPEN_BET_COLS)
            .eq("user_id", user_id)
            .eq("status", "OPEN")
            .order("placed_at")
            .execute()
        )
        return res.data or []

    def record_settlement(self, bet_id: int, result: str, profit: float, source: str = "auto") -> dict:
        res = self._c.table("settlements").insert({
            "bet_id": bet_id, "result": result, "profit": profit, "source": source,
        }).execute()
        return (res.data or [{}])[0]

    def settled_pnl(self, user_id: str, paper: bool = False) -> float:
        """SUM(profit) over the user's settlements — reconciliation anchor.
        Real and paper ledgers reconciled separately (paper=True)."""
        res = (
            self._c.table("settlements")
            .select("profit, bets!inner(user_id,is_paper)")
            .eq("bets.user_id", user_id)
            .eq("bets.is_paper", paper)
            .execute()
        )
        return round(sum(float(r.get("profit") or 0) for r in (res.data or [])), 2)

    # ── snapshots / epochs ────────────────────────────────────────────
    def record_snapshot(self, user_id: str, balance: float, peak: float,
                        total_pnl: float, drawdown_pct: float,
                        paper_balance: float | None = None) -> dict:
        row: dict = {
            "user_id": user_id, "balance": balance, "peak": peak,
            "total_pnl": total_pnl, "drawdown_pct": drawdown_pct,
        }
        if paper_balance is not None:
            row["paper_balance"] = paper_balance
        res = self._c.table("bankroll_snapshots").insert(row).execute()
        return (res.data or [{}])[0]

    def start_epoch(self, user_id: str, opening_balance: float, note: str = "") -> dict:
        """'Start fresh' — new epoch row. Nothing is deleted, ever."""
        res = self._c.table("ledger_epochs").insert({
            "user_id": user_id, "opening_balance": opening_balance, "note": note,
        }).execute()
        return (res.data or [{}])[0]

    # ── profiles ────────────────────────────────────────────────────
    def ensure_profile(self, user_id: str, display_name: str | None = None) -> dict:
        """Auto-provision the profiles row on first authenticated use.

        Without this, every user-owned insert dies on the FK constraint
        (Oct-2026: link-code mint 500'd for a valid login with no profile).
        Idempotent upsert — safe to call on every authenticated request.
        """
        row: dict = {"id": user_id}
        if display_name:
            row["display_name"] = display_name
        res = self._c.table("profiles").upsert(row, on_conflict="id").execute()
        return (res.data or [{}])[0]

    # ── telegram passcode links ───────────────────────────────────────
    def create_link_code(self, user_id: str) -> str:
        """Generate a single-use code. Returns the CLEAR code once."""
        code = new_passcode()
        expires = datetime.now(timezone.utc) + timedelta(minutes=PASSCODE_TTL_MINUTES)
        self._c.table("telegram_links").insert({
            "code_hash": hash_code(code), "user_id": user_id,
            "status": "PENDING", "expires_at": expires.isoformat(),
        }).execute()
        return code

    def redeem_link_code(self, code: str, chat_id: int, username: Optional[str]) -> Optional[dict]:
        """Bind a Telegram chat to the code's owner. Single-use + expiry enforced."""
        now = datetime.now(timezone.utc).isoformat()
        found = (
            self._c.table("telegram_links")
            .select("*")
            .eq("code_hash", hash_code(code))
            .eq("status", "PENDING")
            .gt("expires_at", now)
            .execute()
        )
        rows = found.data or []
        if not rows:
            return None
        row = rows[0]
        updated = (
            self._c.table("telegram_links")
            .update({
                "status": "LINKED", "telegram_chat_id": chat_id,
                "telegram_username": username, "linked_at": now,
            })
            .eq("code_hash", row["code_hash"])
            .eq("status", "PENDING")
            .execute()
        )
        data = updated.data or []
        return data[0] if data else None

    def link_status(self, user_id: str) -> Optional[dict]:
        res = (
            self._c.table("telegram_links")
            .select("telegram_username, status, linked_at")
            .eq("user_id", user_id)
            .eq("status", "LINKED")
            .order("linked_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return rows[0] if rows else None

    def revoke_link(self, user_id: str) -> int:
        res = (
            self._c.table("telegram_links")
            .update({"status": "REVOKED"})
            .eq("user_id", user_id)
            .eq("status", "LINKED")
            .execute()
        )
        return len(res.data or [])
