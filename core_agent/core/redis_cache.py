"""
Async Redis-backed cache for search results and general key-value caching.
Replaces the old sync disk-backed search_cache.py.
Includes in-memory fallback for when Redis is unavailable.
"""

import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger("redis-cache")

_SEARCH_TTL = 86400
_MAX_CACHE_SIZE = 500

# In-memory fallback for when Redis is unavailable
_memory_cache: dict = {}
_memory_cache_ttl: dict = {}


def _clean_expired():
    """Remove expired entries from memory cache."""
    now = time.time()
    expired = [k for k, exp in _memory_cache_ttl.items() if exp < now]
    for k in expired:
        _memory_cache.pop(k, None)
        _memory_cache_ttl.pop(k, None)


async def get_cache(key: str) -> Optional[Any]:
    # Try Redis first
    try:
        from core_agent.core.task_queue import get_redis
        r = await get_redis()
        data = await r.get(f"cache:{key}")
        if data is not None:
            return json.loads(data)
    except Exception as e:
        logger.debug("Redis cache get failed: %s", e)

    # Fallback to in-memory
    _clean_expired()
    return _memory_cache.get(key)


async def set_cache(key: str, value: Any, ttl: int = _SEARCH_TTL) -> None:
    # Try Redis first
    try:
        from core_agent.core.task_queue import get_redis
        r = await get_redis()
        await r.setex(f"cache:{key}", ttl, json.dumps(value))
        await _enforce_max_size(r)
    except Exception as e:
        logger.debug("Redis cache set failed: %s", e)

    # Always store in memory as fallback
    _clean_expired()
    _memory_cache[key] = value
    _memory_cache_ttl[key] = time.time() + ttl


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
