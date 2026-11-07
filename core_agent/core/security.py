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
    "/api/health",
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
    "/api/monitoring/snapshot-hash",
    "/api/monitoring/snapshot",
    "/v1/health",
    # OpenAI-compatible clients probe GET /v1/models before their first chat
    # call. It returns a static 6-line catalogue (no inference, no cost), and
    # Pages already lists it in openPaths — without this the probe 401s.
    "/v1/models",
    "/api/racing/exotics",
    "/api/news",
    "/api/news/images",
    "/api/telemetry",
    "/api/telegram/bot-name",
    "/api/telegram/link-code",
    "/api/telegram/link-status",
    "/api/telegram/unlink",
    "/api/telegram/test",
    "/api/league/board",
    "/api/league/formula",
    "/api/league/races",
    "/api/league/picks",
    "/api/league/me",
}


async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # League routes authenticate themselves with the punter's Supabase JWT
    # (see routes/league.py). They must reach the app without the machine API
    # key, otherwise a signed-in browser can never pick or set an avatar.
    if (
        path in SAFE_PATHS
        or path.startswith("/mcp")
        or path.startswith("/api/league/tipster/")
        or path.startswith("/api/league/me")
    ):
        return await call_next(request)

    # Fail-closed: everything outside SAFE_PATHS needs the key — /api/*,
    # /v1/* (LLM inference = attacker-funded compute), and /ws/chat.
    # (Sep-2026 audit: open /v1/chat was unlimited free inference.)
    if path.startswith("/api/") or path.startswith("/v1/") or path == "/ws/chat":
        if request.scope.get("type") == "websocket":
            from starlette.websockets import WebSocket

            ws = WebSocket(request.scope, request.receive)
            key = request.query_params.get("api_key", "") or request.query_params.get("key", "")
            if not API_KEY or not key or key != API_KEY:
                await ws.close(code=4401)
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
            return await call_next(request)
        key = request.headers.get("X-API-KEY")
        if not key:
            auth = request.headers.get("Authorization", "")
            if auth.lower().startswith("bearer "):
                key = auth[7:].strip()
        if not API_KEY or not key or key != API_KEY:
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized: Invalid or missing API key"},
            )

    return await call_next(request)
