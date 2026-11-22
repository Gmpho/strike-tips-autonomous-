"""Cloudflare KV access from Modal, over the REST API.

Modal cannot call ``*.workers.dev`` reliably: Cloudflare refuses those requests
from some Modal colos (403 "Attention Required! | Cloudflare" — BOM/SIN, while
AMS answers 200). ``api.cloudflare.com`` is a different hostname and is reachable
from Modal (verified 2026-11-22), so KV is read and written through the REST API
instead of through the Worker.

The Worker's cron fetches Betway and parks raw GetEvent payloads in KV; this
module is how the Python monitor gets at them.
"""

from __future__ import annotations

import logging
import json
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

API_ROOT = "https://api.cloudflare.com/client/v4"
# The ODDS_KV namespace from cloudflare_mcp_edge/wrangler.jsonc.
DEFAULT_NAMESPACE_ID = "3e60752804c4489c9542a6e211ea549d"
_TIMEOUT_SECS = 20.0

# Where Modal parks the last batch it fetched successfully. The Worker cron
# writes `betway:raw:slot:*`; Modal writes these. Both are read back, so a
# cycle landing in a blocked colo can still publish a real (slightly older)
# card instead of going blank.
MODAL_RAW_PREFIX = "betway:raw:modal:"
MODAL_SLOT_SIZE = 15
MODAL_TTL_SECS = 3 * 3600


def _account_id() -> str:
    return (
        os.environ.get("EDGE_KV_ACCOUNT_ID", "")
        or os.environ.get("CF_ACCOUNT_ID", "")
    ).strip()


def _namespace_id() -> str:
    return (os.environ.get("CF_KV_NAMESPACE_ID", "").strip() or DEFAULT_NAMESPACE_ID)


def _token() -> str:
    return (
        os.environ.get("EDGE_KV_API_TOKEN", "")
        or os.environ.get("CF_API_TOKEN", "")
        or os.environ.get("CLOUDFLARE_API_TOKEN", "")
    ).strip()


def configured() -> bool:
    """True when the REST credentials needed for KV access are present."""
    return bool(_account_id() and _token())


def _value_url(key: str) -> str:
    return (
        f"{API_ROOT}/accounts/{_account_id()}/storage/kv/namespaces/"
        f"{_namespace_id()}/values/{key}"
    )


async def kv_get_json(key: str) -> Optional[Dict[str, Any]]:
    """Read one KV value as JSON. None when missing, unauthorized or corrupt."""
    if not configured():
        return None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            resp = await client.get(
                _value_url(key),
                headers={"Authorization": f"Bearer {_token()}"},
            )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            logger.debug("KV GET %s -> HTTP %s: %.160s", key, resp.status_code, resp.text)
            return None
        return resp.json()
    except Exception as exc:  # pragma: no cover - network variance
        logger.debug("KV GET %s failed: %s", key, exc)
        return None


async def put_details(details: list, now_iso: str | None = None) -> int:
    """Park fetched race payloads in KV, chunked under the 25 MB value cap.

    Returns the number of slots written. Old slots beyond this batch are left
    alone rather than deleted: a shorter recent batch must not erase still
    useful races, and the 3h TTL cleans everything up on its own.
    """
    if not configured() or not details:
        return 0
    from datetime import datetime, timezone

    ts = now_iso or datetime.now(timezone.utc).isoformat()
    try:
        moment = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        moment = datetime.now(timezone.utc)
    # Free-tier KV allows 1,000 writes/day. At one cycle per 5 min, three
    # slots per cycle is 864 writes — just under the cap. Rotate the base so
    # successive cycles cover different races instead of overwriting slots 0-2.
    base = (moment.minute // 5) % 16
    max_slots = 3
    written = 0
    for start in range(0, len(details), MODAL_SLOT_SIZE):
        if written >= max_slots:
            break
        chunk = details[start : start + MODAL_SLOT_SIZE]
        slot = (base + start // MODAL_SLOT_SIZE) % 16
        payload = {
            "ts": ts,
            "events": {
                str(d.get("eventId") or index): {
                    "payload": d,
                    "region": d.get("regionName") or "Unknown",
                    "league": d.get("leagueName") or "Unknown",
                }
                for index, d in enumerate(chunk)
            },
        }
        if await kv_put_json(f"{MODAL_RAW_PREFIX}{slot}", payload, ttl_secs=MODAL_TTL_SECS):
            written += 1
    return written


async def kv_put_json(key: str, value: Any, ttl_secs: Optional[int] = None) -> bool:
    """Write one KV value as JSON. False when it did not land."""
    if not configured():
        return False
    params: Dict[str, Any] = {}
    if ttl_secs:
        params["expiration_ttl"] = int(ttl_secs)
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECS) as client:
            resp = await client.put(
                _value_url(key),
                params=params,
                headers={
                    "Authorization": f"Bearer {_token()}",
                    "Content-Type": "application/json",
                },
                content=json.dumps(value, default=str).encode("utf-8"),
            )
        if resp.status_code != 200:
            logger.debug("KV PUT %s -> HTTP %s: %.160s", key, resp.status_code, resp.text)
            return False
        return True
    except Exception as exc:  # pragma: no cover - network variance
        logger.debug("KV PUT %s failed: %s", key, exc)
        return False
