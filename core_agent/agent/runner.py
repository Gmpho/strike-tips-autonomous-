from __future__ import annotations
from collections.abc import AsyncIterator
from core_agent.agent.providers.task_router import TaskRouter


class AgentRunner:
    def __init__(self, router: TaskRouter) -> None:
        self.router = router

    async def run_stream(self, messages: list[dict], intent: str | None) -> AsyncIterator[str]:
        async for chunk in self.router.stream(messages, None, intent):
            yield chunk

    async def run_complete(self, messages: list[dict], intent: str | None) -> str:
        chunks = []
        async for chunk in self.router.stream(messages, None, None):
            chunks.append(chunk)
        return "".join(chunks)
