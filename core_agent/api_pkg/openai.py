from __future__ import annotations
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import re
import uuid
import json
import logging
from core_agent.bus.events import InboundMessage

logger = logging.getLogger("openai-handler")

# ── Fast-path for casual chat ──────────────────────────────────────────────────
# Detect greetings, thanks, goodbyes — skip bus/AgentLoop entirely.
_CASUAL_PATTERNS = re.compile(
    r"^(hey|hello|hi|howdy|sup|yo|good\s*(morning|afternoon|evening|day)|"
    r"thanks|thank\s*(?:you|s)|thx|ty|"
    r"ok(?:ay)?|k+|"
    r"yes|yeah|yep|sure|no|nope|nah|"
    r"(?:lol|lmao|nice|cool|great|awesome|perfect)"
    r"|what'?s\s*up|how'?s\s*it\s*going|how\s+(?:are|r)\s*(?:you|u)|"
    r"bye|goodbye|cya|see\s*(?:ya|you|later)|good\s*night)"
    r"[\s!?.]*$",
    re.IGNORECASE,
)


def _is_casual(text: str) -> bool:
    return bool(_CASUAL_PATTERNS.match(text.strip()))


def _casual_reply(text: str) -> str:
    t = text.strip().lower()
    bye_words = {"bye", "goodbye", "cya", "see ya", "see you", "see later", "goodnight", "good night"}
    thanks_words = {"thanks", "thank you", "thank u", "thanks!", "thank you!", "thx", "ty"}
    if any(w in t for w in bye_words):
        return "Goodbye! Come back anytime to check on your races."
    if any(w in t for w in thanks_words):
        return "You're welcome! Let me know if you need anything else — race analysis, odds, or account updates."
    return "Hey there! I'm Strike Tips. Ask me about today's races, odds, or your account."


async def handle_chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(400, "Invalid JSON")

    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "messages required")

    last_user = next((m for m in reversed(messages) if m.get("role") == "user"), None)
    if not last_user:
        raise HTTPException(400, "No user message")

    user_text = last_user["content"].strip()
    stream = body.get("stream", False)
    session_id = body.get("session_id", "api:default")
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    # ── FAST PATH ────────────────────────────────────────────────────────────
    # Greetings, thanks, goodbyes — respond instantly, skip bus/AgentLoop
    if _is_casual(user_text):
        reply = _casual_reply(user_text)
        logger.info("[FAST_PATH] casual chat: '%s' → '%s'", user_text[:20], reply[:30])
        if stream:
            async def _single_chunk():
                yield _sse_chunk(reply, "strike-tips", chunk_id)
                yield _sse_chunk("", "strike-tips", chunk_id, finish_reason="stop")
                yield b"data: [DONE]\n\n"
            return StreamingResponse(
                _single_chunk(),
                media_type="text/event-stream",
                headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
            )
        return JSONResponse({
            "id": chunk_id,
            "object": "chat.completion",
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
            "model": "strike-tips",
        })

    # ── NORMAL PATH: bus-based AgentLoop ─────────────────────────────────────
    bus = request.app.state.bus
    msg = InboundMessage(
        session_key=f"api:{session_id}",
        channel="rest",
        chat_id=session_id,
        content=user_text,
    )

    if stream:
        return StreamingResponse(
            _stream_generator(bus, msg, chunk_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    sub = bus.subscribe()
    try:
        await bus.publish(msg)
        content = ""
        while True:
            out = await sub.get()
            if out.content:
                content = out.content
            if out.done:
                break
    finally:
        bus.unsubscribe(sub)

    # ── SAFETY NET: never return empty ───────────────────────────────────────
    if not content:
        content = "I'm sorry, I couldn't process that request. Try asking about today's races, odds, or your account."

    return JSONResponse({
        "id": chunk_id,
        "object": "chat.completion",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "model": "strike-tips",
    })


async def _stream_generator(bus, msg: InboundMessage, chunk_id: str):
    sub = bus.subscribe()
    try:
        await bus.publish(msg)
        while True:
            out = await sub.get()
            if out.delta and out.content:
                yield _sse_chunk(out.content, "strike-tips", chunk_id)
            if out.done:
                break
        yield _sse_chunk("", "strike-tips", chunk_id, finish_reason="stop")
        yield b"data: [DONE]\n\n"
    finally:
        bus.unsubscribe(sub)


async def handle_models(request: Request):
    return JSONResponse({
        "object": "list",
        "data": [{
            "id": "strike-tips",
            "object": "model",
            "created": 0,
            "owned_by": "strike-tips",
        }],
    })


async def handle_health(request: Request):
    import httpx
    import os

    ollama_status = "offline"
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    try:
        async with httpx.AsyncClient(timeout=1.0) as client:
            resp = await client.get(f"{ollama_host}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                if models:
                    ollama_status = "connected"
                else:
                    ollama_status = "no_models"
    except Exception:
        pass

    return JSONResponse({
        "success": True,
        "orchestrator": "ready",
        "ollama": ollama_status,
        "note": "Orchestrator is ready regardless of Ollama status"
    })


def _sse_chunk(content: str, model: str, chunk_id: str, finish_reason: str | None = None) -> bytes:
    data = {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "choices": [{
            "index": 0,
            "delta": {"content": content} if content else {},
            "finish_reason": finish_reason,
        }],
    }
    return f"data: {json.dumps(data)}\n\n".encode()
