"""
Task Routes — FastAPI endpoints for managing the async task queue.
Enqueue, check status, list, and cancel tasks.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core_agent.core import task_queue

logger = logging.getLogger("task-routes")

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class EnqueueRequest(BaseModel):
    type: str
    params: Optional[dict] = {}


class EnqueueResponse(BaseModel):
    task_id: str
    type: str
    status: str = "queued"


class TaskStatusResponse(BaseModel):
    task_id: str
    type: str
    status: str
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[object] = None
    error: Optional[str] = None


@router.post("/enqueue", response_model=EnqueueResponse)
async def enqueue_task(req: EnqueueRequest):
    task_id = await task_queue.enqueue(req.type, req.params)
    return EnqueueResponse(task_id=task_id, type=req.type)


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    task = await task_queue.get_status(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return TaskStatusResponse(
        task_id=task.get("task_id", task_id),
        type=task.get("type", "unknown"),
        status=task.get("status", "unknown"),
        created_at=task.get("created_at"),
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
        result=task.get("result"),
        error=task.get("error"),
    )


@router.get("/")
async def list_all_tasks(status: Optional[str] = None, limit: int = 50):
    tasks = await task_queue.list_tasks(status_filter=status, limit=limit)
    return {
        "count": len(tasks),
        "tasks": [
            {
                "task_id": t.get("task_id"),
                "type": t.get("type"),
                "status": t.get("status"),
                "created_at": t.get("created_at"),
                "started_at": t.get("started_at"),
                "completed_at": t.get("completed_at"),
            }
            for t in tasks
        ],
    }


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    cancelled = await task_queue.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found or already finished",
        )
    return {"status": "cancelled", "task_id": task_id}


@router.get("/queue/length")
async def queue_length():
    length = await task_queue.queue_length()
    return {"queue_length": length}
