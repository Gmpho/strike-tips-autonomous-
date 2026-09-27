"""Single sanctioned writer for ``data/market_snapshot_latest.json``.

Root cause (Sep-2026): two scan-side writers dumped the RAW Betway bundle
straight over the monitor's pruned snapshot file:

- ``core_agent/core/scheduler.py`` (continuous scan, every 15 min)
- ``core_agent/core/strike_tips.py`` (daily scan)

The raw bundle has no ``timestamp``, keeps ``isFinished`` races and keeps
races whose off-time passed hours ago. The HUD's 15s disk poll therefore
re-served a ~126-race morning card minutes after the monitor had pruned the
card to ~58 live races — the dashboard count oscillated all day and finished
races kept "coming back".

Every writer now funnels through :func:`write_market_snapshot`, which:

1. drops ``isFinished`` races,
2. prunes overdue races (``_close_overdue_races`` — off-time + grace),
3. stamps ``expires_at`` (epoch secs) so *any* reader can drop a race that
   finished after the snapshot was written (worker KV, HUD, Telegram),
4. stamps ``timestamp`` + ``snapshot_source`` and refreshes the in-memory
   snapshot cache so same-container reads agree with the file.

All helpers are defensive — a snapshot write must never break a scan.
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("snapshot-writer")

# Races whose off-time passed by more than this are closed (mirrors the
# monitor's closer default so every writer prunes identically).
CLOSE_GRACE_MINUTES = 2


def _prune_events(events: Dict[str, Any]) -> Dict[str, Any]:
    """Prune finished/overdue races via the monitor's closer.

    Lazy import keeps this module import-light (the monitor pulls in alert
    engines, swarm and parsers). Falls back to a local copy of the same
    predicate if that import is unavailable (partial installs, tests).
    """
    try:
        from core_agent.core.adaptive_odds_monitor import _close_overdue_races

        return _close_overdue_races(events, max_minutes_after_off=CLOSE_GRACE_MINUTES)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Closer import failed, using local prune: %s", exc)

    from datetime import timedelta

    now = datetime.now()
    grace = CLOSE_GRACE_MINUTES * 60
    kept: Dict[str, Any] = {}
    for eid, event in events.items():
        if event.get("isFinished"):
            continue
        raw = event.get("bf_off_time") or event.get("t") or event.get("st")
        off = None
        if isinstance(raw, str) and ":" in raw:
            try:
                h, m = raw.strip().split(":")[:2]
                off = now.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
                if event.get("bf_off_time"):
                    off -= timedelta(hours=2)  # SAST wall -> container UTC
                elif (off - now).total_seconds() > 18 * 3600:
                    off -= timedelta(days=1)
            except (ValueError, TypeError):
                off = None
        if off is not None:
            if (now - off).total_seconds() > grace:
                continue
            # Keep the client-side contract identical to the monitor's closer:
            # expires_at lets the HUD/worker drop a race that finishes after
            # the snapshot was written, even in this degraded path.
            event["expires_at"] = off.timestamp() + grace
            event.pop("first_seen", None)
        kept[eid] = event
    return kept


def sanitize_snapshot(state: Dict[str, Any], *, source: str = "unknown") -> Dict[str, Any]:
    """Return a copy of ``state`` with only current races and fresh metadata.

    Idempotent: running it over the monitor's own pruned snapshot changes
    nothing except (re)stamping ``timestamp``/``snapshot_source``.
    """
    if not isinstance(state, dict):
        return {"events": {}, "count": 0, "timestamp": datetime.now().isoformat(),
                "snapshot_source": source}

    clean: Dict[str, Any] = dict(state)
    events = clean.get("events")
    if not isinstance(events, dict):
        events = {}

    active = {
        eid: {**e, "en": " ".join(str(e.get("en", "")).split())}
        for eid, e in events.items()
        if isinstance(e, dict) and not e.get("isFinished")
    }
    clean["events"] = _prune_events(active)
    clean["count"] = len(clean["events"])
    clean["timestamp"] = datetime.now().isoformat()
    # A producer that already labelled itself (e.g. the monitor stamps
    # "monitor") keeps its label; readers use it to report feed provenance.
    existing_source = clean.get("snapshot_source")
    clean["snapshot_source"] = (
        existing_source
        if isinstance(existing_source, str) and existing_source
        else source
    )
    return clean


def _atomic_write_json(path: Any, data: Any, indent: int = 2) -> None:
    """Write JSON atomically so a crash can never leave a half-written file."""
    tmp_path = str(path) + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=indent, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as exc:
        print(f"[WARN] Failed atomic write to {path}: {exc}")


def _snapshot_file_timestamp(state: Dict[str, Any]) -> float:
    """Epoch seconds for a snapshot payload's stamped ``timestamp`` (0.0 if absent)."""
    try:
        from datetime import datetime as _dt

        raw = state.get("timestamp")
        return _dt.fromisoformat(raw).timestamp() if raw else 0.0
    except Exception:
        return 0.0


