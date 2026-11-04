"""Internal agent tools backed by Composio (creation flows only).

Fixed schemas, gambling-free names, deterministic where money or numbers
are involved. Vendor slugs never appear here — only the pinned adapter.
Alerts stay on Resend (out of scope).
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from core_agent.integrations.composio_client import ComposioError, execute

logger = logging.getLogger("composio-tools")

# Per-user daily caps (X pay-per-use: $0.015 link-free post).
MAX_POSTS_PER_USER_PER_DAY = 5

_post_counts: Dict[str, List[float]] = {}


def _post_cap_ok(user_id: str) -> bool:
    now = time.time()
    stamps = [t for t in _post_counts.get(user_id, []) if now - t < 86400]
    _post_counts[user_id] = stamps
    return len(stamps) < MAX_POSTS_PER_USER_PER_DAY


def _post_cap_hit(user_id: str) -> None:
    _post_counts.setdefault(user_id, []).append(time.time())


def _next_empty_row(spreadsheet_id: str, tab: str) -> int:
    """First empty row in column A (1-indexed). Headers live in row 1 —
    writers must append below them, never overwrite (Sep-2026: a proof
    write landed on A1 and ate the headers)."""
    from core_agent.integrations.composio_client import execute as _exec

    try:
        res = _exec(
            "GOOGLESHEETS_VALUES_GET",
            {"spreadsheet_id": spreadsheet_id, "range": f"{tab}!A:A"},
        )
        vals = res.get("data", {}).get("values", []) or []
        return len(vals) + 1
    except ComposioError:
        return 2  # conservative: skip the header row


def create_analysis_sheet(
    spreadsheet_id: str,
    title: str,
    rows: List[List[str]],
    account: Optional[str] = None,  # noqa: F841 — account routing lands with subscriber mapping (task 3.x)
) -> Dict[str, Any]:
    """Append form-analysis/tips rows to a tab in a spreadsheet.

    Returns plain confirmation (sheet title, updated range) or an error
    string — never raw vendor JSON.
    """
    _ = account
    try:
        row = _next_empty_row(spreadsheet_id, title)
        res = execute(
            "GOOGLESHEETS_VALUES_UPDATE",
            {
                "spreadsheet_id": spreadsheet_id,
                "range": f"{title}!A{row}",
                "values": rows,
                "value_input_option": "RAW",
            },
        )
        data = res.get("data", {})
        return {
            "ok": True,
            "sheet": title,
            "updated": data.get("updatedRange", data.get("updated_range", "?")),
        }
    except ComposioError as e:
        logger.warning("create_analysis_sheet failed: %s", e)
        return {"ok": False, "error": str(e)}


def export_pnl_report(
    spreadsheet_id: str,
    rows: List[List[str]],
    tab: str = "PnL",
    account: Optional[str] = None,  # noqa: F841 — see above
) -> Dict[str, Any]:
    """Write precomputed PnL rows (computed by the caller from the ledger —
    never by a model) to a tab. Figures pass through untouched.
    """
    _ = account
    try:
        row = _next_empty_row(spreadsheet_id, tab)
        res = execute(
            "GOOGLESHEETS_VALUES_UPDATE",
            {
                "spreadsheet_id": spreadsheet_id,
                "range": f"{tab}!A{row}",
                "values": rows,
                "value_input_option": "RAW",
            },
        )
        data = res.get("data", {})
        return {
            "ok": True,
            "sheet": tab,
            "updated": data.get("updatedRange", data.get("updated_range", "?")),
        }
    except ComposioError as e:
        logger.warning("export_pnl_report failed: %s", e)
        return {"ok": False, "error": str(e)}


def publish_tip_post(
    text: str,
    user_id: str,
    dry_run: bool = True,
) -> Dict[str, Any]:
    """Post a tipped slip to the subscriber's X account.

    Link-free only ($0.015, never $0.20 URLs) — URLs are stripped, not
    sent. Defaults to dry_run; per-user daily cap enforced. X post slug
    is pinned after discovery + first live test (tasks 2.x).
    """
    if not _post_cap_ok(user_id):
        return {
            "ok": False,
            "error": "Daily post cap reached (5/day) — resets in 24h.",
        }
    clean = " ".join(str(text or "").split())
    if not clean:
        return {"ok": False, "error": "Empty post text — nothing to publish."}
    if dry_run:
        return {"ok": True, "dry_run": True, "chars": len(clean)}
    # Live path resolves the pinned X post slug at build time (task 2.x);
    # wired then, never before a verified slug exists.
    return {"ok": False, "error": "Live posting not yet wired (pending slug pin)."}
