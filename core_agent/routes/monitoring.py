"""
Strike Tips - Monitoring Routes
Endpoints for system health, performance, and monitoring.
"""
from fastapi import APIRouter, HTTPException, Request
import os
import json

router = APIRouter(prefix="/api", tags=["monitoring"])

@router.get("/monitoring/snapshot")
async def get_monitoring_snapshot(request: Request):
    """Get latest zero-hallucination snapshot from in-memory cache"""
    cache = request.app.state.snapshot_cache
    if not cache:
        return {"status": "no_snapshot_available"}
    return cache

@router.get("/monitoring/performance")
async def get_performance_summary():
    """Get AI performance metrics"""
    from performance_tracker import tracker
    return tracker.get_summary()
