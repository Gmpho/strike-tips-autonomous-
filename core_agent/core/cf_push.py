"""Cloudflare worker pushes (KV odds snapshot + D1 form insights).

Single-key design (2026-09-13 rotation): the worker's BACKEND_API_KEY and
Modal's STRIKE_TIPS_API_KEY hold the SAME value. CLOUDFLARE_API_KEY /
CLOUDFLARE_MCP_URL env vars still work as overrides, but the STRIKE key
and the hardcoded worker URL are the fallback so a two-key drift (Sep-2026:
stale CF key 401'd every push for hours) can never recur.

All helpers are best-effort and never raise — a failed push must not break
scans, settles, or monitor cycles.
"""

import logging
import os

logger = logging.getLogger("cf-push")

CF_WORKER_URL = "https://striketips-mcp.gmphorg379.workers.dev"


def _cf_config():
    """(worker_url, api_key) with single-key discipline.

    STRIKE_TIPS_API_KEY is canonical (rotation keeps it fresh everywhere);
    CLOUDFLARE_API_KEY is a legacy override and must equal it when set.
    STRIKE-first ordering guarantees a stale legacy var can never 401 all
    pushes again (Sep-2026: stale CF var bypassed the fallback for hours).
    """
    url = (os.environ.get("CLOUDFLARE_MCP_URL", "") or "").rstrip("/") or CF_WORKER_URL
    key = os.environ.get("STRIKE_TIPS_API_KEY", "") or os.environ.get("CLOUDFLARE_API_KEY", "")
    return url, key


async def _post(path: str, payload: dict) -> bool:
    url, key = _cf_config()
    if not key:
        logger.debug("Cloudflare push skipped (no API key configured)")
        return False
    try:
        import httpx

        async def _try(k: str):
            async with httpx.AsyncClient(timeout=10) as client:
                return await client.post(
                    f"{url}{path}",
                    headers={"x-api-key": k, "content-type": "application/json"},
                    json=payload,
                )

        resp = await _try(key)
        if resp.status_code == 401:
            # Secret shadowing (e.g. overlapping Modal secrets): retry once
            # with the alternate configured key before giving up.
            alt = os.environ.get("CLOUDFLARE_API_KEY", "")
            if alt and alt != key:
                logger.warning("Cloudflare push 401, retrying with alternate key")
                resp = await _try(alt)
        if resp.status_code not in (200, 201):
            logger.warning("Cloudflare push %s returned %d: %.100s", path, resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:
        logger.debug("Cloudflare push %s skipped: %s", path, exc)
        return False


async def push_snapshot(state: dict) -> bool:
    """Push the odds snapshot to KV (180-300s TTL server-side)."""
    if not isinstance(state, dict) or not state.get("events"):
        return False
    return await _post("/api/ingest-snapshot", state)


async def push_insight(
    doc_id: str,
    horse: str,
    content: str,
    insight_type: str = "form_insight",
    track: str = "",
    race_number=None,
    date: str = "",
    metadata: dict = None,
) -> bool:
    """Store one form-insight row in D1 (INSERT OR REPLACE on doc_id)."""
    if not doc_id or not horse or not content:
        return False
    return await _post("/api/ingest-insight", {
        "doc_id": str(doc_id)[:200],
        "horse": str(horse)[:200],
        "content": str(content)[:10000],
        "type": insight_type,
        "track": track or "",
        "race_number": race_number,
        "date": date or "",
        "metadata": metadata or {},
    })
