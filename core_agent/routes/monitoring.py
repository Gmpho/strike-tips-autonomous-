"""
Strike Tips - Monitoring Routes
Endpoints for system health, performance, and monitoring.
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime
from core_agent.config.paths import DATA_DIR

import logging
import psutil
from fastapi import APIRouter, Request

logger = logging.getLogger("monitoring-routes")

router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/monitoring/snapshot")
async def get_monitoring_snapshot(request: Request):
    """Get latest zero-hallucination snapshot from in-memory cache with hash for differential sync"""
    cache = request.app.state.snapshot_cache
    if not cache:
        cache = {"status": "no_snapshot_available"}

    # Return a copy so we don't mutate shared app state
    result = dict(cache)

    # Calculate hash for frontend differential sync
    result["snapshot_hash"] = hashlib.md5(
        json.dumps(result, sort_keys=True).encode()
    ).hexdigest()

    # Inject recently triggered alerts from the AlertEngine's history log
    result["alerts"] = _load_recent_alerts(20)
    return result


def _load_recent_alerts(limit: int = 20) -> list:
    """Load last N triggered alerts from alert_history.json (JSONL)."""
    alerts = []
    try:
        hist_path = str(DATA_DIR / "alert_history.json")
        if os.path.exists(hist_path):
            with open(hist_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            alerts.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
            return alerts[-limit:]
    except Exception:
        pass
    return alerts


@router.get("/system/health")
async def get_system_health():
    """L7 Diagnostics endpoint for the Next.js Frontend"""
    mem = psutil.virtual_memory()
    return {
        "cpu_usage_percent": psutil.cpu_percent(interval=0.1),
        "memory_usage_percent": mem.percent,
        "available_memory_mb": round(mem.available / (1024 * 1024), 1),
        "status": (
            "HEALTHY"
            if mem.percent < 90 and psutil.cpu_percent(interval=0.1) < 95
            else "DEGRADED"
        ),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/monitoring/performance")
async def get_performance_summary():
    """Get AI performance metrics"""
    from core_agent.core.performance_tracker import tracker

    return tracker.get_summary()


@router.get("/logs")
async def get_logs(tail: int = 50):
    """Get last N log lines from monitor.log"""
    log_lines = []
    try:
        # Try multiple log locations
        log_paths = [
            str(DATA_DIR / "strike.log"),
            "monitor.log",
            "ollama.log",
        ]

        for log_path in log_paths:
            if os.path.exists(log_path):
                with open(log_path, "r") as f:
                    lines = f.readlines()
                    log_lines = [line.strip() for line in lines[-tail:] if line.strip()]
                break

        if not log_lines:
            return {"logs": [], "count": 0, "source": "no_log_file"}
    except Exception as e:
        return {"logs": [], "count": 0, "error": str(e)}

    return {
        "logs": log_lines,
        "count": len(log_lines),
        "source": log_path if log_lines else "none",
    }


@router.get("/system/vitals")
async def get_intelligence_vitals():
    """Get real-time AI performance and host statistics (Intelligence Pulse)"""
    from core_agent.core.performance_tracker import tracker

    ai_metrics = tracker.get_summary()
    mem = psutil.virtual_memory()

    vitals = []
    # Convert AI metrics to the 'vitals' format for the frontend
    for model_name, metrics in ai_metrics.items():
        vitals.append(
            {
                "id": f"ai-{model_name}",
                "name": model_name.upper(),
                "cpu": metrics["success_rate"],  # Success rate as progress
                "mem": "100%",  # Active status
                "mem_usage": f"Latency: {metrics['avg_latency']} | {metrics['requests']} reqs",
            }
        )

    # Always include the host bot process
    vitals.append(
        {
            "id": "host-bot",
            "name": "STRIKE-BOT (ORCHESTRATOR)",
            "cpu": f"{psutil.cpu_percent()}%",
            "mem": f"{mem.percent}%",
            "mem_usage": f"{round(mem.used/(1024**3), 1)}GB / {round(mem.total/(1024**3), 1)}GB",
        }
    )

    return {"success": True, "vitals": vitals, "timestamp": datetime.now().isoformat()}
