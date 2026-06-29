from __future__ import annotations
from collections.abc import AsyncIterator
from core_agent.agent.providers.task_router import TaskRouter


class AgentRunner:
    def __init__(self, router: TaskRouter) -> None:
        self.router = router

    async def run_stream(self, messages: list[dict], intent: str | None, model_override: str | None = None) -> AsyncIterator[str]:
        async for chunk in self.router.stream(messages, None, intent, model_override=model_override):
            yield chunk

    async def run_complete(self, messages: list[dict], intent: str | None, model_override: str | None = None) -> str:
        chunks = []
        async for chunk in self.router.stream(messages, None, None, model_override=model_override):
            chunks.append(chunk)
        return "".join(chunks)
