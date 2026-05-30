"""
Strike Bot API Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from core_agent.routes import (
    agent,
    betting,
    racing,
    config,
    monitoring,
    healing,
    dreaming,
    tasks,
)
from core_agent.core.mcp_server import mcp
from core_agent.core.security import AuthMiddleware
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
import random
import time
from threading import Thread
from core_agent.config.paths import MARKET_SNAPSHOT_PATH, DATA_DIR
from core_agent.core.strike_brain import brain
from core_agent.config.model_config import ModelConfig
from core_agent.core.scheduler import StrikeTipsScheduler
from contextlib import asynccontextmanager

logger = logging.getLogger("strike-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start background tasks on server startup, clean up on shutdown."""
    from core_agent.core.log_setup import configure_file_logging
    configure_file_logging()

    ollama_host = ModelConfig.ollama_host()
    logger.info("Ollama configured host: %s", ollama_host)

    # Initialize cache in app state from shared snapshot cache
    from core_agent.core.snapshot_cache import get_snapshot, ensure_populated
    app.state.snapshot_cache = get_snapshot()
    try:
        await ensure_populated()
        app.state.snapshot_cache = get_snapshot()
    except Exception as e:
        logger.warning("Snapshot populate fallback failed: %s", e)

    # Clear stale alert conditions that may have been superseded by code defaults
    try:
        import os as _os, json as _json
        from core_agent.config.paths import DATA_DIR as _DATA_DIR
        ac_path = _DATA_DIR / "alert_conditions.json"
        if ac_path.exists():
            with open(ac_path) as _f:
                _data = _json.load(_f)
            _before = len(_data)
            _data = [c for c in _data if c.get("condition_type") != "value_bet"]
            if len(_data) < _before:
                with open(ac_path, "w") as _f:
                    _json.dump(_data, _f, indent=4)
                logger.info(f"Purged {_before - len(_data)} stale value_bet alert conditions from disk")
    except Exception as e:
        logger.warning(f"Alert condition cleanup skipped: {e}")

    # Start AdaptiveOddsMonitor as background task
    from core_agent.core.adaptive_odds_monitor import AdaptiveOddsMonitor
    monitor = AdaptiveOddsMonitor()
    bg_task = asyncio.create_task(monitor.run())
    logger.info("AdaptiveOddsMonitor started as background task")

    # Background tasks from former on_event startup
    async def start_task_worker():
        from core_agent.core.task_worker import run_worker_loop
        logger.info("Starting background task worker...")
        try:
            await run_worker_loop(poll_interval=2.0)
        except Exception as e:
            logger.warning("Task worker stopped: %s", e)

    asyncio.create_task(start_task_worker())

    async def prewarm_pipeline():
        try:
            from core_agent.agents import pipeline
            logger.info("Agent pipeline pre-warmed")
        except Exception as e:
            logger.warning(f"Pipeline pre-warm failed: {e}")

    asyncio.create_task(prewarm_pipeline())

    async def refresh_snapshot():
        try:
            from core_agent.core.task_queue import get_redis
            redis_client = await get_redis()
            from core_agent.core.snapshot_cache import subscribe_snapshot, get_snapshot
            asyncio.create_task(subscribe_snapshot(redis_client))
            logger.info("Snapshot cache subscriber started")
        except Exception as e:
            logger.warning("Redis subscriber failed, using disk fallback: %s", e)

    asyncio.create_task(refresh_snapshot())

    # Ollama keepalive
    async def keepalive_model(ollama_ready: bool):
        import httpx

        model_name = "racing_qwen"
        chat_url = ModelConfig.ollama_native_url("/api/chat")
        ps_url = ModelConfig.ollama_native_url("/api/ps")
        warmup_timeout_sec = float(os.getenv("OLLAMA_KEEPALIVE_TIMEOUT_SEC", "45"))
        base_interval_sec = float(os.getenv("OLLAMA_KEEPALIVE_INTERVAL_SEC", "240"))
        jitter_sec = float(os.getenv("OLLAMA_KEEPALIVE_JITTER_SEC", "25"))

        async def _ollama_busy_or_loading(client: httpx.AsyncClient) -> bool:
            started = time.monotonic()
            try:
                response = await client.get(ps_url, timeout=8)
                elapsed = time.monotonic() - started
                if response.status_code != 200:
                    return False
                payload = response.json()
                models = payload.get("models", []) if isinstance(payload, dict) else []
                busy_markers = ("loading", "busy", "generating", "pulling")
                for model in models:
                    if not isinstance(model, dict):
                        continue
                    state_blob = " ".join(str(model.get(key, "")).lower() for key in ("status", "state"))
                    if any(marker in state_blob for marker in busy_markers):
                        return True
                return False
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                return False

        if not ollama_ready:
            logger.warning("keepalive_disabled model=%s reason=initial_self_check_failed", model_name)
            return

        await asyncio.sleep(15)
        while True:
            sleep_for = max(30.0, base_interval_sec + random.uniform(-jitter_sec, jitter_sec))
            try:
                from core_agent.core.http_client import get_async_client
                client = get_async_client(timeout=warmup_timeout_sec)
                if await _ollama_busy_or_loading(client):
                    await asyncio.sleep(sleep_for)
                    continue
                await client.post(chat_url, json={"model": model_name, "messages": [{"role": "user", "content": "ping"}], "stream": False, "options": {"num_predict": 1}})
            except (httpx.HTTPError, ValueError, TypeError):
                pass
            await asyncio.sleep(sleep_for)

    async def ollama_startup_self_check() -> bool:
        from core_agent.core.http_client import get_async_client
        tags_url = ModelConfig.ollama_native_url("/api/tags")
        try:
            client = get_async_client(timeout=6)
            response = await client.get(tags_url)
            logger.info("Ollama self-check: status=%s", response.status_code)
            return response.status_code == 200
        except Exception:
            return False

    ollama_ready = await ollama_startup_self_check()
    asyncio.create_task(keepalive_model(ollama_ready))

    brain.initialize()

    def start_scheduler():
        try:
            sched = StrikeTipsScheduler(data_dir=str(DATA_DIR))
            sched.running = True
            sched.setup_schedule()
            sched.scheduler_thread = Thread(target=sched.run_pending, daemon=True)
            sched.scheduler_thread.start()
            logger.info("StrikeTipsScheduler started")
        except Exception as e:
            logger.warning("Scheduler startup failed: %s", e)

    start_scheduler()

    logger.info("Strike Tips Bot fully initialized")
    try:
        yield
    finally:
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass
        await monitor.close()
        logger.info("AdaptiveOddsMonitor stopped")


