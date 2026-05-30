import asyncio
import logging
from typing import Optional

from core_agent.agents.schemas import AgentReply

logger = logging.getLogger("base-provider")


class BaseProvider:
    """Base class for all LLM providers with built-in retry.

    Subclasses override _call() — the public chat() method handles retries.
    """

    MAX_RETRIES = 2
    RETRY_DELAY = 1.0

    async def chat(self, message: str, model: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
        last_error = None
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return await self._call(message, model=model, intent=intent)
            except Exception as e:
                last_error = e
                logger.warning("%s attempt %d/%d failed: %s",
                               self.__class__.__name__, attempt + 1, self.MAX_RETRIES + 1, e)
                if attempt < self.MAX_RETRIES:
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
        raise last_error  # type: ignore[union-attr]

    async def _call(self, message: str, model: Optional[str] = None, intent: Optional[str] = None) -> AgentReply:
        raise NotImplementedError
