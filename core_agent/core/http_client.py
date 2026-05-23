"""
Shared HTTPX clients — per-host connection pooling.
Avoids creating a new client on every request (TCP connection reuse).
"""

import logging
from typing import Dict, Optional

import httpx

logger = logging.getLogger("http-client")

_async_clients: Dict[str, httpx.AsyncClient] = {}
_sync_clients: Dict[str, httpx.Client] = {}

_ASYNC_LIMITS = httpx.Limits(max_keepalive_connections=20, max_connections=100)
_SYNC_LIMITS = httpx.Limits(max_keepalive_connections=10, max_connections=50)


def _host_key(base_url: str = "") -> str:
    return base_url or "__default__"


def get_async_client(base_url: str = "", timeout: float = 30.0, **kwargs) -> httpx.AsyncClient:
    key = _host_key(base_url)
    existing = _async_clients.get(key)
    if existing is not None and not existing.is_closed:
        return existing
    client = httpx.AsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        limits=_ASYNC_LIMITS,
        **kwargs,
    )
    _async_clients[key] = client
    return client


def get_sync_client(base_url: str = "", timeout: float = 30.0, **kwargs) -> httpx.Client:
    key = _host_key(base_url)
    existing = _sync_clients.get(key)
    if existing is not None and not existing.is_closed:
        return existing
    client = httpx.Client(
        base_url=base_url,
        timeout=httpx.Timeout(timeout),
        limits=_SYNC_LIMITS,
        **kwargs,
    )
    _sync_clients[key] = client
    return client


async def close_async():
    for key, client in list(_async_clients.items()):
        if not client.is_closed:
            await client.aclose()
        del _async_clients[key]


def close_sync():
    for key, client in list(_sync_clients.items()):
        if not client.is_closed:
            client.close()
        del _sync_clients[key]


async def close_all():
    await close_async()
    close_sync()