def _last_write_info(path: Any = None) -> Dict[str, Any]:
    """(mtime, timestamp, source) of the current snapshot file (0.0/\"\" when unreadable)."""
    path = path or MARKET_SNAPSHOT_PATH
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return {"mtime": 0.0, "timestamp": 0.0, "source": ""}
    try:
        with open(path) as f:
            prev = json.load(f)
    except Exception:
        return {"mtime": mtime, "timestamp": 0.0, "source": ""}
    if not isinstance(prev, dict):
        return {"mtime": mtime, "timestamp": 0.0, "source": ""}
    source = prev.get("snapshot_source")
    return {
        "mtime": mtime,
        "timestamp": _snapshot_file_timestamp(prev),
        "source": source if isinstance(source, str) else "",
    }


def write_market_snapshot(
    state: Dict[str, Any],
    *,
    source: str,
    path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Prune + stamp + persist a market snapshot, then refresh the memory cache.

    Source priority: the monitor ("monitor") is the live writer; scan-side
    writers ("scheduler_scan" / "daily_scan") only provide the BHM-time card.
    A scan write must never clobber a fresher monitor file — so when the
    current file already carries a monitor timestamp newer than this payload,
    the write is skipped and the payload is returned for its in-memory use.

    Returns the sanitized state (never raises).
    """
    path = path or MARKET_SNAPSHOT_PATH
    try:
        clean = sanitize_snapshot(state, source=source)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Snapshot write skipped (%s): %s", source, exc)
        return state if isinstance(state, dict) else {"events": {}}

    if source in ("scheduler_scan", "daily_scan"):
        try:
            from datetime import datetime as _dt

            info = _last_write_info(path)
            payload_ts = _snapshot_file_timestamp(clean)
            # ISO timestamps carry microsecond resolution while filesystems /
            # clocks can differ by a hair — give the incumbent a 60s grace so a
            # same-minute scan payload never wins a photo-finish against the live
            # monitor file.
            if info.get("source") == "monitor" and info.get("timestamp", 0.0) + 60.0 > payload_ts:
                logger.info(
                    "Snapshot write skipped (%s): monitor file %s newer than payload %s",
                    source,
                    _dt.fromtimestamp(info["timestamp"]).isoformat(),
                    _dt.fromtimestamp(payload_ts).isoformat() if payload_ts else "unstamped",
                )
                return clean
            # The file's stat mtime is only a fallback: a monitor container that
            # started before this deployment stamps "unknown" — its mtime still
            # proves freshness versus this payload.
            if (
                not info.get("source")
                and info.get("mtime", 0.0) > payload_ts > 0.0
            ):
                logger.info(
                    "Snapshot write skipped (%s): existing file newer than payload",
                    source,
                )
                return clean
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Source-priority check skipped: %s", exc)

    try:
        _atomic_write_json(path, clean)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Snapshot write skipped (%s): %s", source, exc)
        return state if isinstance(state, dict) else {"events": {}}

    try:
        from core_agent.core.snapshot_cache import set_snapshot

        set_snapshot(clean, source=source)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Snapshot cache refresh skipped: %s", exc)
    return clean
