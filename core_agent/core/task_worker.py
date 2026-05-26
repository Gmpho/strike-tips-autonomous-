"""
Task Worker — Async background worker that polls Redis for pending tasks.
Runs as an asyncio background task inside the FastAPI app or standalone.
"""

import asyncio
import logging
import traceback
from datetime import date, datetime, timedelta
from typing import Any, Callable, Coroutine, Dict, Optional

from core_agent.config.paths import PDF_CACHE_DIR
from core_agent.config.settings import TRACKS

logger = logging.getLogger("task-worker")

HANDLERS: Dict[str, Callable[..., Coroutine[Any, Any, Any]]] = {}


def register_handler(task_type: str):
    def decorator(func):
        HANDLERS[task_type] = func
        return func
    return decorator


async def dispatch(task: Dict[str, Any]) -> Any:
    task_type = task.get("type", "")
    params = task.get("params", {}) or {}
    handler = HANDLERS.get(task_type)
    if handler is None:
        raise ValueError(f"No handler registered for task type: {task_type}")
    logger.info("Dispatching task type=%s params=%s", task_type, params)
    return await handler(**params)


async def _execute_and_report(task: Dict[str, Any]):
    from core_agent.core.task_queue import complete, fail

    task_id = task.get("task_id", "")
    try:
        result = await dispatch(task)
        await complete(task_id, result)
        logger.info("Task %s completed successfully", task_id)
    except Exception as e:
        tb = traceback.format_exc()
        logger.error("Task %s failed: %s\n%s", task_id, e, tb)
        await fail(task_id, f"{type(e).__name__}: {e}")


async def run_worker_loop(poll_interval: float = 2.0):
    from core_agent.core.task_queue import dequeue

    logger.info("Task worker loop started (poll_interval=%.1fs)", poll_interval)
    while True:
        try:
            task = await dequeue(timeout=int(poll_interval))
            if task is not None:
                await _execute_and_report(task)
        except asyncio.CancelledError:
            logger.info("Task worker loop cancelled")
            break
        except Exception as e:
            logger.error("Task worker loop error: %s", e)
            await asyncio.sleep(poll_interval)


# ─── Handlers ────────────────────────────────────────────────────────────────


@register_handler("daily_scan")
async def handle_daily_scan(region: Optional[str] = None):
    from core_agent.core.strike_tips import StrikeTips
    strike = StrikeTips()
    try:
        tracks = None
        if region:
            from core_agent.skills.race_schedule import RaceScheduleService
            service = RaceScheduleService()
            all_tracks = await service.get_todays_tracks()
            tracks = {k: v for k, v in all_tracks.items() if v.get("region") == region}
        result = await strike.run_daily_scan(tracks=tracks)
        return {"scanned_tracks": result.get("scanned_tracks", 0), "region": region or "all"}
    finally:
        await strike.close()


@register_handler("pdf_sync")
async def handle_pdf_sync(days_back: int = 3):
    import subprocess
    result = subprocess.run(
        ["python3", "core_agent/core/strike_tips.py", "sync_pdfs"],
        capture_output=True, text=True, timeout=300,
    )
    return {
        "returncode": result.returncode,
        "stdout": result.stdout[-500:],
        "stderr": result.stderr[-500:],
    }


@register_handler("pre_warm")
async def handle_pre_warm(region: Optional[str] = None):
    from core_agent.skills.race_schedule import RaceScheduleService
    service = RaceScheduleService()
    tracks = await service.get_tomorrows_tracks()
    target_tracks = [t for t in tracks.keys() if t in TRACKS]
    if region:
        target_tracks = [t for t in target_tracks if tracks[t].get("region") == region]
    print(f"[CACHE] Pre-warm skipped — Betway API needs no pre-cache. {len(target_tracks)} tracks identified for tomorrow.")
    return {"pre_warmed": 0, "reason": "Betway API — no pre-cache needed", "tracks": target_tracks}


@register_handler("scrape_track")
async def handle_scrape_track(track_name: str, date_str: Optional[str] = None):
    from core_agent.core.strike_tips import StrikeTips
    strike = StrikeTips()
    try:
        result = await strike.scrape_and_analyze_track(track_name, date_str=date_str)
        return {"track": track_name, "status": "success", "details": str(result)[:500]}
    finally:
        await strike.close()


@register_handler("heartbeat_insight")
async def handle_heartbeat_insight():
    from core_agent.core.heartbeat import HeartbeatEngine
    engine = HeartbeatEngine()
    try:
        insight = await engine.generate_insight()
        return {"insight": insight}
    finally:
        await engine.close()


@register_handler("odds_snapshot")
async def handle_odds_snapshot():
    from core_agent.core.strike_tips import StrikeTips
    strike = StrikeTips()
    try:
        snapshot = await strike.get_odds_snapshot()
        return {"snapshot_size": len(str(snapshot)) if snapshot else 0}
    finally:
        await strike.close()


@register_handler("race_analysis")
async def handle_race_analysis(track_name: str, race_number: int, date_str: Optional[str] = None):
    from core_agent.core.strike_tips import StrikeTips
    strike = StrikeTips()
    try:
        result = await strike.evaluate_race(track_name, race_number, date_str=date_str)
        return {"track": track_name, "race": race_number, "status": "success"}
    finally:
        await strike.close()


@register_handler("cleanup_cache")
async def handle_cleanup_cache(max_age_days: int = 7):
    import shutil
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cleaned = 0
    for entry in PDF_CACHE_DIR.iterdir():
        if entry.is_file():
            mtime = datetime.fromtimestamp(entry.stat().st_mtime)
            if mtime < cutoff:
                entry.unlink()
                cleaned += 1
    return {"cleaned_files": cleaned, "cache_dir": str(PDF_CACHE_DIR)}


# ─── Standalone entry point ──────────────────────────────────────────────────


async def run_worker_standalone(poll_interval: float = 2.0):
    logger.info("Starting standalone task worker...")
    try:
        await run_worker_loop(poll_interval)
    except KeyboardInterrupt:
        logger.info("Worker stopped by keyboard interrupt")
    finally:
        from core_agent.core.task_queue import close_redis
        await close_redis()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strike Tips Task Worker")
    parser.add_argument("--poll-interval", type=float, default=2.0, help="Poll interval in seconds")
    args = parser.parse_args()
    asyncio.run(run_worker_standalone(args.poll_interval))


if __name__ == "__main__":
    main()
