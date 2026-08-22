import os
from fastapi import Request
from fastapi.responses import JSONResponse

API_KEY = os.getenv("STRIKE_TIPS_API_KEY")

SAFE_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/telegram-webhook",
    "/api/system/health",
    "/api/agent/chat",
    "/api/agent/chat/stream",
    "/api/agent/health",
    "/api/agent/tools",
    "/api/agent/models",
    "/api/agent/history",
    "/api/legal/privacy",
    "/api/legal/terms",
    "/api/legal/disclaimer",
    "/api/legal/how-to-bet",
    "/api/legal/faq",
    "/api/legal/betting-rules",
    "/api/legal/responsible",
    "/api/legal/",
    "/api/monitoring/stream",
    "/api/racing/exotics",
    "/api/news",
    "/api/news/images",
    "/api/telemetry",
}


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    if path in SAFE_PATHS or path.startswith("/mcp"):
        return await call_next(request)

    if path.startswith("/api/"):
        key = request.headers.get("X-API-KEY")
        if not key or key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Invalid or missing API key"},
            )

    return await call_next(request)
