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
from core_agent.config.paths import MARKET_SNAPSHOT_PATH
from core_agent.core.strike_brain import brain

app = FastAPI(title="Strike Bot API")

app.add_middleware(AuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE", "PATCH", "HEAD"],
    allow_headers=["*"],
)
    
@app.on_event("startup")
async def startup_event():
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
            await asyncio.sleep(5) # Refresh every 5s
            
    asyncio.create_task(refresh_snapshot())
    
    # Initialize the brain
    brain.initialize()

    # Proactively load all local racing models into memory
    async def warm_up():
        import httpx
        # Give the Ollama container time to actually start the API server
        await asyncio.sleep(15) 
        
        # List of models to pre-warm (local only, skip :cloud models)
        models = [
            "racing_llama", "ds_racing", "lfm_racing", "racing_qwen", "func_gemma"
        ]
        async with httpx.AsyncClient(timeout=600.0) as client:
            for model in models:
                try:
                    print(f"[WARMUP] Pre-loading {model}...")
                    await client.post("http://ollama:11434/api/generate", json={"model": model, "prompt": "warmup"})
                    await asyncio.sleep(5)  # Let the CPU recover between loads
                except Exception as e:
                    print(f"[WARMUP ERR] Could not pre-load {model}: {e}")

    asyncio.create_task(warm_up())
    
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
app.include_router(betting.router)
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
