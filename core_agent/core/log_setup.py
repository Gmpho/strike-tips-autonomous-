"""Configure file-based logging so the /api/logs endpoint has data to serve."""

import logging
import os
import tempfile
from logging.handlers import RotatingFileHandler

_LOG_PATH: str | None = None


def ensure_log_file() -> str:
    global _LOG_PATH
    if _LOG_PATH:
        return _LOG_PATH

    # Container-local, NOT the Modal volume: the handler holds the file open
    # for the process lifetime, and an open volume file blocks
    # ``volume.reload()`` ("there are open files preventing the operation:
    # path strike.log is open") — which froze snapshot/news refresh in the
    # web keeper (Sep-2026: monitor writes never reached the HUD).
    # /api/logs reads via this same path, so it stays self-consistent.
    path = os.path.join(tempfile.gettempdir(), "strike.log")
    _LOG_PATH = path
    return path


def configure_file_logging():
    """Add a rotating file handler to the root logger.

    Call once during application startup (lifespan).  The file is written
    to the container's temp dir so the ``/api/logs`` endpoint can read it
    without holding an open handle on the shared Modal volume.
    """
    path = ensure_log_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=2)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(handler)
