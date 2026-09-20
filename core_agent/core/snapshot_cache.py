"""
Shared in-memory snapshot cache with Redis pub/sub for push-based updates.
Replaces disk polling with push-based in-memory updates.
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH, NEWS_PATH

logger = logging.getLogger("snapshot-cache")

_snapshot: Dict[str, Any] = {}
_redis_pubsub = None

REDIS_CHANNEL = "snapshot:updates"

# Freshness bookkeeping for /api/monitoring/snapshot* — the HUD shows the
# monitor's write time instead of silently rendering a stale card.
_snapshot_source: str = "unknown"
_snapshot_written_at: float = 0.0


def _sanitize(data: Dict[str, Any], source: str) -> Dict[str, Any]:
    """Prune a snapshot to current races via the snapshot writer.

    Runs on every ingress (disk poll, Redis, monitor push, scan-side writes)
    so a legacy/unpruned file can never leak finished races to the HUD.
    """
    try:
        from core_agent.core.snapshot_writer import sanitize_snapshot

        return sanitize_snapshot(data, source=source)
    except Exception as e:  # pragma: no cover - defensive
        logger.debug("Snapshot sanitize skipped: %s", e)
        return data


def _timestamp_epoch(data: Dict[str, Any]) -> float:
    """Epoch seconds for the snapshot's stamped ``timestamp`` (0.0 if absent)."""
    try:
        from datetime import datetime as _dt

        raw = data.get("timestamp")
        return _dt.fromisoformat(raw).timestamp() if raw else 0.0
    except Exception:
        return 0.0

# ---------------------------------------------------------------------------
# News in-memory cache — mirrors the snapshot pattern for news_latest.json.
# Populated at startup and refreshed every 15s by news_mtime_refresh_loop.
# ---------------------------------------------------------------------------
_news_cache: List[Any] = []
_last_news_mtime: float = 0.0


def get_snapshot() -> Dict[str, Any]:
    if _snapshot:
        return _snapshot
    try:
        if os.path.exists(MARKET_SNAPSHOT_PATH):
            with open(MARKET_SNAPSHOT_PATH) as f:
                data = json.load(f)
            set_snapshot(
                data,
                source="disk-startup",
                written_at=os.path.getmtime(MARKET_SNAPSHOT_PATH),
            )
            return _snapshot
    except Exception as e:
        logger.debug("Snapshot disk fallback failed: %s", e)
    return _snapshot or {"events": {}}


def set_snapshot(
    data: Dict[str, Any],
    source: str = "unknown",
    written_at: Optional[float] = None,
) -> None:
    """Sanitize + store a snapshot; records source and write time.

    ``written_at`` (epoch secs) — pass the file mtime when the payload came
    from disk so age reporting reflects the writer, not the reader.
    """
    global _snapshot_source, _snapshot_written_at
    clean = _sanitize(data if isinstance(data, dict) else {}, source)
    _snapshot.clear()
    _snapshot.update(clean)
    # Prefer the producer's own label (monitor / scheduler_scan / daily_scan);
    # fall back to how this copy arrived (disk-poll, redis, ...).
    payload_source = clean.get("snapshot_source")
    _snapshot_source = (
        payload_source
        if isinstance(payload_source, str) and payload_source
        else source
    )
    _snapshot_written_at = written_at or _timestamp_epoch(clean) or time.time()


def get_snapshot_meta() -> Dict[str, Any]:
    """Source, write time and age (secs) of the cached snapshot."""
    age = None
    if _snapshot_written_at > 0:
        age = max(0.0, time.time() - _snapshot_written_at)
    return {
        "source": _snapshot_source,
        "written_at": _snapshot_written_at or None,
        "age_secs": round(age, 1) if age is not None else None,
    }


def get_news() -> List[Any]:
    """Return the in-memory news cache, falling back to a direct disk read."""
    if _news_cache:
        return list(_news_cache)
    try:
        if os.path.exists(NEWS_PATH):
            with open(NEWS_PATH) as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                _news_cache.extend(data)
                return list(_news_cache)
    except Exception as e:
        logger.debug("News disk fallback failed: %s", e)
    return []


_last_disk_mtime: float = 0.0


