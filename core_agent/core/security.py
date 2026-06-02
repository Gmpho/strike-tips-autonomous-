import os
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("STRIKE_TIPS_API_KEY")

SAFE_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/telegram-webhook",
    "/api/system/health",
}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in SAFE_PATHS or path.startswith("/mcp"):
            return await call_next(request)

        if path.startswith("/api/"):
            key = request.headers.get("X-API-KEY")
            if not key or key != API_KEY:
                raise HTTPException(
                    status_code=401, detail="Unauthorized: Invalid or missing API key"
                )
        return await call_next(request)
