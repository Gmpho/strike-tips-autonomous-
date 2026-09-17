import json
import logging
import os
from pathlib import Path
from core_agent.config.paths import DATA_DIR

logger = logging.getLogger("access-control")


def _whitelist_path() -> Path:
    return DATA_DIR / "whitelist.json"


def _load_whitelist() -> set:
    path = _whitelist_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            return set(data.get("authorized_ids", []))
        except Exception as e:
            logger.warning("Failed to load whitelist: %s", e)
    return set()


def _save_whitelist(ids: set):
    path = _whitelist_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"authorized_ids": list(ids)}, indent=2))


def is_authorized(chat_id: int, owner_chat_id: str = "") -> bool:
    whitelist = _load_whitelist()
    if owner_chat_id and str(chat_id) == str(owner_chat_id):
        return True
    return chat_id in whitelist


def authorize(chat_id: int):
    whitelist = _load_whitelist()
    whitelist.add(chat_id)
    _save_whitelist(whitelist)
    logger.info("Authorized chat_id: %s", chat_id)


# PIN brute-force guard (Sep-2026 audit VULN-04). Counts failures per chat
# in a volume JSON so separate containers share state. 5 fails -> 30 min
# lockout. Best-effort file ops; fail-open on I/O errors (availability
# beats a lockout that can never clear).
PIN_MAX_FAILS = 5
PIN_LOCKOUT_SECS = 30 * 60


def _pin_attempts_path() -> Path:
    return DATA_DIR / "pin_attempts.json"


def _load_pin_attempts() -> dict:
    try:
        path = _pin_attempts_path()
        if path.exists():
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                return data
    except Exception as e:
        logger.debug("PIN attempts load skipped: %s", e)
    return {}


def _save_pin_attempts(state: dict) -> None:
    try:
        _pin_attempts_path().parent.mkdir(parents=True, exist_ok=True)
        _pin_attempts_path().write_text(json.dumps(state))
    except Exception as e:
        logger.debug("PIN attempts save skipped: %s", e)


def pin_locked(chat_id: int) -> bool:
    """True while a chat is inside a brute-force lockout window."""
    import time

    try:
        rec = _load_pin_attempts().get(str(chat_id), {})
        return float(rec.get("locked_until", 0)) > time.time()
    except Exception:
        return False


def record_pin_attempt(chat_id: int, success: bool) -> bool:
    """Record a PIN attempt. Returns True if the chat is now locked out."""
    import time

    try:
        state = _load_pin_attempts()
        key = str(chat_id)
        rec = state.get(key, {"fails": 0, "locked_until": 0})
        if success:
            state.pop(key, None)
            _save_pin_attempts(state)
            return False
        rec["fails"] = int(rec.get("fails", 0)) + 1
        locked = rec["fails"] >= PIN_MAX_FAILS
        if locked:
            rec["locked_until"] = time.time() + PIN_LOCKOUT_SECS
            logger.warning("PIN lockout engaged for chat_id %s (%d fails)", chat_id, rec["fails"])
        state[key] = rec
        _save_pin_attempts(state)
        return locked
    except Exception:
        return False
