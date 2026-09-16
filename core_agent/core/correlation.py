"""Correlation IDs: one id per scan/settle/chat flow, threaded through logs
and Telegram messages so any incident is solvable with a single grep.

Usage:
    from core_agent.core.correlation import bind, get, new_id

    cid = bind(new_id("settle"))   # at flow entry
    logger.info("[%s] starting settle", get())
    await telegram.send_bet_result(..., ref=get())  # trailing token

Zero dependencies. Never raises. Empty string when unbound (e.g. tests,
REPL) so all call sites stay unconditional.
"""

import uuid
from contextvars import ContextVar

_cid: ContextVar[str] = ContextVar("strike_cid", default="")


def new_id(prefix: str) -> str:
    """Short unique id like 'settle-a1b2c3d4'."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def bind(cid: str) -> str:
    """Bind an id to the current async context. Returns it for inline use."""
    _cid.set(cid or "")
    return cid or ""


def get() -> str:
    """Current correlation id, or '' when unbound."""
    try:
        return _cid.get()
    except Exception:
        return ""


def tag() -> str:
    """Bracketed suffix for log lines, '' when unbound: '[settle-a1b2c3d4]'."""
    cid = get()
    return f"[{cid}]" if cid else ""
