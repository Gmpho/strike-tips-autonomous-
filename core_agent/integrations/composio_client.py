"""Thin, audited bridge to the Composio CLI.

- Fixed slug allowlist: only pinned, verified slugs may execute. Anything
  else raises before a subprocess ever spawns (a model can never reach the
  1,500-tool catalog through here).
- JSON in/out, per-call timeout, non-interactive flags only.
- No credentials handled: the CLI session (operator `composio login` /
  linked accounts) carries auth. Never pass keys in commands.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any, Dict, Optional

logger = logging.getLogger("composio-client")

# Pinned slugs — verified live via --get-schema / dry-run + one real call
# each. Additions require the same ritual; see openspec change
# composio-creation-tools.
PINNED_SLUGS = frozenset({
    # Google Sheets (read + write shapes proven Sep-2026)
    "GOOGLESHEETS_GET_SHEET_NAMES",
    "GOOGLESHEETS_VALUES_GET",
    "GOOGLESHEETS_LOOKUP_SPREADSHEET_ROW",
    "GOOGLESHEETS_BATCH_GET",
    "GOOGLESHEETS_ADD_SHEET",
    "GOOGLESHEETS_VALUES_UPDATE",
    # X posting family — pinned after discovery + dry-run (see tasks 2.x).
})

CALL_TIMEOUT_SECS = 90


class ComposioError(Exception):
    """A Composio/CLI/vendor failure, already plain-worded for the agent."""


def _cli() -> str:
    path = shutil.which("composio")
    if not path:
        raise ComposioError(
            "Composio CLI not installed. Install it, then run "
            "`composio login` (see docs/RESEND_EMAIL_PLAN.md pattern)."
        )
    return path


def execute(
    slug: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = CALL_TIMEOUT_SECS,
) -> Dict[str, Any]:
    """Run one pinned tool. Returns the parsed JSON result.

    Raises ComposioError on: unknown slug, CLI missing/failing, timeout,
    or unsuccessful vendor result. Never raises raw subprocess errors.
    """
    if slug not in PINNED_SLUGS:
        raise ComposioError(
            f"Slug '{slug}' is not in the pinned allowlist — refusing to execute."
        )
    cmd = [_cli(), "execute", slug, "-d", json.dumps(payload or {})]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as e:
        raise ComposioError(f"Composio call timed out after {timeout}s: {slug}") from e
    except OSError as e:
        raise ComposioError(f"Composio CLI failed to launch: {e}") from e
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        raise ComposioError(
            f"Composio returned non-JSON for {slug}: {(proc.stderr or '')[:200]}"
        ) from e
    if proc.returncode != 0 or data.get("successful") is False:
        err = data.get("error", proc.stderr or "unknown error")
        raise ComposioError(f"{slug} failed: {str(err)[:300]}")
    return data
