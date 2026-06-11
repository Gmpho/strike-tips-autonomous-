from __future__ import annotations
from collections.abc import AsyncIterator
from core_agent.agent.providers.router import ProviderRouter


class AgentRunner:
    def __init__(self, provider_router: ProviderRouter) -> None:
        self.provider_router = provider_router

    async def run_stream(self, messages: list[dict], intent: str | None) -> AsyncIterator[str]:
        async for chunk in self.provider_router.stream(messages, None, intent):
            yield chunk

    async def run_complete(self, messages: list[dict], intent: str | None) -> str:
        chunks = []
        async for chunk in self.provider_router.stream(messages, None, None):
            chunks.append(chunk)
        return "".join(chunks)
