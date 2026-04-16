import logging
from ddgs import DDGS
from typing import List, Dict

logger = logging.getLogger("search-tool")

def search_racing_data(query: str, limit: int = 3) -> List[str]:
    """Perform a live search for racing information, results, or news."""
    try:
        logger.info(f"[SEARCH] Query: {query}")
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=limit))
            return [r.get("body", "") for r in results]
    except Exception as e:
        logger.error(f"[SEARCH] Failed: {e}")
        return []
