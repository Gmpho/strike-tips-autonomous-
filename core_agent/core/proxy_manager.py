"""
Rotating proxy pool with dead-proxy tracking.
Loads proxies from SCRAPER_PROXIES env var (comma-separated).
"""

import os
import random
import logging
from typing import Optional, List

logger = logging.getLogger("proxy-manager")

BROWSERS = [
    "chrome131",
    "chrome124",
    "safari17_0",
    "firefox135",
]

class ProxyManager:
    def __init__(self):
        raw = os.environ.get("SCRAPER_PROXIES", "")
        self._proxies: List[str] = [p.strip() for p in raw.split(",") if p.strip()]
        self._dead: set = set()
        self._round_robin_idx = 0
        if self._proxies:
            logger.info(f"ProxyManager loaded {len(self._proxies)} proxies")
        else:
            logger.info("ProxyManager: no proxies configured — direct connections")

    def get_proxy(self) -> Optional[str]:
        alive = [p for p in self._proxies if p not in self._dead]
        if not alive:
            return None
        proxy = alive[self._round_robin_idx % len(alive)]
        self._round_robin_idx = (self._round_robin_idx + 1) % len(alive)
        return proxy

    def mark_dead(self, proxy: str):
        if proxy:
            self._dead.add(proxy)
            logger.warning(f"Proxy marked dead: {proxy} ({len(self._dead)}/{len(self._proxies)} dead)")

    def get_impersonate(self) -> str:
        return random.choice(BROWSERS)

    @property
    def has_proxies(self) -> bool:
        return len(self._proxies) > 0

    @property
    def alive_count(self) -> int:
        return len([p for p in self._proxies if p not in self._dead])


_manager: Optional[ProxyManager] = None

def get_proxy_manager() -> ProxyManager:
    global _manager
    if _manager is None:
        _manager = ProxyManager()
    return _manager
