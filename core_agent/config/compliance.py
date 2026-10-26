"""Scraper compliance policy — the honest-client contract for outbound requests.

Rules this module enforces (see the `honest-scraper-clients` change):

1. Identify honestly. No browser TLS impersonation by default, no fake
   User-Agent. `SCRAPER_IMPERSONATE` re-enables a profile explicitly and logs
   that it is doing so — it is evasion, not a default.
2. One request per host per `min_interval_secs`. Bursts are what get scrapers
   blocked, and rate limiting is the one part of "be a good citizen" that is
   fully in our control.
3. A deny list always wins. `SCRAPER_DENY_HOSTS` takes a comma-separated list
   and is checked before every request.

Nothing here makes automated access permitted by a site's terms — it only
removes the things that make us look like an adversary.
"""

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger("compliance")

DEFAULT_USER_AGENT = "strike-tips/1.0 (+https://strike-tips-hud.pages.dev)"
UA_ENV = "SCRAPER_UA"
IMPERSONATE_ENV = "SCRAPER_IMPERSONATE"
DENY_ENV = "SCRAPER_DENY_HOSTS"


class PolicyViolation(RuntimeError):
    """Raised when a request targets a host the policy denies."""


@dataclass(frozen=True)
class DomainPolicy:
    host: str
    min_interval_secs: float
    purpose: str
    allowed: bool = True


# Known scraper targets. Intervals are deliberately slow: these endpoints are
# polled on a schedule, not browsed, so nothing is lost by pacing them.
DOMAIN_POLICIES: Dict[str, DomainPolicy] = {
    "www.betway.co.za": DomainPolicy(
        "www.betway.co.za", 5.0, "TrackRacing odds API (documented endpoint)"
    ),
    "www.tab.co.za": DomainPolicy("www.tab.co.za", 3.0, "TAB race cards / results"),
    "www.tab4racing.com": DomainPolicy(
        "www.tab4racing.com", 3.0, "4Racing race cards / results"
    ),
    "www.tabonline.co.za": DomainPolicy(
        "www.tabonline.co.za", 3.0, "TAB tote content"
    ),
    "totex-col.4racing.com": DomainPolicy(
        "totex-col.4racing.com", 3.0, "4Racing phumelelaV4 content service"
    ),
    "totex-vasx.4racing.com": DomainPolicy(
        "totex-vasx.4racing.com", 3.0, "4Racing phumelelaV4 gameplay service"
    ),
    "www.raceform.co.za": DomainPolicy(
        "www.raceform.co.za", 3.0, "Raceform results + tote dividends"
    ),
    "raceform.co.za": DomainPolicy(
        "raceform.co.za", 3.0, "Raceform results + tote dividends"
    ),
    "www.racing-odds.com": DomainPolicy(
        "www.racing-odds.com", 3.0, "Odds comparison HTML"
    ),
    "www.attheraces.com": DomainPolicy(
        "www.attheraces.com",
        6.0,
        "UK/IRE results only — no stealth tier, circuit-broken when blocked",
    ),
}

# Unlisted hosts are allowed but paced at this interval and logged once, so a
# new target shows up in the audit trail instead of silently joining the set.
DEFAULT_MIN_INTERVAL_SECS = 2.0
DEFAULT_PURPOSE = "unlisted host"

_next_allowed: Dict[str, float] = {}
_throttle_lock = threading.Lock()
_warned_hosts: set = set()


def host_for(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _denied_hosts() -> set:
    raw = os.environ.get(DENY_ENV, "")
    return {h.strip().lower() for h in raw.split(",") if h.strip()}


def user_agent() -> str:
    return os.environ.get(UA_ENV, "").strip() or DEFAULT_USER_AGENT


def impersonate_profile() -> Optional[str]:
    """Browser TLS profile to impersonate, or None for an honest client.

    Off by default. When set, it is logged at WARNING because presenting a
    browser fingerprint while not being a browser is exactly the behaviour
    that turns "a scraper" into "an evader".
    """
    profile = os.environ.get(IMPERSONATE_ENV, "").strip()
    if profile:
        logger.warning(
            "SCRAPER_IMPERSONATE=%s — TLS fingerprint spoofing enabled "
            "(evasion; disable unless a target genuinely requires it)",
            profile,
        )
        return profile
    return None


def policy_for(url: str) -> DomainPolicy:
    host = host_for(url)
    denied = _denied_hosts()
    if host and any(host == d or host.endswith("." + d) for d in denied):
        return DomainPolicy(host, 0.0, f"denied via {DENY_ENV}", allowed=False)
    policy = DOMAIN_POLICIES.get(host)
    if policy is not None:
        return policy
    if host and host not in _warned_hosts:
        _warned_hosts.add(host)
        logger.info("Unlisted host %s — default %.1fs pacing", host, DEFAULT_MIN_INTERVAL_SECS)
    return DomainPolicy(host, DEFAULT_MIN_INTERVAL_SECS, DEFAULT_PURPOSE)


def check_allowed(url: str) -> DomainPolicy:
    policy = policy_for(url)
    if not policy.allowed:
        raise PolicyViolation(f"Request to {policy.host} denied by policy ({policy.purpose})")
    return policy


def reserve_slot(url: str) -> float:
    """Reserve the next request slot for a host; return seconds to wait.

    Reservation (not fire-then-wait) keeps concurrent callers from all waking
    at once when several parsers hit the same host in a gather().
    """
    policy = check_allowed(url)
    host = policy.host or "_"
    with _throttle_lock:
        now = time.monotonic()
        slot = max(now, _next_allowed.get(host, 0.0))
        _next_allowed[host] = slot + policy.min_interval_secs
    return max(0.0, slot - now)


def reset_throttle() -> None:
    """Clear pacing state (tests + long-running monitors after clock jumps)."""
    with _throttle_lock:
        _next_allowed.clear()
