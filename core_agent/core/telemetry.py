"""
Engine Telemetry — lightweight in-memory ring buffer + optional Redis fanout.

Every background engine (Swarm Researcher, News poller, Dream heartbeat,
Governor) pushes structured events here. The SSE stream (monitoring.py)
serves the buffer to the HUD as `event: telemetry`; Redis pub/sub mirrors
it for multi-process deployments.

Zero external dependencies, zero disk I/O — events live in memory only.
"""

import asyncio
import json
import logging
import time
from collections import deque
from typing import Any, Dict, List, Optional

logger = logging.getLogger("telemetry")

MAX_EVENTS = 100

# (ts, engine, badge, message) tuples, newest at the right.
_buffer: deque = deque(maxlen=MAX_EVENTS)
_redis_client: Any = None
REDIS_TELEMETRY_CHANNEL = "agent:telemetry"


def emit(engine: str, message: str, badge: Optional[str] = None) -> Dict[str, Any]:
    """Record a telemetry event. Safe to call from anywhere; never raises."""
    event = {
        "ts": time.time(),
        "engine": engine,          # swarm | news | dream | governor | system
        "badge": badge or _default_badge(engine),
        "message": message[:300],
    }
    _buffer.append(event)
    logger.info(f"[TELEMETRY][{engine}] {event['message']}")
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_fanout(event))
    except RuntimeError:
        pass  # No running loop (sync context) — buffer-only is fine.
    return event


def _default_badge(engine: str) -> str:
    return {
        "swarm": "SWARM SCANNING",
        "news": "NEWS RAG",
        "dream": "DREAMING",
        "governor": "GOVERNOR CHECK",
        "system": "SYSTEM",
    }.get(engine, engine.upper())


async def _fanout(event: Dict[str, Any]) -> None:
    """Best-effort Redis publish so multi-process deployments see events too."""
    global _redis_client
    try:
        if _redis_client is None:
            from core_agent.core.task_queue import get_redis
            _redis_client = await get_redis()
        await _redis_client.publish(REDIS_TELEMETRY_CHANNEL, json.dumps(event))
    except Exception as e:
        logger.debug(f"Telemetry redis fanout skipped: {e}")


def get_events(limit: int = 30) -> List[Dict[str, Any]]:
    """Newest-first snapshot of recent events."""
    return list(_buffer)[-limit:][::-1]


def get_latest_by_engine() -> Dict[str, Dict[str, Any]]:
    """Most recent event per engine — used by the HUD status badges."""
    latest: Dict[str, Dict[str, Any]] = {}
    for ev in _buffer:
        latest[ev["engine"]] = ev  # later entries overwrite → newest wins
    return latest


def clear() -> None:
    _buffer.clear()
