from __future__ import annotations
import asyncio
from collections.abc import AsyncIterator
from core_agent.bus.events import InboundMessage, OutboundMessage


class MessageBus:
    def __init__(self) -> None:
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        self._subscribers: list[asyncio.Queue[OutboundMessage]] = []

    async def publish(self, msg: InboundMessage) -> None:
        await self.inbound.put(msg)

    def subscribe(self) -> asyncio.Queue[OutboundMessage]:
        q: asyncio.Queue[OutboundMessage] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[OutboundMessage]) -> None:
        if q in self._subscribers:
            self._subscribers.remove(q)

    async def _broadcast(self, msg: OutboundMessage) -> None:
        for q in self._subscribers:
            await q.put(msg)

    async def worker_loop(self, processor) -> None:
        while True:
            msg = await self.inbound.get()
            try:
                await processor(msg)
            except Exception as e:
                await self._broadcast(
                    OutboundMessage(
                        session_key=msg.session_key,
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=f"Error: {e}",
                        delta=True,
                        done=True,
                    )
                )
            finally:
                self.inbound.task_done()

    async def publish_outbound(self, msg: OutboundMessage) -> None:
        await self._broadcast(msg)