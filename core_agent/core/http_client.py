"""Shared HTTP clients with an honest-client outbound policy.

Every request is paced per host and identifies as `strike-tips/1.0`. Browser
TLS impersonation is off by default — `SCRAPER_IMPERSONATE` re-enables it
explicitly and warns, because a browser fingerprint without a browser is
evasion rather than scraping. See `core_agent/config/compliance.py`.
"""

import asyncio
import logging
import socket
import time
from typing import Optional

from curl_cffi.curl import CurlOpt
from curl_cffi.requests import Session, AsyncSession

from core_agent.config.compliance import impersonate_profile, reserve_slot, user_agent
from core_agent.core.proxy_manager import get_proxy_manager

logger = logging.getLogger("http-client")

REQUEST_TIMEOUT = 30.0

# DNS cache: {host: (ip_list, expiry_timestamp)}
_dns_cache: dict[str, tuple[list[str], float]] = {}
_DNS_CACHE_TTL = 300  # 5 minutes


def _resolve_host(host: str) -> list[str]:
    """Resolve hostname with retries + cache."""
    now = time.time()
    cached = _dns_cache.get(host)
    if cached and cached[1] > now:
        return cached[0]

    last_err = None
    for attempt in range(3):
        try:
            ips = [r[4][0] for r in socket.getaddrinfo(host, 443)]
            if ips:
                _dns_cache[host] = (ips, now + _DNS_CACHE_TTL)
                return ips
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(2)
    logger.debug("Could not resolve %s after 3 attempts: %s", host, last_err)
    return []


def _resolve_hosts_curl_opts(hosts: set[str]) -> dict:
    """Pre-resolve hostnames via Python's socket (works in Docker) and return
    CurlOpt.RESOLVE entries so curl_cffi's bundled libcurl doesn't need c-ares."""
    if not hosts:
        return {}
    entries = []
    for host in hosts:
        ips = _resolve_host(host)
        for ip in ips[:2]:
            entries.append(f"{host}:443:{ip}")
    if entries:
        return {CurlOpt.RESOLVE: entries}
    return {}


def _policy_headers(url: str, headers: Optional[dict]) -> dict:
    """Attach the honest User-Agent unless the caller set one deliberately."""
    merged = dict(headers or {})
    if not any(str(k).lower() == "user-agent" for k in merged):
        merged["User-Agent"] = user_agent()
    return merged


class PolicySession(Session):
    """Sync client that paces requests and identifies honestly."""

    def request(self, method, url, *args, **kwargs):
        delay = reserve_slot(url)
        if delay > 0:
            time.sleep(delay)
        kwargs["headers"] = _policy_headers(url, kwargs.get("headers"))
        return super().request(method, url, *args, **kwargs)


class AsyncPolicySession(AsyncSession):
    """Async client that paces requests and identifies honestly."""

    async def request(self, method, url, *args, **kwargs):
        delay = reserve_slot(url)
        if delay > 0:
            await asyncio.sleep(delay)
        kwargs["headers"] = _policy_headers(url, kwargs.get("headers"))
        return await super().request(method, url, *args, **kwargs)


def _build_session(async_mode: bool, timeout: float = REQUEST_TIMEOUT, **kwargs):
    pm = get_proxy_manager()
    proxy = pm.get_proxy()
    proxies = {"https": proxy, "http": proxy} if proxy else None
    impersonate = impersonate_profile()

    # Merge any existing curl_options with pre-resolved hostnames
    existing_opts = kwargs.pop("curl_options", {}) or {}
    resolve_hosts = kwargs.pop("resolve_hosts", None)
    if resolve_hosts:
        existing_opts.update(_resolve_hosts_curl_opts(resolve_hosts))

    cls = AsyncPolicySession if async_mode else PolicySession
    return cls(
        timeout=timeout,
        impersonate=impersonate,
        proxies=proxies,
        curl_options=existing_opts or None,
        **kwargs,
    )


def get_async_client(timeout: float = REQUEST_TIMEOUT, **kwargs) -> AsyncSession:
    return _build_session(async_mode=True, timeout=timeout, **kwargs)


def get_sync_client(timeout: float = REQUEST_TIMEOUT, **kwargs) -> Session:
    return _build_session(async_mode=False, timeout=timeout, **kwargs)


async def close_async():
    pass


def close_sync():
    pass


async def close_all():
    pass
