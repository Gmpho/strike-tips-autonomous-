"""Configure file-based logging so the /api/logs endpoint has data to serve."""

import logging
import os
from logging.handlers import RotatingFileHandler
from core_agent.config.paths import DATA_DIR


_LOG_PATH: str | None = None


def ensure_log_file() -> str:
    global _LOG_PATH
    if _LOG_PATH:
        return _LOG_PATH

    os.makedirs(DATA_DIR, exist_ok=True)
    path = str(DATA_DIR / "strike.log")
    _LOG_PATH = path
    return path


def configure_file_logging():
    """Add a rotating file handler to the root logger.

    Call once during application startup (lifespan).  The file is written
    to *DATA_DIR / strike.log* so the ``/api/logs`` endpoint can read it.
    Idempotent: repeat calls attach nothing when a handler for the same
    path already exists (lets volume-reload close + reopen cleanly).
    """
    path = ensure_log_file()
    root = logging.getLogger()
    for h in root.handlers:
        if getattr(h, "baseFilename", "") == path:
            return
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=2)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(handler)


def close_file_handlers() -> None:
    """Close + detach strike.log handlers.

    Modal Volumes refuse ``reload()`` while any file is open — our own log
    handler is the usual holder, freezing the web container's volume view
    (Sep-2026: 8h-stale telemetry/news). Close across the reload, then call
    ``configure_file_logging()`` again to reopen (idempotent, no dupes).
    """
    root = logging.getLogger()
    for h in list(root.handlers):
        try:
            if getattr(h, "baseFilename", ""):
                root.removeHandler(h)
                h.close()
        except Exception:
            pass
