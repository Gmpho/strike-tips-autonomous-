"""Logging setup: human-readable locally, JSON on Modal.

Modal log tailing is only queryable with structured lines, so any container
running under MODAL_TASK_ID emits one JSON object per record (ts, level,
logger, msg). Everywhere else keeps the classic single-line format.
Idempotent — safe to call from every entry module.
"""

import json
import logging
import os
from datetime import datetime, timezone

_configured = False


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        })


def configure_logging() -> None:
    """Install root handler once. JSON iff LOG_FORMAT=json or on Modal."""
    global _configured
    if _configured:
        return
    _configured = True
    fmt = os.getenv("LOG_FORMAT", "")
    want_json = fmt.lower() == "json" or bool(os.getenv("MODAL_TASK_ID"))
    handler = logging.StreamHandler()
    if want_json:
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S"))
    root = logging.getLogger()
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
