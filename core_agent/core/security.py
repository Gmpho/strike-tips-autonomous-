import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("STRIKE_TIPS_API_KEY")

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow health checks, docs, root, and MCP SSE handshake without key
        if request.url.path in ["/", "/docs", "/openapi.json"] or request.url.path.startswith("/mcp"):
            return await call_next(request)
            
        key = request.headers.get("X-API-KEY")
        if not key or key != API_KEY:
            raise HTTPException(status_code=401, detail="Unauthorized: Invalid or missing API key")
        return await call_next(request)
