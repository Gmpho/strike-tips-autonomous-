"""
Task Queue — Redis-backed lightweight task queue.
Uses Redis lists for FIFO queuing and hashes for task status/metadata.
No Celery dependency — designed for asyncio.run() worker pattern.
"""

import json
import logging
import os
import time
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("task-queue")

QUEUE_KEY = "task_queue:pending"
TASK_PREFIX = "task:"
TASK_TTL = 86400 * 7  # 7 days

_task_redis: Optional[aioredis.Redis] = None
_lock = asyncio.Lock()

async def get_redis() -> aioredis.Redis:
    global _task_redis
    async with _lock:
        if _task_redis is None:
            url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _task_redis = aioredis.from_url(
                url, 
                decode_responses=True,
                max_connections=5, 
                socket_connect_timeout=5
            )
        return _task_redis


async def close_redis():
    global _task_redis
    if _task_redis:
        await _task_redis.close()
        _task_redis = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def enqueue(task_type: str, params: Optional[Dict[str, Any]] = None) -> str:
    r = await get_redis()
    task_id = str(uuid.uuid4())
    now = _now_iso()
    task = {
        "task_id": task_id,
        "type": task_type,
        "params": params or {},
        "status": "queued",
        "created_at": now,
        "started_at": None,
        "completed_at": None,
        "result": None,
        "error": None,
    }
    clean = {k: (json.dumps(v) if not isinstance(v, str) and v is not None else (v or "")) for k, v in task.items()}
    await r.hset(f"{TASK_PREFIX}{task_id}", mapping=clean)
    await r.expire(f"{TASK_PREFIX}{task_id}", TASK_TTL)
    await r.lpush(QUEUE_KEY, task_id)
    logger.info("Task %s enqueued: type=%s params=%s", task_id, task_type, params)
    return task_id


async def dequeue(timeout: int = 5) -> Optional[Dict[str, Any]]:
    r = await get_redis()
    result = await r.brpop(QUEUE_KEY, timeout=timeout)
    if result is None:
        return None
    _, task_id = result
    raw = await r.hgetall(f"{TASK_PREFIX}{task_id}")
    if not raw:
        return None
    task = dict(raw)
    for field in ("params", "result"):
        val = task.get(field)
        if val and isinstance(val, str):
            try:
                task[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    started_at = _now_iso()
    await r.hset(f"{TASK_PREFIX}{task_id}", mapping={"status": "running", "started_at": started_at})
    task["status"] = "running"
    task["started_at"] = started_at
    return task


async def complete(task_id: str, result: Any = None):
    r = await get_redis()
    now = _now_iso()
    await r.hset(
        f"{TASK_PREFIX}{task_id}",
        mapping={
            "status": "completed",
            "completed_at": now,
            "result": json.dumps(result) if result is not None else "",
        },
    )


async def fail(task_id: str, error: str):
    r = await get_redis()
    now = _now_iso()
    await r.hset(
        f"{TASK_PREFIX}{task_id}",
        mapping={"status": "failed", "completed_at": now, "error": str(error)},
    )


async def get_status(task_id: str) -> Optional[Dict[str, Any]]:
    r = await get_redis()
    task = await r.hgetall(f"{TASK_PREFIX}{task_id}")
    if not task:
        return None
    for field in ("params", "result"):
        val = task.get(field)
        if val and isinstance(val, str):
            try:
                task[field] = json.loads(val)
            except (json.JSONDecodeError, TypeError):
                pass
    return task


async def list_tasks(status_filter: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    r = await get_redis()
    tasks = []
    async for key in r.scan_iter(match=f"{TASK_PREFIX}*", count=200):
        raw = await r.hgetall(key)
        if raw:
            task = dict(raw)
            for field in ("params", "result"):
                val = task.get(field)
                if val and isinstance(val, str):
                    try:
                        task[field] = json.loads(val)
                    except (json.JSONDecodeError, TypeError):
                        pass
            if status_filter is None or task.get("status") == status_filter:
                tasks.append(task)
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return tasks[:limit]


async def cancel_task(task_id: str) -> bool:
    r = await get_redis()
    task = await r.hgetall(f"{TASK_PREFIX}{task_id}")
    if not task:
        return False
    status = task.get("status", "")
    if status in ("completed", "failed"):
        return False
    await r.hset(f"{TASK_PREFIX}{task_id}", mapping={"status": "cancelled", "completed_at": _now_iso()})
    await r.lrem(QUEUE_KEY, 0, task_id)
    return True


async def queue_length() -> int:
    r = await get_redis()
    return await r.llen(QUEUE_KEY)
