"""
Persistent JSON-backed search cache.
Survives restarts — written to disk as search_cache.json.
"""

import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("search-cache")

CACHE_FILE = os.path.join(os.path.dirname(__file__), "search_cache.json")
MAX_CACHE_SIZE = 500

_cache: dict = None


def _load():
    global _cache
    if _cache is not None:
        return
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                data = json.load(f)
                _cache = data if isinstance(data, dict) else {}
        else:
            _cache = {}
    except Exception as e:
        logger.warning(f"Failed to load search cache: {e}")
        _cache = {}


def _save():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f)
    except Exception as e:
        logger.warning(f"Failed to save search cache: {e}")


def get_cache(key: str) -> Optional[Any]:
    _load()
    return _cache.get(key)


def set_cache(key: str, value: Any):
    _load()
    if len(_cache) >= MAX_CACHE_SIZE:
        _cache.pop(next(iter(_cache)))
    _cache[key] = value
    _save()


def clear_cache():
    global _cache
    _cache = {}
    _save()
