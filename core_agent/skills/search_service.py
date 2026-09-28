"""
Fast search — Tavily/Exa API keys first (free tiers), DDGS + httpx fetch
as the free fallback. No duplicate of Betway/Schedule (already in context).
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from typing import Dict, List

from core_agent.core.http_client import get_async_client

logger = logging.getLogger("search-service")
# Suppress noisy ddgs engine-level timeouts (shown at INFO by library)
logging.getLogger("ddgs.ddgs").setLevel(logging.WARNING)

_BLOCKED = (
    "youtube.com", "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "pinterest.com", "linkedin.com",
    "doubleclick.net", "googleadservices.com", "googlesyndication.com",
    "consent.yahoo.com", "consent.google.com", "cookiebot.com",
    "onetrust.com", "cookielaw.org", "trustarc.com",
)


def _blocked(url: str) -> bool:
    return any(d in url.lower() for d in _BLOCKED)


def _clean(text: str, max_chars: int = 1500) -> str:
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'&[a-z]+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 30]
    cleaned = '\n'.join(lines)
    if not cleaned:
        return ""
    return (cleaned[:max_chars] + "...") if len(cleaned) > max_chars else cleaned


async def _fetch(url: str, timeout: int = 5) -> str:
    try:
        client = get_async_client(timeout=timeout)
        r = await client.get(url, headers={"Accept": "text/html,application/xhtml+xml"})
        if r.status_code == 200 and len(r.text) > 100:
            return _clean(r.text)
    except Exception:
        pass
    return ""


# Free-tier monthly budgets (Tavily 1000, Exa ~1400). Tracked in a JSON
# sidecar so every process shares the count; exhausted providers are
# skipped, never billed. Sep-2026: Brave needed money, so these two
# free tiers carry agent search.
_SEARCH_BUDGETS = {"tavily": 1000, "exa": 1400}


def _budget_path() -> str:
    try:
        from core_agent.config.paths import DATA_DIR
        return str(DATA_DIR / "search_budget.json")
    except Exception:
        return "/tmp/opencode-search-budget.json"


def _budget_used() -> Dict[str, int]:
    try:
        with open(_budget_path()) as f:
            data = json.load(f)
        if isinstance(data, dict) and data.get("month") == datetime.now(timezone.utc).strftime("%Y-%m"):
            return {k: int(v) for k, v in (data.get("used") or {}).items()}
    except Exception:
        pass
    return {}


def _budget_spend(provider: str) -> None:
    try:
        used = _budget_used()
        used[provider] = used.get(provider, 0) + 1
        with open(_budget_path(), "w") as f:
            json.dump({"month": datetime.now(timezone.utc).strftime("%Y-%m"), "used": used}, f)
    except Exception:
        pass  # budget tracking is best-effort; never block search


async def _tavily_search(query: str, limit: int) -> List[Dict]:
    """Direct answers + clean text. Returns [] on any failure/no-budget."""
    key = os.environ.get("TAVILY_API_KEY", "")
    if not key or _budget_used().get("tavily", 0) >= _SEARCH_BUDGETS["tavily"]:
        return []
    try:
        client = get_async_client(timeout=15)
        r = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": key, "query": query, "max_results": limit, "include_answer": False},
        )
        if r.status_code != 200:
            return []
        out = [
            {"title": h.get("title", ""), "snippet": (h.get("content", "") or "")[:500], "url": h.get("url", "")}
            for h in (r.json().get("results") or [])[:limit]
            if h.get("url") and not _blocked(h.get("url", ""))
        ]
        if out:
            _budget_spend("tavily")
        return out
    except Exception as e:
        logger.debug(f"[SEARCH] Tavily failed: {e}")
        return []


async def _exa_search(query: str, limit: int) -> List[Dict]:
    """Semantic search (patterns, profiles, PDF sheets). [] on failure."""
    key = os.environ.get("EXA_API_KEY", "")
    if not key or _budget_used().get("exa", 0) >= _SEARCH_BUDGETS["exa"]:
        return []
    try:
        client = get_async_client(timeout=15)
        r = await client.post(
            "https://api.exa.ai/search",
            headers={"Content-Type": "application/json", "x-api-key": key},
            json={"query": query, "numResults": limit},
        )
        if r.status_code != 200:
            return []
        out = [
            {"title": h.get("title", ""), "snippet": (h.get("text", "") or "")[:500], "url": h.get("url", "")}
            for h in (r.json().get("results") or [])[:limit]
            if h.get("url") and not _blocked(h.get("url", ""))
        ]
        if out:
            _budget_spend("exa")
        return out
    except Exception as e:
        logger.debug(f"[SEARCH] Exa failed: {e}")
        return []


async def search_racing(query: str, limit: int = 5) -> Dict:
    """
    Fast web search for racing info. Betway+Schedule already in system prompt.
    Cascade: Tavily (direct answers) -> Exa (semantic) -> DDGS + page fetch.
    """
    results: List[Dict] = []
    seen: set = set()
    provider = "none"

    # 1. Tavily — best quality, no scraping needed.
    tavily_items = await _tavily_search(query, limit)
    for item in tavily_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            results.append(item)
    if results:
        provider = "tavily"
        logger.info(f"[SEARCH] Tavily: {len(results)} results")
        return {"results": results, "provider": provider}

    # 2. Exa — semantic fallback.
    exa_items = await _exa_search(query, limit)
    for item in exa_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            results.append(item)
    if results:
        provider = "exa"
        logger.info(f"[SEARCH] Exa: {len(results)} results")
        return {"results": results, "provider": provider}
    ddgs_items = []
    
    def _run_ddgs(q: str, lim: int) -> List[Dict]:
        try:
            from ddgs import DDGS
            with DDGS() as d:
                return list(d.text(q, max_results=lim))
        except Exception as err:
            logger.debug(f"[SEARCH] DDGS worker error: {err}")
            return []

    try:
        loop = asyncio.get_event_loop()
        raw_results = await asyncio.wait_for(
            loop.run_in_executor(None, _run_ddgs, query, limit * 2),
            timeout=20.0,
        )
        for r in raw_results:
            url = r.get("href", "") or r.get("url", "")
            if url and not _blocked(url) and url not in seen:
                seen.add(url)
                ddgs_items.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                })
        logger.info(f"[SEARCH] DDGS: {len(ddgs_items)} URLs")
        provider = "ddgs"
    except Exception as e:
        logger.debug(f"[SEARCH] DDGS wrapper: {e}")

    # 2. Fetch top 2 URLs for real content (concurrent)
    to_fetch = ddgs_items[:2]
    if to_fetch:
        texts = await asyncio.gather(*[_fetch(item["url"], timeout=3) for item in to_fetch])
        for item, text in zip(to_fetch, texts):
            if text:
                results.append({
                    "title": item["title"] or "",
                    "snippet": text[:1500],
                    "url": item["url"],
                })
                logger.info(f"[SEARCH] Fetched: {item['url'][:55]}")
            elif item.get("snippet"):
                results.append({
                    "title": item["title"] or "",
                    "snippet": item["snippet"][:500],
                    "url": item["url"],
                })

    # 3. Snippet fallback for remaining
    for item in ddgs_items:
        if len(results) >= limit:
            break
        url = item["url"]
        if any(r["url"] == url for r in results):
            continue
        results.append({
            "title": item["title"] or "",
            "snippet": item.get("snippet", "")[:500],
            "url": url,
        })

    # 4. SA-specific fallback — direct fetch to known SA racing sites
    _is_sa_query = any(kw in query.lower() for kw in ("south africa", "sa ", "sa racing", "tomorrow", "scottsville", "kenilworth", "fairview", "turffontein", "vaal", "greyville", "durbanville"))
    _has_sa_result = any("tab4racing" in r.get("url","") or "sahorseracing" in r.get("url","") or "topbets" in r.get("url","") or "raceform" in r.get("url","") or "goldcircle" in r.get("url","") or "bethq" in r.get("url","") for r in results)
    if not results and _is_sa_query:
        sa_urls = [
            "https://www.tab4racing.com/racecards",
            "https://www.tab4racing.com/results",
            "https://www.topbets.co.za/racing",
            "https://www.raceform.co.za/",
            "https://www.sahorseracing.com/race-meetings",
        ]
        texts = await asyncio.gather(*[_fetch(u, timeout=3) for u in sa_urls])
        for url, text in zip(sa_urls, texts):
            if text and url not in seen:
                seen.add(url)
                label = url.split("//")[1].split(".")[0]
                results.append({
                    "title": f"{label.title()} — SA Racing",
                    "snippet": text[:1500],
                    "url": url,
                })
                logger.info(f"[SEARCH] SA-fallback: {url} ({len(text)} chars)")

    if not results:
        logger.info(f"[SEARCH] Empty for '{query[:60]}' (no results published yet)")

    return {
        "query": query,
        "results": results[:limit],
        "count": len(results),
        "status": "success" if results else "no_data_found",
        "provider": provider,
    }
