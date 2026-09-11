"""
Volume sync guard for long-lived Modal containers.

Root cause (Sep 2026): serve_api never idles (5s HUD polling vs 60s
scaledown), so its container — and its volume mount view — lives for days.
Files written by short-lived sibling containers (scans, repairs, monitor)
were invisible to it: endpoints served hours-old bet_history, exotics, and
ATR snapshots while fresh volume-direct reads proved the data was current.

Fix: throttled `Volume.reload()` (a.k.a. blocking_reload — "make latest
committed state available in the running container") ahead of hot reads.
No-op everywhere except inside a running Modal container with the data
volume attached.
"""

import logging
import os
import time

logger = logging.getLogger("volume-sync")

_VOLUME_NAME = "strike-tips-data"
_last_reload = 0.0
_volume = None


def _in_modal_container() -> bool:
    return bool(os.getenv("MODAL_TASK_ID"))


def sync_volume(max_age_secs: int = 30) -> bool:
    """Pull latest committed volume state if older than max_age_secs.

    Returns True when a reload was attempted (even if the backend call
    failed — failures are debug-logged, never raised). Safe to call on
    every request; the timestamp guard makes it ~free.
    """
    global _last_reload, _volume
    now = time.time()
    if now - _last_reload < max_age_secs:
        return False
    _last_reload = now
    if not _in_modal_container():
        return False
    try:
        import modal

        if _volume is None:
            _volume = modal.Volume.from_name(_VOLUME_NAME)
        _volume.reload()
        return True
    except Exception as e:
        # Reload fails with open files on the volume — transient, retry next window.
        logger.debug(f"Volume reload skipped: {e}")
        return True
