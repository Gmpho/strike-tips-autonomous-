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
    """
    path = ensure_log_file()
    handler = RotatingFileHandler(path, maxBytes=5 * 1024 * 1024, backupCount=2)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logging.getLogger().addHandler(handler)
