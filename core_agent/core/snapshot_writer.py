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
from datetime import datetime, timezone
from pathlib import Path
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
        raw = event.get("t") or event.get("st")
        bf_raw = event.get("bf_off_time")
        off = None
        if isinstance(raw, str) and ":" in raw:
            try:
                h, m = raw.strip().split(":")[:2]
                # Betway t/st are UTC wall-clock. Force the base to UTC so an
                # SAST host cannot shift every off-time by two hours.
                off = datetime.now(timezone.utc).replace(tzinfo=None).replace(
                    hour=int(h), minute=int(m), second=0, microsecond=0
                )
                if (off - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() > 18 * 3600:
                    off -= timedelta(days=1)
            except (ValueError, TypeError):
                off = None
        if isinstance(bf_raw, str) and ":" in bf_raw:
            try:
                h, m = bf_raw.strip().split(":")[:2]
                bf = datetime.now(timezone.utc).replace(tzinfo=None).replace(
                    hour=int(h), minute=int(m), second=0, microsecond=0
                ) - timedelta(hours=2)  # SAST wall -> UTC
                # Prefer the earlier plausible clock: a stale Betfair time
                # must not keep a finished race alive (Scottsville R1 bug).
                if off is None or abs((bf - off).total_seconds()) <= 3 * 3600:
                    off = bf if off is None else min(off, bf)
            except (ValueError, TypeError):
                pass
        if off is not None:
            if (datetime.now(timezone.utc).replace(tzinfo=None) - off).total_seconds() > grace:
                continue
            # Keep the client-side contract identical to the monitor's closer:
            # expires_at lets the HUD/worker drop a race that finishes after
            # the snapshot was written, even in this degraded path.
            event["expires_at"] = off.replace(tzinfo=timezone.utc).timestamp() + grace
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


# Durable race registry (Nov-21). Carry-forward from the *previous* snapshot
# alone still allows a race to vanish after two missed cycles and then come
# back when a late GetEvent succeeds. Keep the last good body of every race
# seen today, plus tombstones for races whose off-time has passed, so a race
# cannot disappear on a single miss nor be resurrected once expired.
RACE_REGISTRY_PATH = os.environ.get("BETWAY_RACE_REGISTRY") or str(
    Path(__file__).resolve().parents[3] / "data" / "betway_race_registry.json"
)
_REGISTRY_TOMBSTONE_TTL_SECS = 24 * 3600


def _load_race_registry() -> Dict[str, Any]:
    try:
        raw = json.loads(Path(RACE_REGISTRY_PATH).read_text())
    except Exception:
        return {"events": {}, "tombstones": {}}
    if not isinstance(raw, dict):
        return {"events": {}, "tombstones": {}}
    events = raw.get("events") if isinstance(raw.get("events"), dict) else {}
    tombstones = raw.get("tombstones") if isinstance(raw.get("tombstones"), dict) else {}
    return {"events": events, "tombstones": tombstones}


def _save_race_registry(registry: Dict[str, Any]) -> None:
    try:
        path = Path(RACE_REGISTRY_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(registry, default=str))
    except Exception as exc:  # pragma: no cover - read-only volume
        logger.debug("Race registry write skipped: %s", exc)


def merge_registry_events(state: Dict[str, Any], path: Any = None) -> Dict[str, Any]:
    """Union in last-good races, and permanently drop expired ones.

    A race seen on any cycle survives partial fetches; a race whose
    ``expires_at`` has passed is tombstoned so a late GetEvent success cannot
    put a finished race back on the card.
    """
    clean: Dict[str, Any] = dict(state)
    events = clean.get("events")
    if not isinstance(events, dict):
        return clean
    now_dt = datetime.now()
    now = now_dt.timestamp()
    registry = _load_race_registry()
    known = registry["events"]
    tombstones = registry["tombstones"]

    # 1. Never re-add an expired/tombstoned race, even if this cycle fetched it.
    for eid in list(tombstones):
        try:
            if now - float(tombstones[eid]) < _REGISTRY_TOMBSTONE_TTL_SECS:
                events.pop(eid, None)
            else:
                del tombstones[eid]
        except Exception:
            del tombstones[eid]

    # 2. Tombstone known races whose off-time has genuinely passed.
    for eid, entry in list(known.items()):
        try:
            expires = float((entry or {}).get("expires_at") or 0)
        except Exception:
            expires = 0.0
        if expires and expires <= now:
            events.pop(eid, None)
            tombstones[eid] = expires
            del known[eid]

    # 3. Restore still-live races missing from this cycle's partial fetch.
    restored = 0
    for eid, entry in known.items():
        if eid in events:
            continue
        ev = entry.get("event") if isinstance(entry, dict) else None
        if not isinstance(ev, dict) or ev.get("isFinished"):
            continue
        if sanitize_snapshot({"events": {eid: ev}}, source="registry")["events"]:
            events[eid] = ev
            restored += 1

    # 4. Refresh every currently-fetched race's last-good body.
    for eid, ev in events.items():
        if isinstance(ev, dict):
            known[eid] = {
                "event": ev,
                "expires_at": ev.get("expires_at"),
                "last_seen": now_dt.isoformat(),
            }

    if restored:
        logger.info("Race registry restored %d still-live event(s)", restored)
    clean["events"] = events
    clean["count"] = len(events)
    _save_race_registry(registry)
    return clean


def _merge_previous_live_events(clean: Dict[str, Any], path: Any = None) -> Dict[str, Any]:
    """Carry forward still-live events from the previous snapshot.

    Partial per-event fetch failures (e.g. Betway 403 on some GetEvent calls)
    mean a writer can produce a valid-but-incomplete card. Without a merge,
    each full-overwrite write would drop races that were present last cycle
    but missed this one, causing oscillation (26→30→18…) and "disappearing"
    races. We union in previous events that are still live (not finished,
    not past off-time/grace) and missing from the new snapshot. Pruning is
    applied to previous events so expired/zombie races are never resurrected.
    """
    path = path or MARKET_SNAPSHOT_PATH
    try:
        with open(path) as f:
            prev = json.load(f)
    except Exception:
        return clean
    prev_events = prev.get("events") if isinstance(prev, dict) else None
    if not isinstance(prev_events, dict) or not prev_events:
        return clean
    try:
        prev_clean = sanitize_snapshot(
            {"events": prev_events},
            source=str(prev.get("snapshot_source") or "previous"),
        )
        prev_live = prev_clean.get("events") or {}
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Previous-snapshot merge skipped: %s", exc)
        return clean

    events = clean.get("events")
    if not isinstance(events, dict):
        events = {}
    added = 0
    for eid, ev in prev_live.items():
        if eid not in events:
            events[eid] = ev
            added += 1
    if added:
        clean["events"] = events
        clean["count"] = len(events)
        logger.info(
            "Carried forward %d still-live event(s) missing from new snapshot",
            added,
        )
    return clean


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

    # Stabilise against partial per-event fetch failures: keep still-live races
    # from the previous snapshot that are missing from this (incomplete) fetch.
    try:
        clean = _merge_previous_live_events(clean, path)
        try:
            clean = merge_registry_events(clean, path)
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("Race registry merge failed: %s", exc)
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Previous-snapshot merge failed: %s", exc)

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

    # Feed the canonical market event stream. This is the primary source of
    # "a price moved" — 5-minute cadence across every meeting we quote,
    # instead of ATR's 45-minute challenge-walled page. Hooked here because
    # this is the single sanctioned writer: every producer of a snapshot
    # feeds the stream by using it, and no producer has to remember to.
    try:
        from core_agent.core.market_events import diff_snapshot

        moved = diff_snapshot(clean)
        if moved:
            logger.info(
                "Market events: %d move(s) recorded (%s)",
                len(moved),
                ", ".join(
                    f"{(e.get('race') or {}).get('course')} "
                    f"R{(e.get('race') or {}).get('race_number')} "
                    f"{(e.get('runner') or {}).get('name')} "
                    f"{e.get('prev')}->{e.get('price')}"
                    for e in moved[:4]
                ),
            )
    except Exception as exc:  # pragma: no cover - defensive
        logger.debug("Market event diff skipped: %s", exc)

    return clean
