"""
Strike Bot API Entry Point
"""

from fastapi import FastAPI, Request, WebSocket, Query
from fastapi.responses import RedirectResponse, JSONResponse
from core_agent.routes import (
    agent,
    betting,
    racing,
    config,
    monitoring,
    healing,
    dreaming,
    tasks,
    legal,
)
from core_agent.core.mcp_server import mcp
from core_agent.core.security import auth_middleware
from core_agent.core.volume_sync import sync_volume
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
import time
from core_agent.config.paths import DATA_DIR
from core_agent.core.strike_brain import brain
from core_agent.core.scheduler import StrikeTipsScheduler
from contextlib import asynccontextmanager
from core_agent.core.logging_setup import configure_logging

configure_logging()

logger = logging.getLogger("strike-api")


async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    # Opt into cross-origin embedding: the HUD (Vercel/Pages) fetches this
    # API directly under a COEP document, which requires CORP on responses.
    # Readability is still gated by CORS (allow_origins below).
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response


RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 30
RATE_LIMIT_MAX_KEYS = 10_000  # hard cap on tracked ip:path keys (memory guard)
_rate_store: dict = {}


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path

    if path in ("/", "/docs", "/openapi.json", "/telegram-webhook"):
        return await call_next(request)

    # Long-lived containers see a frozen volume view; pull the latest
    # committed state (throttled internally) so reads reflect other
    # containers' writes. Runs in a thread to avoid blocking the loop.
    try:
        await asyncio.to_thread(sync_volume)
    except Exception:
        pass

    client_ip = request.client.host if request.client else "unknown"
    key = f"{client_ip}:{path}"
    now = time.time()

    timestamps = _rate_store.get(key)
    if timestamps is None:
        # Evict expired/empty keys when the store grows unbounded
        if len(_rate_store) >= RATE_LIMIT_MAX_KEYS:
            stale = [k for k, v in _rate_store.items() if not v or now - v[-1] >= RATE_LIMIT_WINDOW]
            for k in stale:
                _rate_store.pop(k, None)
            while len(_rate_store) >= RATE_LIMIT_MAX_KEYS:
                _rate_store.pop(next(iter(_rate_store)))
        timestamps = _rate_store[key] = []

    timestamps[:] = [t for t in timestamps if now - t < RATE_LIMIT_WINDOW]

    if len(timestamps) >= RATE_LIMIT_MAX:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded. Try again later."})

    timestamps.append(now)
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from core_agent.core.log_setup import configure_file_logging
    configure_file_logging()

    from core_agent.core.snapshot_cache import get_snapshot, ensure_populated
    app.state.snapshot_cache = get_snapshot()
    try:
        await ensure_populated()
        app.state.snapshot_cache = get_snapshot()
    except Exception as e:
        logger.warning("Snapshot populate fallback failed: %s", e)

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

    # NOTE (Sep-2026 outage): the full monitor.run() loop (scrapes +
    # heartbeat dreams + swarm research) must NOT run inside web
    # containers — the 5-min run_odds_monitor cron already covers scraping,
    # and every web container duplicating it fork-bombed CPU/RAM, burned
    # Groq quota, got the egress IP rate-limited (ATR tiers all failing),
    # and starved the event loop until HTTP inputs hung and Modal reported
    # init timeouts. Web lifespan serves requests + scheduler only.
    monitor = None
    bg_task = None

    # Task worker needs Redis, which exists in local docker only — not on
    # Modal. Starting it here just error-spams every 2s forever, so only
    # start when a local Redis actually answers (Sep-2026 outage cleanup).
    def _redis_present() -> bool:
        try:
            import socket as _socket

            _s = _socket.create_connection(("localhost", 6379), timeout=2)
            _s.close()
            return True
        except Exception:
            return False

    async def start_task_worker():
        from core_agent.core.task_worker import run_worker_loop
        logger.info("Starting background task worker...")
        try:
            await run_worker_loop(poll_interval=2.0)
        except Exception as e:
            logger.warning("Task worker stopped: %s", e)

    if _redis_present():
        asyncio.create_task(start_task_worker())
    else:
        logger.info("Task worker skipped (no local Redis on this host)")

    async def refresh_snapshot():
        try:
            from core_agent.core.task_queue import get_redis
            redis_client = await get_redis()
            from core_agent.core.snapshot_cache import subscribe_snapshot, get_snapshot
            asyncio.create_task(subscribe_snapshot(redis_client))
            logger.info("Snapshot cache subscriber started")
        except Exception as e:
            logger.warning("Redis subscriber failed, using disk fallback: %s", e)

    # Snapshot subscriber needs Redis too — disk fallback otherwise.
    if _redis_present():
        asyncio.create_task(refresh_snapshot())
    else:
        logger.info("Snapshot subscriber skipped (no local Redis; disk fallback)")

    brain.initialize()

    # New bus-based chat architecture
    from core_agent.bus.queue import MessageBus
    from core_agent.agent.loop import AgentLoop

    bus = MessageBus()
    loop = AgentLoop(bus)

    async def processor(msg):
        await loop.process(msg)

    bus_task = asyncio.create_task(bus.worker_loop(processor))

    app.state.bus = bus
    app.state.bus_task = bus_task

    def start_scheduler():
        try:
            sched = StrikeTipsScheduler(data_dir=str(DATA_DIR))
            sched.scheduler.start()
            app.state.scheduler = sched
            job_count = len(sched.scheduler.get_jobs())
            logger.info("StrikeTipsScheduler started with %d jobs (APScheduler SAST)", job_count)
        except Exception as e:
            logger.warning("Scheduler startup failed: %s", e)

    start_scheduler()

    # ContextBuilder warmup burns LLM calls on every cold start for zero
    # request benefit — skip in web containers (Sep-2026 outage cleanup).

    try:
        from core_agent.channels.telegram import TelegramChannel
        tg_channel = TelegramChannel(bus)
        await tg_channel.start()
        logger.info("Telegram channel registered")
    except Exception as e:
        logger.warning("Telegram channel startup failed: %s", e)

    logger.info("Strike Tips Bot fully initialized")
    try:
        yield
    finally:
        if bg_task is not None:
            bg_task.cancel()
            try:
                await bg_task
            except asyncio.CancelledError:
                pass
        if hasattr(app.state, "bus_task"):
            app.state.bus_task.cancel()
            try:
                await app.state.bus_task
            except asyncio.CancelledError:
                pass
        if monitor is not None:
            await monitor.close()
            logger.info("AdaptiveOddsMonitor stopped")
        if tg_channel is not None:
            try:
                await tg_channel.stop()
                logger.info("Telegram channel stopped")
            except Exception:
                pass


