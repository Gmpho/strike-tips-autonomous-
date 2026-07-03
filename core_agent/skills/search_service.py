"""
Fast search — DDGS + httpx fetch. No duplicate of Betway/Schedule (already in context).
"""

import asyncio
import logging
import re
from typing import Dict, List

from core_agent.core.http_client import get_async_client

logger = logging.getLogger("search-service")

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


async def search_racing(query: str, limit: int = 5) -> Dict:
    """
    Fast web search for racing info. Betway+Schedule already in system prompt.
    Just DDGS + httpx page fetch.
    """
    results: List[Dict] = []
    seen: set = set()
    provider = "none"

    # 1. DDGS → get URLs (try auto backend, not lite which was removed)
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
        raw_results = await loop.run_in_executor(None, _run_ddgs, query, limit * 2)
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
        logger.warning(f"[SEARCH] Empty for '{query[:60]}'")

    return {
        "query": query,
        "results": results[:limit],
        "count": len(results),
        "status": "success" if results else "no_data_found",
        "provider": provider,
    }