async def disk_refresh_loop(interval: int = 15) -> None:
    """Poll market_snapshot_latest.json mtime; reload on change.

    The 5-min monitor cron is the writer; web containers are readers.
    Without this, the web in-memory snapshot freezes at container startup
    (Sep-2026: bundle served 138 morning events all day while the monitor
    synced 90). One stat per interval; full parse only on change.
    Interval reduced from 60s → 15s (Sep-2026: 60s meant up to 1-min lag
    even when the monitor cron ran perfectly).
    """
    global _last_disk_mtime
    import time as _time

    while True:
        try:
            await asyncio.sleep(interval)
            try:
                mtime = os.path.getmtime(MARKET_SNAPSHOT_PATH)
            except OSError:
                continue
            if mtime <= _last_disk_mtime:
                continue
            with open(MARKET_SNAPSHOT_PATH) as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("events") is not None:
                set_snapshot(data, source="disk-poll", written_at=mtime)
                _last_disk_mtime = mtime
                logger.info(
                    "Snapshot reloaded from disk (%d events after pruning)",
                    len(_snapshot.get("events", {})),
                )
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"Snapshot disk refresh skipped: {e}")


async def news_mtime_refresh_loop(interval: int = 15) -> None:
    """Poll news_latest.json mtime; reload in-memory cache on change.

    The Swarm Researcher (monitor/cron container) is the writer; web
    containers are readers. Without this loop, the news feed in the web
    container freezes at startup mtime — same root cause as the snapshot
    staleness fixed by disk_refresh_loop.
    Interval: 15s (matches snapshot refresh for consistent freshness).
    """
    global _news_cache, _last_news_mtime
    import time as _time

    while True:
        try:
            await asyncio.sleep(interval)
            try:
                mtime = os.path.getmtime(NEWS_PATH)
            except OSError:
                continue
            if mtime <= _last_news_mtime:
                continue
            with open(NEWS_PATH) as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                _news_cache.clear()
                _news_cache.extend(data)
                _last_news_mtime = mtime
                logger.info("News reloaded from disk (%d items)", len(data))
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.debug(f"News disk refresh skipped: {e}")


async def ensure_populated() -> None:
    """If the snapshot is empty, fetch a live Betway card as a stopgap.

    The in-process fetch is raw (no off-time pruning), so it MUST go through
    ``set_snapshot``'s sanitizer — otherwise it re-introduces the Sep-2026
    "126-event morning card served all day" regression in containers that
    boot before the monitor's next cron tick.
    """
    if _snapshot:
        return
    try:
        from core_agent.skills.parsers.betway_api import BetwayAPI
        betway = BetwayAPI()
        races = await betway.get_races()
        if races:
            events = {}
            for r in races:
                eid = f"{r.track}_{r.race_number}".replace(" ", "_").lower()
                events[eid] = {
                    "en": r.track,
                    "raceNumber": r.race_number,
                    "t": r.race_time,
                    "course": r.track,
                    "runners": [
                        {"outcomeName": rn.horse_name, "odds": rn.odds_decimal}
                        for rn in r.runners[:5]
                    ],
                }
            set_snapshot({"events": events, "count": len(events)}, source="betway-fallback")
            logger.info(
                "[SNAPSHOT] Populated from Betway: %d races (%d after pruning)",
                len(events), len(_snapshot.get("events", {})),
            )
    except Exception as e:
        logger.debug(f"[SNAPSHOT] Betway fallback failed: {e}")


async def publish_snapshot(redis_client, data: Dict[str, Any]) -> None:
    try:
        await redis_client.publish(REDIS_CHANNEL, json.dumps(data))
    except Exception as e:
        logger.debug("Redis publish failed: %s", e)


async def subscribe_snapshot(redis_client) -> None:
    global _redis_pubsub
    try:
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(REDIS_CHANNEL)
        _redis_pubsub = pubsub
        logger.info("Subscribed to Redis channel: %s", REDIS_CHANNEL)
        while True:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=30.0)
            if msg and msg["type"] == "message":
                try:
                    data = json.loads(msg["data"])
                    set_snapshot(data)
                    logger.debug("Snapshot updated via Redis pub/sub")
                except Exception as e:
                    logger.debug("Failed to parse snapshot update: %s", e)
    except Exception as e:
        logger.warning("Redis subscriber stopped: %s", e)
    finally:
        if _redis_pubsub:
            try:
                # Attempt to unsubscribe and close only if event loop is still running
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    await _redis_pubsub.unsubscribe(REDIS_CHANNEL)
                    await _redis_pubsub.close()
                else:
                    # Loop is closed; just discard the pubsub object
                    pass
            except Exception:
                # Ignore any errors during cleanup
                pass
            finally:
                _redis_pubsub = None