app = FastAPI(title="Strike Bot API", lifespan=lifespan)

app.middleware("http")(auth_middleware)
app.middleware("http")(rate_limit_middleware)
app.middleware("http")(security_headers_middleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://strike-tips-hud.vercel.app",
        "https://strike-tips-hud.pages.dev",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "X-API-KEY", "X-Request-ID", "Authorization"],
)


try:
    if hasattr(mcp, "app"):
        app.mount("/mcp", mcp.app)
    elif hasattr(mcp, "_app"):
        app.mount("/mcp", mcp._app)
except Exception as e:
    print(f"[WARN] Could not mount MCP: {e}")

app.include_router(agent.router)
app.include_router(betting.router, prefix="/api/betting")
app.include_router(racing.router)
app.include_router(config.router)
app.include_router(monitoring.router)
app.include_router(healing.router)
app.include_router(dreaming.router)
app.include_router(tasks.router)
app.include_router(legal.router)

from core_agent.api_pkg.openai import handle_chat_completions, handle_models, handle_health
from core_agent.api_pkg.websocket import handle_websocket

@app.post("/v1/chat/completions")
async def v1_chat_completions(request: Request):
    return await handle_chat_completions(request)

@app.get("/v1/models")
async def v1_models(request: Request):
    return await handle_models(request)

@app.get("/v1/health")
async def v1_health(request: Request):
    return await handle_health(request)

@app.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket, session_id: str = Query(default="ws:default")):
    await handle_websocket(websocket, session_id)


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
    suffix = f"/{path}" if path else ""
    return RedirectResponse(url=f"/api/betting{suffix}", status_code=307)


@app.get("/")
async def root():
    return {"message": "Strike Bot API Online"}


@app.get("/agent/memory")
async def agent_memory_root(query: str = "betting preferences, favourite tracks, risk tolerance", user_id: str = ""):
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
    }
