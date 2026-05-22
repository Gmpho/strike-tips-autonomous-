import logging
from ddgs import DDGS
from typing import List

from core_agent.skills.memory.search_cache import get_cache, set_cache

logger = logging.getLogger("search-tool")


def search_racing_data(query: str, limit: int = 3) -> List[str]:
    cache_key = f"search_tool:{query}:{limit}"
    cached = get_cache(cache_key)
    if cached is not None:
        logger.info(f"[SEARCH] Cache hit: {query}")
        return cached

    try:
        logger.info(f"[SEARCH] Query: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit, backend="duckduckgo"))
            if not results:
                short_query = " ".join(query.split()[:5])
                logger.info(f"[SEARCH] Fallback: {short_query}")
                results = list(ddgs.text(short_query, max_results=limit, backend="duckduckgo"))

            result_texts = [r.get("body", "") for r in results]
            set_cache(cache_key, result_texts)
            return result_texts
    except Exception as e:
        logger.error(f"[SEARCH] Failed: {e}")
        return []