app = FastAPI(title="Strike Bot API", lifespan=lifespan)

app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://strike-tips-hud.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount MCP
try:
    if hasattr(mcp, "app"):
        app.mount("/mcp", mcp.app)
    elif hasattr(mcp, "_app"):
        app.mount("/mcp", mcp._app)
except Exception as e:
    print(f"[WARN] Could not mount MCP: {e}")

# Register routes
app.include_router(agent.router)
app.include_router(betting.router, prefix="/api/betting")
app.include_router(racing.router)
app.include_router(config.router)
app.include_router(monitoring.router)
app.include_router(healing.router)
app.include_router(dreaming.router)
app.include_router(tasks.router)


@app.api_route(
    "/api/bets",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
@app.api_route(
    "/api/bets/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def redirect_legacy_bets_routes(path: str = ""):
    """Redirect legacy /api/bets routes to the canonical /api/betting prefix."""
    suffix = f"/{path}" if path else ""
    return RedirectResponse(url=f"/api/betting{suffix}", status_code=307)


@app.get("/")
async def root():
    return {"message": "Strike Bot API Online"}


@app.get("/agent/memory")
async def agent_memory_root(query: str = "betting preferences, favourite tracks, risk tolerance", user_id: str = ""):
    """Direct-access alias for /api/agent/memory (handles missing /api prefix)."""
    from fastapi.responses import RedirectResponse
    from urllib.parse import quote
    params = f"query={quote(query)}"
    if user_id:
        params += f"&user_id={quote(user_id)}"
    return RedirectResponse(url=f"/api/agent/memory?{params}")


@app.get("/mcp", include_in_schema=False)
@app.get("/mcp/", include_in_schema=False)
async def mcp_home():
    return {
        "message": "Strike Tips MCP Hub",
        "status": "ready",
        "protocol": "Model Context Protocol",
        "documentation": "Connect via SSE at http://localhost:8000/mcp/sse",
    }
