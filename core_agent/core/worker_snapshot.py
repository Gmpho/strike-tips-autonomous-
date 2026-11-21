"""Read the freshest odds card published to the Cloudflare Worker KV.

Two writers publish snapshots: the Modal cron (datacenter IP, intermittently
blocked by Betway) and the home-network odds monitor (residential IP, usually
accepted). The Worker serves whichever is newer. Modal's HUD endpoints prefer
that card when it is fresher than the local volume copy, so prod stops showing
a 90-race blocked card while the home container holds a live 220-race card.

Network-only, cheap, fail-open: any error falls back to the local volume.
"""

import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger("worker-snapshot")

_WORKER_URL = "https://striketips-mcp.gmphorg379.workers.dev"
_CACHE_SECS = 20.0
_cached: Optional[Dict[str, Any]] = None
_cached_at = 0.0


def _stamp(value: Any) -> float:
    """Epoch seconds for a snapshot timestamp, naive strings treated as UTC."""
    if not isinstance(value, str) or not value:
        return 0.0
    try:
        iso = value if value.endswith("Z") or "+" in value[10:] else value + "Z"
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


async def fetch_best_snapshot() -> Optional[Dict[str, Any]]:
    """Best-effort read of the Worker's freshest snapshot (20s memoised)."""
    global _cached, _cached_at
    now = time.monotonic()
    if _cached is not None and now - _cached_at < _CACHE_SECS:
        return _cached
    try:
        import httpx

        url = (os.environ.get("CLOUDFLARE_MCP_URL") or _WORKER_URL).rstrip("/")
        key = os.environ.get("STRIKE_TIPS_API_KEY") or os.environ.get("BACKEND_API_KEY") or ""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{url}/api/racing/odds", headers={"x-api-key": key} if key else None
            )
        data = resp.json() if resp.status_code == 200 else None
        _cached = data if isinstance(data, dict) and data.get("events") else None
        _cached_at = now
        logger.info(
            "Worker snapshot read: url=%s status=%s races=%d",
            url, resp.status_code, len(_cached.get("events") or {}) if _cached else 0,
        )
        return _cached
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Worker snapshot read failed: %s", exc)
        _cached, _cached_at = None, now
        return None
