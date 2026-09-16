"""Date-scoped prompt→response cache (volume JSON, midnight TTL).

Identical prompts (morning scan, midday rescan, chat repeats) re-pay Groq
for the same answer. This store answers repeats for free: keyed by
sha256(model + prompt), scoped to the current SAST date, evicted lazily.

Best-effort throughout — a cache failure must never break the caller.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("llm-cache")

_SAST = timezone(timedelta(hours=2))
MAX_ENTRIES = 800


def _today() -> str:
    return datetime.now(_SAST).strftime("%Y-%m-%d")


def _path(data_dir) -> str:
    return os.path.join(str(data_dir), "llm_cache.json")


def _load(data_dir) -> dict:
    try:
        with open(_path(data_dir)) as f:
            store = json.load(f)
        if isinstance(store, dict):
            return store
    except Exception:
        pass
    return {}


def _save(data_dir, store: dict) -> None:
    try:
        while len(store) > MAX_ENTRIES:
            store.pop(next(iter(store)))
        with open(_path(data_dir), "w") as f:
            json.dump(store, f)
    except Exception as e:
        logger.debug(f"llm_cache save skipped: {e}")


def _key(model: str, prompt: str) -> str:
    return hashlib.sha256(f"{model}\n{prompt}".encode()).hexdigest()


def get(data_dir, model: str, prompt: str):
    """Return the cached response for an identical prompt today, else None."""
    try:
        entry = _load(data_dir).get(_key(model, prompt))
        if isinstance(entry, dict) and entry.get("date") == _today():
            return entry.get("response")
    except Exception:
        pass
    return None


def put(data_dir, model: str, prompt: str, response: str) -> None:
    """Store a response under today's date (evicts oldest past cap)."""
    try:
        store = _load(data_dir)
        store[_key(model, prompt)] = {"date": _today(), "response": response}
        _save(data_dir, store)
    except Exception:
        pass


def default_data_dir():
    try:
        from core_agent.config.paths import DATA_DIR
        return str(DATA_DIR)
    except Exception:
        return "./data"
