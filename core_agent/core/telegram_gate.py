"""Telegram access-gate helpers (Oct-2026 passcode-first fix).

The passcode redeem MUST live inside the auth gate: strangers are
unauthorized by definition, so a `/start ST-XXXXX` handler placed after the
gate is unreachable (the original bug — passcode only worked post-PIN).
Pure logic here; the webhook wires it to sending.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

logger = logging.getLogger("telegram-gate")

START_CODE_RE = re.compile(r"^/start\s+(ST-\d{5})\s*$", re.IGNORECASE)


def parse_start_code(text: str) -> Optional[str]:
    """Extract the passcode from '/start ST-XXXXX'. None if not a code turn."""
    m = START_CODE_RE.match((text or "").strip())
    return m.group(1).upper() if m else None


def redeem_and_authorize(code: str, chat_id: int, username: Optional[str]) -> bool:
    """Redeem a passcode, authorize + de-quarantine the chat. True on link."""
    try:
        from core_agent.db.repository import LedgerRepository
        from core_agent.db.client import get_service_client
        from core_agent.core import access_control as _ac
        from core_agent.skills.notifications.telegram_bot import (
            clear_quarantine as _cq,
        )
    except Exception as e:
        logger.debug("gate imports unavailable: %r", e)
        return False
    try:
        linked = LedgerRepository(get_service_client()).redeem_link_code(
            code, int(chat_id), username)
    except Exception as e:
        logger.warning("gate redeem failed: %r", e)
        return False
    if not linked:
        return False
    try:
        _ac.authorize(int(chat_id))
    except Exception:
        pass
    try:
        _cq(chat_id)
    except Exception:
        pass
    return True
