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

# Disk mirror so events survive across containers. The in-memory buffer only
# ever sees the current process's emits (serve vs monitor vs scheduled jobs
# are separate containers; Redis fanout has no server-side subscriber and no
# Modal Redis to publish to). Every emit appends one JSON line; readers merge
# the file tail with memory. Best-effort throughout — telemetry must never
# break the caller.
TELEMETRY_FILE = "telemetry.jsonl"
TELEMETRY_FILE_MAX_LINES = 250

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
    _append_to_file(event)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_fanout(event))
    except RuntimeError:
        pass  # No running loop (sync context) — buffer-only is fine.
    return event


def _telemetry_path() -> Optional[str]:
    try:
        from core_agent.config.paths import DATA_DIR
        return str(DATA_DIR / TELEMETRY_FILE)
    except Exception:
        return None


def _append_to_file(event: Dict[str, Any]) -> None:
    path = _telemetry_path()
    if not path:
        return
    try:
        with open(path, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        return
    # Opportunistic trim (keeps the file bounded; races harmless).
    try:
        with open(path) as f:
            lines = f.readlines()
        if len(lines) > TELEMETRY_FILE_MAX_LINES:
            with open(path, "w") as f:
                f.writelines(lines[-TELEMETRY_FILE_MAX_LINES:])
    except Exception:
        pass


def _read_file_events(limit: int) -> List[Dict[str, Any]]:
    path = _telemetry_path()
    if not path:
        return []
    try:
        with open(path) as f:
            lines = f.readlines()[-limit:]
        out = []
        for line in lines:
            try:
                ev = json.loads(line)
                if isinstance(ev, dict) and ev.get("ts") and ev.get("engine"):
                    out.append(ev)
            except Exception:
                continue
        return out
    except Exception:
        return []


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
    """Newest-first snapshot of recent events (memory + cross-container file)."""
    seen = set()
    merged: List[Dict[str, Any]] = []
    for ev in list(_buffer) + _read_file_events(MAX_EVENTS):
        key = (ev.get("ts"), ev.get("engine"), ev.get("message"))
        if key in seen:
            continue
        seen.add(key)
        merged.append(ev)
    merged.sort(key=lambda e: float(e.get("ts") or 0), reverse=True)
    return merged[:limit]


def get_latest_by_engine() -> Dict[str, Dict[str, Any]]:
    """Most recent event per engine — used by the HUD status badges."""
    latest: Dict[str, Dict[str, Any]] = {}
    for ev in get_events(MAX_EVENTS):
        if ev["engine"] not in latest:
            latest[ev["engine"]] = ev  # get_events is newest-first
    return latest


def clear() -> None:
    _buffer.clear()
