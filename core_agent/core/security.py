import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("STRIKE_TIPS_API_KEY")


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks, docs, root, MCP, and dashboard API routes without key
        path = request.url.path
        if (
            path in ["/", "/docs", "/openapi.json"]
            or path.startswith("/mcp")
            or path.startswith("/api/")
        ):
            return await call_next(request)

        key = request.headers.get("X-API-KEY")
        if not key or key != API_KEY:
            raise HTTPException(
                status_code=401, detail="Unauthorized: Invalid or missing API key"
            )
        return await call_next(request)
