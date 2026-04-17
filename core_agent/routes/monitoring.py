"""
Strike Tips - Monitoring Routes
Endpoints for system health, performance, and monitoring.
"""
from fastapi import APIRouter, HTTPException, Request
import os
import json
import psutil
from datetime import datetime

router = APIRouter(prefix="/api", tags=["monitoring"])

@router.get("/monitoring/snapshot")
async def get_monitoring_snapshot(request: Request):
    """Get latest zero-hallucination snapshot from in-memory cache"""
    cache = request.app.state.snapshot_cache
    if not cache:
        cache = {"status": "no_snapshot_available"}
        
    # Return a copy so we don't mutate shared app state
    result = dict(cache)
    
    # Inject active intelligent alerts from the L7 Alert Engine
    alerts = []
    try:
        data_dir = os.environ.get("DATA_DIR", "data")
        alerts_path = os.path.join(data_dir, "alert_conditions.json")
        if os.path.exists(alerts_path):
            with open(alerts_path, "r") as f:
                alerts_data = json.load(f)
                # Handle both array and dict formats
                items = alerts_data if isinstance(alerts_data, list) else alerts_data.values()
                for v in items:
                    if isinstance(v, dict) and (v.get('active', False) or v.get('is_active', False) or v.get('condition_type') == 'value_bet'):
                        alerts.append(v)
    except Exception:
        pass
        
    result["alerts"] = alerts
    return result

@router.get("/system/health")
async def get_system_health():
    """L7 Diagnostics endpoint for the Next.js Frontend"""
    mem = psutil.virtual_memory()
    return {
        "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
        "memory_usage_percent": mem.percent,
        "available_memory_mb": round(mem.available / (1024 * 1024), 1),
        "status": "HEALTHY" if mem.percent < 90 and psutil.cpu_percent(interval=0.1) < 95 else "DEGRADED",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/monitoring/performance")
async def get_performance_summary():
    """Get AI performance metrics"""
    from performance_tracker import tracker
    return tracker.get_summary()

