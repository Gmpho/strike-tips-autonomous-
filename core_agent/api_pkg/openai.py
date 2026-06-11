from __future__ import annotations
from fastapi import Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import asyncio
import uuid
import json
from core_agent.bus.events import InboundMessage


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

    stream = body.get("stream", False)
    session_id = body.get("session_id", "api:default")
    bus = request.app.state.bus

    msg = InboundMessage(
        session_key=f"api:{session_id}",
        channel="rest",
        chat_id=session_id,
        content=last_user["content"],
    )

    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    if stream:
        return StreamingResponse(
            _stream_generator(bus, msg, chunk_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    sub = bus.subscribe()
    try:
        await bus.publish(msg)
        while True:
            out = await sub.get()
            if out.done:
                break
        content = out.content
    finally:
        bus.unsubscribe(sub)

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
