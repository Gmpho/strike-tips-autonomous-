from __future__ import annotations
from fastapi import WebSocket, WebSocketDisconnect, Query
import uuid
import json
import asyncio
from core_agent.bus.events import InboundMessage


async def handle_websocket(
    websocket: WebSocket,
    session_id: str = Query(default="ws:default")
):
    await websocket.accept()
    bus = websocket.app.state.bus
    sub = bus.subscribe()
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    async def send_outbound():
        try:
            while True:
                out = await sub.get()
                if out.channel == "ws" and out.chat_id == session_id:
                    data = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "choices": [{
                            "index": 0,
                            "delta": {"content": out.content} if out.delta else {"content": out.content},
                            "finish_reason": "stop" if out.done else None,
                        }],
                    }
                    await websocket.send_text(f"data: {json.dumps(data)}\n\n")
                    if out.done:
                        await websocket.send_text("data: [DONE]\n\n")
                        break
        except Exception:
            pass

    sender_task = asyncio.create_task(send_outbound())

    try:
        while True:
            msg = await websocket.receive_text()
            try:
                data = json.loads(msg)
                content = data.get("content") or data.get("message", "")
                if content:
                    await bus.publish(InboundMessage(
                        session_key=f"ws:{session_id}",
                        channel="ws",
                        chat_id=session_id,
                        content=content,
                    ))
            except Exception:
                pass
    except WebSocketDisconnect:
        pass
    finally:
        sender_task.cancel()
        bus.unsubscribe(sub)