"""
Strike Bot API Entry Point
"""
from fastapi import FastAPI, Request
from core_agent.routes import agent, betting, racing, config, monitoring
from core_agent.core.mcp_server import mcp
from core_agent.core.security import AuthMiddleware
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import json
import os
import logging
from core_agent.config.paths import MARKET_SNAPSHOT_PATH
from core_agent.core.strike_brain import brain
from core_agent.config.model_config import ModelConfig

logger = logging.getLogger("strike-api")

app = FastAPI(title="Strike Bot API")

app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173"],
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

    # Background keepalive — pings racing_qwen every 4min so it stays loaded
    async def keepalive_model():
        import httpx
        chat_url = ModelConfig.ollama_native_url("/api/chat")
        await asyncio.sleep(15)  # wait for Ollama to be ready
        while True:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    await client.post(chat_url, json={
                        "model": "racing_qwen",
                        "messages": [{"role": "user", "content": "ping"}],
                        "stream": False,
                        "options": {"num_predict": 1},
                    })
            except Exception:
                pass
            await asyncio.sleep(240)  # every 4 minutes

    async def ollama_startup_self_check():
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
        except Exception as exc:
            logger.warning("Ollama self-check failed: tags_url=%s error=%s", tags_url, exc)

    await ollama_startup_self_check()
    asyncio.create_task(keepalive_model())
    
    # Initialize the brain
    brain.initialize()
    
    print("\n" + "="*50)
    print("Strike Tips Bot Initialized")
    print("API Base: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("MCP Endpoint (SSE): http://localhost:8000/mcp")
    print("="*50 + "\n")

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
app.include_router(betting.router, prefix="/api/bets")
app.include_router(racing.router)
app.include_router(config.router)
# app.include_router(monitoring.router)
app.include_router(monitoring.router)

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
        "documentation": "Connect via SSE at http://localhost:8000/mcp/sse"
    }
