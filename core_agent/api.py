"""
Strike Bot API Entry Point
"""

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from core_agent.routes import agent, betting, racing, config, monitoring, healing
from core_agent.core.mcp_server import mcp
from core_agent.core.security import AuthMiddleware
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
import random
import time
from core_agent.config.paths import MARKET_SNAPSHOT_PATH
from core_agent.core.strike_brain import brain
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("strike-api")

app = FastAPI(title="Strike Bot API")

app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    ollama_host = ModelConfig.ollama_host()
    logger.info("Ollama configured host: %s", ollama_host)

    # Initialize cache in app state
    app.state.snapshot_cache = {}

    # Background task to poll disk snapshot
    async def refresh_snapshot():
        while True:
            try:
                if os.path.exists(MARKET_SNAPSHOT_PATH):
                    with open(MARKET_SNAPSHOT_PATH, "r") as f:
                        app.state.snapshot_cache = json.load(f)
            except Exception:
                pass
            await asyncio.sleep(5)

    asyncio.create_task(refresh_snapshot())

    # Background keepalive — pings racing_qwen periodically so it stays loaded
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
                    logger.warning(
                        "keepalive_ps_check_non_200 model=%s elapsed_sec=%.2f status_code=%s",
                        model_name,
                        elapsed,
                        response.status_code,
                    )
                    return False
                payload = response.json()
                models = payload.get("models", []) if isinstance(payload, dict) else []
                busy_markers = ("loading", "busy", "generating", "pulling")
                for model in models:
                    if not isinstance(model, dict):
                        continue
                    state_blob = " ".join(
                        str(model.get(key, "")).lower() for key in ("status", "state")
                    )
                    if any(marker in state_blob for marker in busy_markers):
                        return True
                return False
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                elapsed = time.monotonic() - started
                logger.warning(
                    "keepalive_ps_check_failed model=%s elapsed_sec=%.2f exception_class=%s error=%s",
                    model_name,
                    elapsed,
                    exc.__class__.__name__,
                    exc,
                )
                return False

        if not ollama_ready:
            logger.warning(
                "keepalive_disabled_not_ready model=%s elapsed_sec=0.00 reason=initial_self_check_failed",
                model_name,
            )
            return

        await asyncio.sleep(15)  # grace period after startup readiness check
        while True:
            sleep_for = max(
                30.0, base_interval_sec + random.uniform(-jitter_sec, jitter_sec)
            )
            started = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=warmup_timeout_sec) as client:
                    if await _ollama_busy_or_loading(client):
                        logger.info(
                            "keepalive_skipped_busy model=%s elapsed_sec=0.00",
                            model_name,
                        )
                        await asyncio.sleep(sleep_for)
                        continue
                    await client.post(
                        chat_url,
                        json={
                            "model": model_name,
                            "messages": [{"role": "user", "content": "ping"}],
                            "stream": False,
                            "options": {"num_predict": 1},
                        },
                    )
                    elapsed = time.monotonic() - started
                    logger.info(
                        "keepalive_ping_ok model=%s elapsed_sec=%.2f timeout_sec=%.2f",
                        model_name,
                        elapsed,
                        warmup_timeout_sec,
                    )
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                elapsed = time.monotonic() - started
                logger.warning(
                    "keepalive_ping_failed model=%s elapsed_sec=%.2f timeout_sec=%.2f exception_class=%s error=%s",
                    model_name,
                    elapsed,
                    warmup_timeout_sec,
                    exc.__class__.__name__,
                    exc,
                )
            await asyncio.sleep(sleep_for)

    async def ollama_startup_self_check() -> bool:
        import httpx

        tags_url = ModelConfig.ollama_native_url("/api/tags")
        try:
            async with httpx.AsyncClient(timeout=6) as client:
                response = await client.get(tags_url)
                model_count = "n/a"
                if response.status_code == 200:
                    try:
                        payload = response.json()
                        model_count = len(payload.get("models", []))
                    except Exception:
                        model_count = "unparseable-json"
                logger.info(
                    "Ollama self-check: status=%s tags_url=%s model_count=%s",
                    response.status_code,
                    tags_url,
                    model_count,
                )
                return response.status_code == 200
        except Exception as exc:
            logger.warning(
                "Ollama self-check failed: tags_url=%s error=%s", tags_url, exc
            )
        return False

    ollama_ready = await ollama_startup_self_check()
    asyncio.create_task(keepalive_model(ollama_ready))

    # Initialize the brain
    brain.initialize()

    print("\n" + "=" * 50)
    print("Strike Tips Bot Initialized")
    print("API Base: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("MCP Endpoint (SSE): http://localhost:8000/mcp")
    print("=" * 50 + "\n")


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


@app.get("/mcp", include_in_schema=False)
@app.get("/mcp/", include_in_schema=False)
async def mcp_home():
    return {
        "message": "Strike Tips MCP Hub",
        "status": "ready",
        "protocol": "Model Context Protocol",
        "documentation": "Connect via SSE at http://localhost:8000/mcp/sse",
    }
