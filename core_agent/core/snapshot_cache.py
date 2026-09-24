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
_volume_obj: Optional[Any] = None
_volume_retry_at: float = 0.0
_volume_lock: Optional[Any] = None
_volume_last_reload: float = 0.0

_VOLUME_NAME = "strike-tips-data"
_VOLUME_RETRY_SECS = 600.0
# Two loops (snapshot + news) share one volume object; reloads are serialized
# and throttled (Sep-2026: concurrent reloads deadlocked — exactly one ingest
# at container startup, then every later monitor write was ignored).
_VOLUME_RELOAD_MIN_SECS = 14.0
_VOLUME_RELOAD_TIMEOUT = 30.0


def _get_data_volume() -> Optional[Any]:
    """The Modal volume backing ``/app/data``, or ``None`` outside Modal.

    Cross-container visibility: Modal Volumes are cached per container.
    The monitor cron writes ``market_snapshot_latest.json`` from its own
    container, while this web container's mount keeps serving the view it
    had at startup — ``volume.reload()`` is the documented way to see other
    containers' writes. (Sep-2026: ``disk_refresh_loop`` polled mtime on the
    stale view, so every monitor write was invisible to the web keeper and
    the HUD stayed on the container's own ``scheduler_scan`` card for hours
    while the volume file carried a fresh, Betfair-rich monitor snapshot.)
    """
    global _volume_obj, _volume_retry_at
    if _volume_obj is not None:
        return _volume_obj
    if time.time() < _volume_retry_at:
        return None
    if not os.environ.get("MODAL_TASK_ID") and not os.environ.get("MODAL_TOKEN_ID"):
        # Plain docker/local: bind mounts already share writes, so a Modal
        # reload is pointless — and Volume.from_name() constructs lazily,
        # meaning the AuthError only surfaces on reload(), spamming every
        # refresh cycle (Sep-2026: docker logs full of AuthError noise while
        # the disk fallback carried every read anyway).
        logger.debug("Not on Modal — skipping volume reload (bind mount is live)")
        _volume_retry_at = time.time() + _VOLUME_RETRY_SECS
        return None
    try:
        import modal

        _volume_obj = modal.Volume.from_name(_VOLUME_NAME, create_if_missing=False)
        return _volume_obj
    except Exception as e:
        # No token / not on Modal / modal not installed — stat the local
        # mount as before (works for same-container writers and shared
        # bind mounts, e.g. docker-compose).
        logger.debug("Modal volume unavailable for disk refresh: %s", e)
        _volume_retry_at = time.time() + _VOLUME_RETRY_SECS
        return None


async def _reload_data_volume() -> None:
    """Reload the Modal volume so cross-container writes become visible.

    Serialized + throttled (the two refresh loops share one volume object —
    concurrent reloads deadlocked, Sep-2026) and timeout-bounded so a hung
    reload can never stall the refresh loops again.
    """
    global _volume_lock, _volume_last_reload
    vol = _get_data_volume()
    if vol is None:
        return
    if _volume_lock is None:
        _volume_lock = asyncio.Lock()
    since = time.time() - _volume_last_reload
    if since < _VOLUME_RELOAD_MIN_SECS:
        return
    async with _volume_lock:
        since = time.time() - _volume_last_reload
        if since < _VOLUME_RELOAD_MIN_SECS:
            return
        try:
            aio_reload = getattr(vol.reload, "aio", None)

            async def _do_reload():
                if aio_reload is not None:
                    await aio_reload()
                else:
                    await asyncio.to_thread(vol.reload)

            # wait_for cancels a hung reload instead of freezing the loop.
            await asyncio.wait_for(_do_reload(), timeout=_VOLUME_RELOAD_TIMEOUT)
            _volume_last_reload = time.time()
            print(
                f"[snapshot-cache] volume reloaded ok "
                f"(last ingest age {since:.0f}s)",
                flush=True,
            )
        except asyncio.TimeoutError:
            print("[snapshot-cache] volume reload TIMED OUT", flush=True)
        except Exception as e:
            print(f"[snapshot-cache] volume reload failed: {e!r}", flush=True)


async def disk_refresh_loop(interval: int = 15) -> None:
    """Poll market_snapshot_latest.json mtime; reload on change.

    The 5-min monitor cron is the writer; web containers are readers.
    Without this, the web in-memory snapshot freezes at container startup
    (Sep-2026: bundle served 138 morning events all day while the monitor
    synced 90). One stat per interval; full parse only on change.
    Interval reduced from 60s → 15s (Sep-2026: 60s meant up to 1-min lag
    even when the monitor cron ran perfectly).

    On Modal the volume must be reloaded each cycle before stat — the
    mount caches the startup view, so monitor writes are otherwise
    invisible for the life of the web container (see _get_data_volume).
    """
    global _last_disk_mtime
    import time as _time

    while True:
        try:
            await asyncio.sleep(interval)
            await _reload_data_volume()
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
            await _reload_data_volume()
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
