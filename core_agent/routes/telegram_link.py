"""Telegram passcode-link endpoints (CryptoPulse-style, Oct-2026).

- POST /api/telegram/link-code   (auth: Supabase user JWT) -> {code}
- GET  /api/telegram/link-status (auth) -> {linked, username}
- POST /api/telegram/unlink      (auth) -> {ok}
- POST /api/telegram/test       (auth) -> {ok} sends a test ping to the chat

Auth model: HUD sends the user's Supabase access token as
`Authorization: Bearer <jwt>`. The service client verifies it
(`auth.get_user`) — never trust a client-supplied user_id.
Turnstile proof-of-browser runs client-side (ensureSession on 401),
same as /api/config.
"""
from __future__ import annotations

import logging
import os

import httpx
from fastapi import APIRouter, Header, HTTPException

logger = logging.getLogger("telegram-link")

router = APIRouter(prefix="/api/telegram", tags=["telegram-link"])


def _user_id_from_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Missing Authorization Bearer token")
    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise HTTPException(401, "Empty bearer token")
    try:
        from core_agent.db.client import get_service_client
        user_res = get_service_client().auth.get_user(token)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("link auth failed: %r", e)
        raise HTTPException(401, "Invalid session — sign in again")
    user = getattr(user_res, "user", None)
    if not user or not getattr(user, "id", None):
        raise HTTPException(401, "Invalid session — sign in again")
    return str(user.id)


def _repo():
    from core_agent.db.client import get_service_client
    from core_agent.db.repository import LedgerRepository
    return LedgerRepository(get_service_client())


@router.get("/bot-name")
async def bot_name():
    """Public: bot username for the t.me deep link (via getMe, never guessed)."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        raise HTTPException(503, "Telegram bot not configured")
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(f"https://api.telegram.org/bot{token}/getMe")
            data = r.json()
            username = (data.get("result") or {}).get("username")
            if not username:
                raise HTTPException(502, "Could not resolve bot username")
            return {"username": username}
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("getMe failed: %r", e)
        raise HTTPException(502, "Could not resolve bot username")


@router.post("/link-code")
async def link_code(authorization: str | None = Header(default=None)):
    """Mint a single-use ST-XXXXX code bound to the caller's account."""
    try:
        user_id = _user_id_from_token(authorization)
        repo = _repo()
        # One live code at a time: revoke stale PENDING rows first.
        try:
            repo._c.table("telegram_links").update({"status": "REVOKED"}) \
                .eq("user_id", user_id).eq("status", "PENDING").execute()
        except Exception as e:
            logger.debug("pending cleanup skipped: %r", e)
        code = repo.create_link_code(user_id)
        try:
            from core_agent.core.telemetry import emit
            emit("telegram-link", "🔗 Link code minted (15-min expiry)")
        except Exception:
            pass
        return {"code": code, "expires_in_minutes": 15}
    except HTTPException:
        raise
    except RuntimeError as e:
        # Supabase not configured (no env) — honest 503, not a 500.
        raise HTTPException(503, str(e))


@router.get("/link-status")
async def link_status(authorization: str | None = Header(default=None)):
    try:
        user_id = _user_id_from_token(authorization)
        st = _repo().link_status(user_id)
        if not st:
            return {"linked": False, "username": None}
        return {"linked": True, "username": st.get("telegram_username")}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.post("/unlink")
async def unlink(authorization: str | None = Header(default=None)):
    try:
        user_id = _user_id_from_token(authorization)
        n = _repo().revoke_link(user_id)
        return {"ok": True, "revoked": n}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(503, str(e))


@router.post("/test")
async def test_link(authorization: str | None = Header(default=None)):
    """Send a test ping to the caller's linked chat."""
    try:
        from core_agent.db.client import get_service_client
        user_id = _user_id_from_token(authorization)
        client = get_service_client()
        res = client.table("telegram_links").select("telegram_chat_id") \
            .eq("user_id", user_id).eq("status", "LINKED") \
            .order("linked_at", desc=True).limit(1).execute()
        rows = res.data or []
        if not rows or not rows[0].get("telegram_chat_id"):
            raise HTTPException(404, "No linked Telegram account")
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise HTTPException(503, "Telegram bot not configured")
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": rows[0]["telegram_chat_id"],
                      "text": "⚡ Strike Tips link test — you're connected. Alerts will land here."},
            )
            if r.status_code != 200:
                raise HTTPException(502, f"Telegram rejected the test ({r.status_code})")
        return {"ok": True}
    except HTTPException:
        raise
    except RuntimeError as e:
        raise HTTPException(503, str(e))
