"""
Strike Tips - Monitoring Routes
Endpoints for system health, performance, and monitoring.
"""

import asyncio
import hashlib
import json
import os
import subprocess
from datetime import datetime
from fastapi import Query
from fastapi.responses import Response
from core_agent.config.paths import DATA_DIR, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH, ATR_RESULTS_PATH, NEWS_PATH, NEWS_IMAGES_DIR, NEWS_PATH, NEWS_IMAGES_DIR

import logging
import psutil
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger("monitoring-routes")

router = APIRouter(prefix="/api", tags=["monitoring"])


@router.get("/monitoring/stream")
async def stream_snapshot(request: Request):
    """SSE endpoint — pushes snapshot + ATR updates the moment they change."""
    async def event_stream():
        last_hash = ""
        last_movers_hash = ""
        last_pred_hash = ""
        last_results_hash = ""
        last_news_hash = ""

        while True:
            try:
                if await request.is_disconnected():
                    break

                # Check snapshot for changes
                cache = request.app.state.snapshot_cache or {}
                current = dict(cache)
                current["snapshot_hash"] = hashlib.md5(
                    json.dumps(current, sort_keys=True).encode()
                ).hexdigest()

                if current["snapshot_hash"] != last_hash:
                    last_hash = current["snapshot_hash"]
                    current["alerts"] = _load_recent_alerts(20)
                    yield f"event: snapshot\ndata: {json.dumps(current)}\n\n"

                # Check ATR movers for changes
                if ATR_MOVERS_PATH.exists():
                    movers_data = json.loads(ATR_MOVERS_PATH.read_text())
                    m_hash = hashlib.md5(json.dumps(movers_data, sort_keys=True).encode()).hexdigest()
                    if m_hash != last_movers_hash:
                        last_movers_hash = m_hash
                        yield f"event: market-movers\ndata: {json.dumps(movers_data.get('movers', []))}\n\n"

                # Check ATR predictor for changes
                if ATR_PREDICTOR_PATH.exists():
                    pred_data = json.loads(ATR_PREDICTOR_PATH.read_text())
                    p_hash = hashlib.md5(json.dumps(pred_data, sort_keys=True).encode()).hexdigest()
                    if p_hash != last_pred_hash:
                        last_pred_hash = p_hash
                        yield f"event: predictor\ndata: {json.dumps(pred_data.get('predictions', []))}\n\n"

                # Check ATR results for changes
                if ATR_RESULTS_PATH.exists():
                    res_data = json.loads(ATR_RESULTS_PATH.read_text())
                    r_hash = hashlib.md5(json.dumps(res_data, sort_keys=True).encode()).hexdigest()
                    if r_hash != last_results_hash:
                        last_results_hash = r_hash
                        yield f"event: results\ndata: {json.dumps(res_data.get('results', []))}\n\n"

                # Check news for changes
                if NEWS_PATH.exists():
                    news_data = json.loads(NEWS_PATH.read_text())
                    n_hash = hashlib.md5(json.dumps(news_data, sort_keys=True).encode()).hexdigest()
                    if n_hash != last_news_hash:
                        last_news_hash = n_hash
                        yield f"event: news\ndata: {json.dumps(news_data)}\n\n"

                await asyncio.sleep(2)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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


@router.get("/news")
async def get_news():
    """Latest horse-racing news from free RSS feeds (BBC/Guardian/Mirror)."""
    if not NEWS_PATH.exists():
        return {"items": [], "count": 0}
    try:
        with open(NEWS_PATH) as f:
            items = json.load(f)
        return {"items": items, "count": len(items)}
    except Exception as e:
        logger.warning(f"News read failed: {e}")
        return {"items": [], "count": 0, "error": str(e)}


@router.get("/news/images")
async def proxy_news_image(url: str = Query(...)):
    """Lazy image proxy — fetch on first view, cache to disk, serve with long TTL."""
    import hashlib
    from core_agent.core.http_client import get_async_client

    # Validate URL: must be from our known feed CDNs
    allowed_hosts = (
        "ichef.bbci.co.uk",
        "i.guim.co.uk",
        "i2-prod.mirror.co.uk",
        "i.dailymail.co.uk",
    )
    if not any(h in url for h in allowed_hosts):
        return Response(status_code=400, content="Disallowed image source")

    cache_key = hashlib.sha256(url.encode()).hexdigest()[:24] + ".jpg"
    cache_path = NEWS_IMAGES_DIR / cache_key

    # Serve cached if fresh (7 days)
    if cache_path.exists() and (os.path.getmtime(cache_path) > (datetime.now().timestamp() - 7 * 86400)):
        with open(cache_path, "rb") as f:
            return Response(content=f.read(), media_type="image/jpeg", headers={
                "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
            })

    # Fetch fresh
    try:
        client = get_async_client(timeout=15.0)
        resp = await client.get(url, headers={"User-Agent": "StrikeTips/1.0 (+news image proxy)"})
        if resp.status_code != 200:
            return Response(status_code=404, content="Image not found")
        content = resp.content
        # Cache
        try:
            with open(cache_path, "wb") as f:
                f.write(content)
        except Exception:
            pass
        return Response(content=content, media_type="image/jpeg", headers={
            "Cache-Control": "public, max-age=86400, stale-while-revalidate=604800",
        })
    except Exception as e:
        logger.warning(f"Image proxy failed for {url}: {e}")
        return Response(status_code=502, content="Image fetch failed")
