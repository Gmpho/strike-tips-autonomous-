"""
Shared in-memory snapshot cache with Redis pub/sub for push-based updates.
Replaces disk polling with push-based in-memory updates.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("snapshot-cache")

_snapshot: Dict[str, Any] = {}
_redis_pubsub = None

REDIS_CHANNEL = "snapshot:updates"


def get_snapshot() -> Dict[str, Any]:
    if _snapshot:
        return _snapshot
    try:
        if os.path.exists(MARKET_SNAPSHOT_PATH):
            with open(MARKET_SNAPSHOT_PATH) as f:
                data = json.load(f)
            _snapshot.update(data)
            return _snapshot
    except Exception as e:
        logger.debug("Snapshot disk fallback failed: %s", e)
    return _snapshot or {"events": {}}


def set_snapshot(data: Dict[str, Any]) -> None:
    _snapshot.clear()
    _snapshot.update(data)


async def ensure_populated() -> None:
    """If snapshot is empty, try to fetch live data from Betway."""
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
            set_snapshot({"events": events, "count": len(events)})
            logger.info(f"[SNAPSHOT] Populated from Betway: {len(events)} races")
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
            await _redis_pubsub.unsubscribe(REDIS_CHANNEL)
            await _redis_pubsub.close()
            _redis_pubsub = None
