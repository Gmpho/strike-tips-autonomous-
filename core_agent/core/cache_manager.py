import json
import os
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger("CacheManager")

class CacheManager:
    """
    Tier-0 Memory: Hybrid Cache Manager.
    Ported from User's Gold Standard Project.
    """
    
    def __init__(self, cache_dir: str = "/app/data/cache", ttl_minutes: int = 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(minutes=ttl_minutes)
        self._memory_cache: Dict[str, Dict] = {}
        
        self.stats = {"hits": 0, "misses": 0}

    def _get_key(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()

    def get(self, url: str) -> Optional[Dict]:
        key = self._get_key(url)
        
        # 1. Memory Hit
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            if not self._is_expired(entry["cached_at"]):
                self.stats["hits"] += 1
                return entry["data"]
            del self._memory_cache[key]

        # 2. File Fallback
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, 'r') as f:
                    entry = json.load(f)
                if not self._is_expired(entry["cached_at"]):
                    self._memory_cache[key] = entry
                    self.stats["hits"] += 1
                    return entry["data"]
                cache_file.unlink()
            except: pass
            
        self.stats["misses"] += 1
        return None

    def set(self, url: str, data: Dict):
        key = self._get_key(url)
        entry = {
            "url": url,
            "cached_at": datetime.now().isoformat(),
            "data": data
        }
        self._memory_cache[key] = entry
        
        # Persist
        try:
            with open(self.cache_dir / f"{key}.json", 'w') as f:
                json.dump(entry, f)
        except: pass

    def _is_expired(self, cached_at_str: str) -> bool:
        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            return (datetime.now() - cached_at) > self.ttl
        except: return True

    def get_stats(self):
        return self.stats
