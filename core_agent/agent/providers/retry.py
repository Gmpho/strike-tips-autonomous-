"""HTTP retry with exponential backoff for 429 rate limits."""

import asyncio
import logging

logger = logging.getLogger("provider-retry")


async def retry_on_429(coro_factory, max_retries: int = 3, base_delay: float = 2.0):
    """Call coro_factory() and retry on HTTP 429 with exponential backoff.

    coro_factory must be a callable that returns an awaitable httpx response.
    """
    for attempt in range(max_retries + 1):
        resp = await coro_factory()
        if resp.status_code != 429:
            return resp
        if attempt < max_retries:
            delay = base_delay * (2 ** attempt)
            logger.warning("HTTP 429 rate limited, retrying in %.1fs (attempt %d/%d)", delay, attempt + 1, max_retries)
            await asyncio.sleep(delay)
        else:
            logger.error("HTTP 429 rate limited — exhausted %d retries", max_retries)
            resp.raise_for_status()
    return resp
