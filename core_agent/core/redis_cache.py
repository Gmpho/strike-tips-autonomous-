"""
Async Redis-backed cache for search results and general key-value caching.
Replaces the old sync disk-backed search_cache.py.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger("redis-cache")

_SEARCH_TTL = 86400
_MAX_CACHE_SIZE = 500


async def get_cache(key: str) -> Optional[Any]:
    from core_agent.core.task_queue import get_redis
    try:
        r = await get_redis()
        data = await r.get(f"cache:{key}")
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.debug("Redis cache get failed: %s", e)
    return None


async def set_cache(key: str, value: Any, ttl: int = _SEARCH_TTL) -> None:
    from core_agent.core.task_queue import get_redis
    try:
        r = await get_redis()
        await r.setex(f"cache:{key}", ttl, json.dumps(value))
        await _enforce_max_size(r)
    except Exception as e:
        logger.debug("Redis cache set failed: %s", e)


async def clear_cache() -> None:
    from core_agent.core.task_queue import get_redis
    try:
        r = await get_redis()
        cursor = 0
        while True:
            cursor, keys = await r.scan(cursor=cursor, match="cache:*", count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break
    except Exception as e:
        logger.warning("Redis cache clear failed: %s", e)


async def _enforce_max_size(r) -> None:
    count = await r.dbsize()
    if count > _MAX_CACHE_SIZE * 2:
        cursor = 0
        keys_to_delete = count - _MAX_CACHE_SIZE
        deleted = 0
        while deleted < keys_to_delete:
            cursor, keys = await r.scan(cursor=cursor, match="cache:*", count=50)
            if keys:
                await r.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
