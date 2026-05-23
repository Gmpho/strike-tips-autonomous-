import logging
from typing import List

from core_agent.tools.maf_tool_registry import search_racing_data as _maf_search

logger = logging.getLogger("search-tool")


def search_racing_data(query: str, limit: int = 3) -> List[str]:
    """Thin wrapper — delegates to maf_tool_registry, returns snippet texts only."""
    result = _maf_search(query=query, limit=limit)
    return [r.get("snippet", "") for r in result.get("results", [])]
