from __future__ import annotations
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class LLMProvider(ABC):
    @abstractmethod
    async def stream(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> AsyncIterator[str]:
        yield ""

    @abstractmethod
    async def complete(self, messages: list[dict], tools: list[dict] | None, intent: str | None) -> str:
        raise NotImplementedError
