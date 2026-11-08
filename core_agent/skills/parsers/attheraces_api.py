"""at-the-races.com Scraper -- Results, Market Movers, Predictor, and Winner Lookup
Uses Scrapling adaptive/self-healing selectors via desktop site (www).

Architecture (tiered fallback):
  1. StealthyFetcher  — headless Chromium + Cloudflare solver, persistent browser profile
  2. Fetcher           — fast HTTP-level impersonation (curl_cffi)
  3. if data: guard    — preserves last good snapshot if both fetchers fail

Integration:
    api = AtTheRacesAPI()
    results = await api.get_results(date="yesterday")
    movers = await api.get_market_movers()
    predictions = await api.get_predictor()
    # Winner lookup for bet settlement:
    winner = await api.get_winner_for_bet("Greyville", 4, "yesterday")
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional, Tuple

_SCRAPLING_AVAILABLE = False
_STEALTH_AVAILABLE = False

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher
    _SCRAPLING_AVAILABLE = True
    _STEALTH_AVAILABLE = True
except ImportError:
    _STEALTH_AVAILABLE = False
    try:
        from scrapling.fetchers import Fetcher
        _SCRAPLING_AVAILABLE = True
    except ImportError:
        _SCRAPLING_AVAILABLE = False

        class Fetcher:
            @staticmethod
            def get(url, **kwargs):
                return type("Page", (), {"status": 200, "body": b"", "headers": {}})()

# Selector imported independently — a fetcher-only failure (e.g. missing
# `patchright` on Modal) must never kill HTML parsing (lxml/bs4 path).
try:
    from scrapling.parser import Selector
    _SELECTOR_AVAILABLE = True
except ImportError:
    _SELECTOR_AVAILABLE = False

    class Selector:
        def __init__(self, *args, **kwargs):
            pass

        def css(self, *args, **kwargs):
            return []

BROWSER_PROFILE = "/app/data/browser_profile"

logger = logging.getLogger("at-the-races")

# ─── Circuit breaker (Oct-2026) ─────────────────────────────────────────────
# ATR moved behind Fastly bot protection: httpx gets 403, curl_cffi and a real
# headless Chromium both get a challenge shell with no content. Verified from
# both the Modal workers and a plain developer machine, so it is not our egress
# IP. Every 5-min odds cycle used to burn 10-15s per dead URL and log a warning
# per attempt; the staleness monitor then alarmed every cycle. Trip after N
# consecutive failures and stay silent for the cooldown instead. The flag sits
# on the data volume so it is shared by all containers and survives cold starts,
# and any successful fetch clears it (self-heals if ATR ever opens back up).
_BREAKER_FAILURE_THRESHOLD = 6
_BREAKER_COOLDOWN_SECS = 6 * 3600
_breaker_failures = 0


def _breaker_flag_path():
    try:
        from core_agent.config.paths import DATA_DIR

        return DATA_DIR / ".atr_blocked_until"
    except Exception:
        return None


def atr_circuit_open() -> bool:
    """True while the breaker is holding ATR fetches off."""
    try:
        import time as _time

        flag = _breaker_flag_path()
        if flag is None or not flag.exists():
            return False
        return float(flag.read_text().strip() or 0) > _time.time()
    except Exception:
        return False


def _record_failure(path: str) -> None:
    global _breaker_failures
    _breaker_failures += 1
    if _breaker_failures < _BREAKER_FAILURE_THRESHOLD:
        return
    try:
        import time as _time

        flag = _breaker_flag_path()
        if flag is not None:
            flag.write_text(str(_time.time() + _BREAKER_COOLDOWN_SECS))
        logger.warning(
            "ATR circuit breaker TRIPPED after %d consecutive failures (last: %s) — "
            "pausing ATR fetches for %dh; host is blocking every tier",
            _breaker_failures,
            path,
            _BREAKER_COOLDOWN_SECS // 3600,
        )
    except Exception:
        pass


def _record_success() -> None:
    global _breaker_failures
    if _breaker_failures:
        logger.info("ATR fetch recovered — circuit breaker reset")
    _breaker_failures = 0
    try:
        flag = _breaker_flag_path()
        if flag is not None and flag.exists():
            flag.unlink()
    except Exception:
        pass
logging.getLogger("scrapling").setLevel(logging.ERROR)

TRACK_NAME_ALIASES = {
    "greyville": "Greyville",
    "durbanville": "Durbanville",
    "turffontein": "Turffontein",
    "vaal": "Vaal",
    "kenilworth": "Kenilworth",
    "fairview": "Fairview",
    "scottsville": "Scottsville",
}


def _parse_odds(odds_text: Optional[str]) -> Optional[float]:
    if not odds_text or odds_text in ("SP", "N/A", "-"):
        return None
    try:
        parts = odds_text.strip().split("/")
        if len(parts) == 2:
            return round((float(parts[0]) / float(parts[1])) + 1, 2)
    except (ValueError, IndexError, ZeroDivisionError):
        pass
    return None


def _text(el) -> str:
    return el.get_all_text(strip=True) if el else ""


# ATR course shorthand → canonical track + region. ATR groups its pages by
# meeting but the course lives in group headers, not row cells — parsers that
# read cells alone produce "Unknown Venue" (Oct-2026: 439/574 movers). SA
# codes follow Computaform (G/N Greyville turf/poly, E/F Fairview poly/turf…);
# UK/IRL use ATR 3-letter codes. FP maps to defunct (Kimberley closed Jul-2020).
ATR_COURSE_MAP: Dict[str, Dict[str, str]] = {
    # SA — KwaZulu-Natal
    "G": {"track": "Greyville", "region": "SA"},
    "GREYVILLE": {"track": "Greyville", "region": "SA"},
    "N": {"track": "Greyville Poly", "region": "SA"},
    "S": {"track": "Scottsville", "region": "SA"},
    "SCOTTSVILLE": {"track": "Scottsville", "region": "SA"},
    "P": {"track": "Scottsville Inside", "region": "SA"},
    # SA — Gauteng
    "T": {"track": "Turffontein", "region": "SA"},
    "TURFFONTEIN": {"track": "Turffontein", "region": "SA"},
    "J": {"track": "Turffontein Inside", "region": "SA"},
    "B": {"track": "Vaal Classic", "region": "SA"},
    "V": {"track": "Vaal Turf", "region": "SA"},
    "VAAL": {"track": "Vaal", "region": "SA"},
    # SA — Western Cape
    "K": {"track": "Kenilworth", "region": "SA"},
    "KENILWORTH": {"track": "Kenilworth", "region": "SA"},
    "W": {"track": "Kenilworth Winter", "region": "SA"},
    "D": {"track": "Durbanville", "region": "SA"},
    "DURBANVILLE": {"track": "Durbanville", "region": "SA"},
    # SA — Eastern Cape
    "E": {"track": "Fairview Poly", "region": "SA"},
    "F": {"track": "Fairview Turf", "region": "SA"},
    "FAIRVIEW": {"track": "Fairview", "region": "SA"},
    # Defunct — never resolve to a live track
    "Y": {"track": "Flamingo Park (closed 2020)", "region": "defunct"},
    "FLAMINGO": {"track": "Flamingo Park (closed 2020)", "region": "defunct"},
    "KIMBERLEY": {"track": "Flamingo Park (closed 2020)", "region": "defunct"},
    # UK — ATR feed regulars
    "NCS": {"track": "Newcastle", "region": "UK"},
    "NEWCASTLE": {"track": "Newcastle", "region": "UK"},
    "SAL": {"track": "Salisbury", "region": "UK"},
    "SALISBURY": {"track": "Salisbury", "region": "UK"},
    "STH": {"track": "Southwell", "region": "UK"},
    "SOUTHWELL": {"track": "Southwell", "region": "UK"},
    "NTT": {"track": "Nottingham", "region": "UK"},
    "NOTTINGHAM": {"track": "Nottingham", "region": "UK"},
    "CLO": {"track": "Clonmel", "region": "Ireland"},
    "CLONMEL": {"track": "Clonmel", "region": "Ireland"},
    "BEL": {"track": "Bellewstown", "region": "Ireland"},
    "BELLEWSTOWN": {"track": "Bellewstown", "region": "Ireland"},
    "ASC": {"track": "Ascot", "region": "UK"},
    "CHL": {"track": "Cheltenham", "region": "UK"},
    "NMK": {"track": "Newmarket", "region": "UK"},
    # ATR 3-letter meeting codes as seen live (Oct-2026 movers feed)
    "KMP": {"track": "Kempton", "region": "UK"},
    "KEMPTON": {"track": "Kempton", "region": "UK"},
    "STR": {"track": "Stratford", "region": "UK"},
    "STRATFORD": {"track": "Stratford", "region": "UK"},
    "PFR": {"track": "Pontefract", "region": "UK"},
    "PONTEFRACT": {"track": "Pontefract", "region": "UK"},
    "WOL": {"track": "Wolverhampton", "region": "UK"},
    "WOLVERHAMPTON": {"track": "Wolverhampton", "region": "UK"},
    "YAR": {"track": "Yarmouth", "region": "UK"},
    "YARMOUTH": {"track": "Yarmouth", "region": "UK"},
    "FAI": {"track": "Fairyhouse", "region": "Ireland"},
    "FAIRYHOUSE": {"track": "Fairyhouse", "region": "Ireland"},
    "KIL": {"track": "Killarney", "region": "Ireland"},
    "KILLARNEY": {"track": "Killarney", "region": "Ireland"},
    "GAL": {"track": "Galway", "region": "Ireland"},
    "GALWAY": {"track": "Galway", "region": "Ireland"},
    "LEI": {"track": "Leicester", "region": "UK"},
    "LEICESTER": {"track": "Leicester", "region": "UK"},
    "HUN": {"track": "Huntingdon", "region": "UK"},
    "HUNTINGDON": {"track": "Huntingdon", "region": "UK"},
    "BHA": {"track": "Brighton", "region": "UK"},
    "BRIGHTON": {"track": "Brighton", "region": "UK"},
    # ATR short codes seen on the movers feed (Nov-2026). Unmapped, they fell
    # through the passthrough branch and the HUD displayed "Ain"/"Hex"/"Fon".
    "AIN": {"track": "Aintree", "region": "UK"},
    "AINTREE": {"track": "Aintree", "region": "UK"},
    "HEX": {"track": "Hexham", "region": "UK"},
    "HEXHAM": {"track": "Hexham", "region": "UK"},
    "FON": {"track": "Fontwell", "region": "UK"},
    "FONTWELL": {"track": "Fontwell", "region": "UK"},
    "DUN": {"track": "Dundalk", "region": "Ireland"},
    "DUNDALK": {"track": "Dundalk", "region": "Ireland"},
}


def normalize_course(raw: str) -> Dict[str, str]:
    """ATR header/cell text → {track, region}.

    Priority: map hit (codes + known names) → short-token passthrough (keeps
    the old display behaviour: unmapped codes like "Ntt" still show instead
    of blanking) → blank. Poison shapes (page titles, horse strings with
    cloth numbers, menu words) ALWAYS blank — a wrong venue is infinitely
    worse than a missing one (Oct-2026: "SHARK TWO ONE" as a venue).
    """
    _POISON_WORDS = ("summary", "results", "predictor", "movers", "login",
                     "join", "menu", "account", "watch", "tips", "news",
                     "replay", "calendar")
    _TOKEN_RE = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,23}$")
    # Meeting headers arrive as "Aintree 13:50"; the off-time is not part of
    # the venue and the digit guard below would blank the whole course. On
    # 2026-11-06 that cost 325 of 458 movers their course (the HUD then fell
    # back to "Course unverified" for every one of them).
    _OFF_TIME_RE = re.compile(r"\s+\d{1,2}[:.]\d{2}\s*$")
    raw = _OFF_TIME_RE.sub("", (raw or "").strip()).strip()
    key = (raw or "").strip().upper()
    if not key:
        return {"track": "", "region": ""}
    # Headers look like "Newcastle Results" / "Greyville" / "Ntt 13:23".
    for token in (key, key.split()[0] if key.split() else ""):
        if token in ATR_COURSE_MAP:
            return dict(ATR_COURSE_MAP[token])
    text = (raw or "").strip()
    lowered = text.lower()
    if (not any(w in lowered for w in _POISON_WORDS)
            and not any(ch.isdigit() for ch in text)
            and _TOKEN_RE.match(text)):
        return {"track": text, "region": ""}
    return {"track": "", "region": ""}


def _segment_by_headings(html: bytes) -> List[Tuple[str, str]]:
    """Split raw HTML into (heading_text, table_html) pairs.

    Every <table> inherits the nearest preceding <h1>–<h4>/caption text.
    Titles are returned RAW — callers must pass them through
    normalize_course (validate-or-blank), never display them directly.
    """
    try:
        text = html.decode("utf-8", errors="ignore") if isinstance(html, bytes) else str(html)
    except Exception:
        return []
    heads = [(m.start(), re.sub(r"<[^>]+>", " ", m.group(1)).strip())
             for m in re.finditer(r"<h[1-4][^>]*>(.*?)</h[1-4]>", text,
                                  re.IGNORECASE | re.DOTALL)]
    tables = [(m.start(), m.group(0))
              for m in re.finditer(r"<table.*?</table>", text,
                                   re.IGNORECASE | re.DOTALL)]
    out: List[Tuple[str, str]] = []
    for tpos, thtml in tables:
        title = ""
        for hpos, htext in heads:
            if hpos < tpos:
                title = htext
            else:
                break
        out.append((re.sub(r"\s+", " ", title).strip(), thtml))
    return out


class AtTheRacesAPI:
    BASE_URL = "https://www.attheraces.com"

    # Set when the last tiered fetch failed only because our own browser
    # throttle (≤1/hour) skipped the one tier that can clear Fastly. Such a
    # miss is self-inflicted, not evidence the host is blocking us, so it must
    # not count toward the circuit breaker (Nov-2026: the throttle plus cheap
    # 403s tripped a 6h breaker every afternoon).
    _self_throttled = False

    @staticmethod
    def _is_challenge_page(body: bytes) -> bool:
        """Detect bot-challenge shells with no real content.

        NOTE (2026-09-04 post-mortem): the Fastly beacon ``/_fs-ch-`` script tag
        is embedded in the <head> of EVERY ATR page — good ones included — so it
        must NEVER be used as a challenge marker (doing so rejected all good
        pages and caused the 18h Sep-03/04 staleness outage). Discriminate on
        size + absence of real content instead: genuine ATR pages are 1-2MB;
        challenge shells are ~3KB noscript stubs.
        """
        if not body:
            return True
        if len(body) < 8000:
            return True
        body_low = body.lower()
        has_content = (b"push--x-small" in body_low) or (b"<table" in body_low)
        if b"javascript is disabled" in body_low[:8000] and not has_content:
            return True
        return False

    @staticmethod
    def _page_date(html: bytes) -> Optional[str]:
        """The ISO day the results page is actually showing, or None.

        ATR embeds the selected day in a readonly datepicker input. Trusting it
        beats guessing from the request label: ``/results`` in the morning can
        still be rendered against the previous day's card, and a snapshot that
        stamps the wrong day mis-settles picks (``settlement._atr_date``).
        """
        if not html:
            return None
        for field in (b"race-nav-datepicker", b"sidebar-racecards-datepicker"):
            m = re.search(
                rb'id="' + field + rb'"[^>]*value="(\d{4}-\d{2}-\d{2})"',
                html,
            )
            if m:
                try:
                    return m.group(1).decode()
                except Exception:
                    continue
        return None

    @staticmethod
    def _label_iso(day: Any) -> Optional[str]:
        """Best-effort ISO day for a relative request label ("today"/"yesterday")."""
        from datetime import date as _date, timedelta as _timedelta

        s = str(day or "").strip().lower()
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        today = _date.today()
        if s in ("today", ""):
            return today.isoformat()
        if s in ("yesterday", "yday"):
            return (today - _timedelta(days=1)).isoformat()
        return None

    # Minimum gap between headless-Chromium escalations. The browser solve is
    # expensive (~60s cold) and looks bot-like at 5-min cron cadence — it likely
    # got our egress IP rate-limited on 2026-09-03 (18h of challenge shells
    # right after Tier 1 was enabled). Throttle file lives on the data volume
    # so it is shared across cold containers.
    _STEALTH_MIN_GAP_SECS = 3600

    # Fastly's proof-of-work needs wall-clock time to run before the body is
    # captured. Without it StealthyFetcher snapshots the ~3KB noscript stub
    # (Nov-2026: /results came back 3.1KB "solved" in 1.4s on every URL).
    # 15s returns the real 800KB page; network_idle usually gets there in ~5s.
    _STEALTH_WAIT_MS = 15000

    # Per-process cache for the parsed results page. A populated page is good
    # for five minutes; an empty one only for one, so a genuine retry is not
    # blocked but a settlement loop cannot hammer the host.
    _RESULTS_CACHE_TTL = 300
    _RESULTS_CACHE_TTL_EMPTY = 60

    def _stealth_allowed(self) -> bool:
        try:
            import time as _time
            from core_agent.config.paths import DATA_DIR
            flag = DATA_DIR / ".atr_stealth_last"
            if flag.exists():
                last = float(flag.read_text().strip() or 0)
                if _time.time() - last < self._STEALTH_MIN_GAP_SECS:
                    return False
            flag.write_text(str(_time.time()))
            return True
        except Exception:
            return True

    def _fetch(self, path: str) -> Optional[bytes]:
        """Fetch with the circuit breaker wrapped around the tiered fallback."""
        if atr_circuit_open():
            logger.debug("ATR circuit breaker open — skipping %s", path)
            return None
        body = self._fetch_tiered(path)
        if body:
            _record_success()
        elif getattr(self, "_self_throttled", False):
            logger.debug(
                "ATR %s missed while the browser tier was throttled — "
                "not counting toward the circuit breaker", path,
            )
        else:
            _record_failure(path)
        return body

    def _fetch_tiered(self, path: str) -> Optional[bytes]:
        """Fetch page with cheap-first tiered fallback: httpx → Fetcher → StealthyFetcher.

        Order matters: the 5-min cron hammers these URLs, so the lightweight
        HTTP tiers run first and the headless browser is a throttled last
        resort (max 1/hour, shared flag on the data volume). Each tier must
        return HTTP 200 with a non-challenge body, otherwise the next tier is
        tried. A 200 challenge shell (e.g. Fastly 3KB page) is NOT accepted.
        """
        url = f"{self.BASE_URL}{path}"
        self._self_throttled = False

        # DNS pre-check — skip entirely if domain can't resolve (avoids noisy retries)
        import socket as _socket
        try:
            _socket.setdefaulttimeout(3)
            _socket.gethostbyname("www.attheraces.com")
        except Exception:
            logger.debug("ATR DNS resolution failed — skipping %s", path)
            return None

        # Tier 1: httpx — cheapest, no Chromium, no curl impersonation
        try:
            import httpx

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            }
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                resp = client.get(url, headers=headers)
                if resp.status_code == 200 and resp.content and len(resp.content) > 1000:
                    if self._is_challenge_page(resp.content):
                        logger.debug("httpx returned challenge shell for %s — trying next tier", path)
                    else:
                        return resp.content
        except Exception as e:
            logger.debug("httpx fetch failed for %s: %s", path, e)

        # Tier 2: Basic Fetcher — fast HTTP impersonation (curl_cffi)
        if _SCRAPLING_AVAILABLE:
            try:
                page = Fetcher.get(url, impersonate="chrome131", timeout=30)
                if page and page.status == 200 and not self._is_challenge_page(page.body):
                    return page.body
                if page and page.status == 200:
                    logger.debug("Basic fetch returned challenge shell for %s — trying next tier", path)
            except Exception as e:
                logger.debug("Basic fetch failed for %s: %s", path, e)

        # Tier 3: StealthyFetcher — real headless Chromium, throttled last resort.
        # solve_cloudflare=False: ATR uses Fastly (not Cloudflare) — the CF solver
        # just errors with "No Cloudflare challenge found". With plain JS enabled
        # the Fastly proof-of-work runs, sets its cookie in the persistent
        # profile, and the second load (same cookies) returns the real page.
        if _STEALTH_AVAILABLE:
            if not self._stealth_allowed():
                # Only this tier can pass Fastly. Skipping it is our throttle,
                # not the host's block: record it so the breaker stays shut.
                self._self_throttled = True
                logger.debug("Stealth fetch throttled for %s (browser used <1h ago)", path)
            else:
                import time as _time
                for _attempt in range(2):
                    # Attempt 1 waits for network idle (usually ~5s). Attempt 2
                    # gives the Fastly proof-of-work a fixed 15s of wall clock —
                    # the reload-with-cookies path that actually clears it.
                    _extra = {"network_idle": True} if _attempt == 0 else {"wait": self._STEALTH_WAIT_MS}
                    try:
                        page = StealthyFetcher.fetch(
                            url,
                            headless=True,
                            solve_cloudflare=False,
                            user_data_dir=BROWSER_PROFILE,
                            timeout=90000,
                            disable_resources=False,
                            retries=1,
                            retry_delay=3,
                            **_extra,
                        )
                        if page and page.status == 200 and not self._is_challenge_page(page.body):
                            return page.body
                        if page and page.status == 200:
                            logger.debug(
                                "Stealth fetch attempt %d returned challenge shell for %s — retrying with a longer wait",
                                _attempt + 1, path,
                            )
                    except TypeError:
                        # Older Scrapling without network_idle/wait kwargs.
                        try:
                            page = StealthyFetcher.fetch(
                                url,
                                headless=True,
                                solve_cloudflare=False,
                                user_data_dir=BROWSER_PROFILE,
                                timeout=90000,
                                disable_resources=False,
                                retries=1,
                                retry_delay=3,
                            )
                            if page and page.status == 200 and not self._is_challenge_page(page.body):
                                return page.body
                        except Exception as e:
                            logger.debug("Stealth fetch fallback failed for %s: %s", path, e)
                    except Exception as e:
                        logger.debug("Stealth fetch attempt %d failed for %s: %s", _attempt + 1, path, e)
                    _time.sleep(4)

        # Breaker owns the operator-facing noise: it logs the trip once and then
        # goes quiet for the cooldown, so per-attempt warnings stay at debug.
        logger.debug("ATR all fetch tiers failed for %s — keeping last-good snapshot", url)
        return None

    def _parse_one_runner(self, runner_el) -> Optional[Dict]:
        """Parse a single runner row from the results page.

        HTML structure:
            <a class="h7 a--plain tooltip" href="/form/horse/...">
                <span class="text-color--neutral">
                    1st
                    <span class="silk silk--inline"><img ...></span>
                    (10)
                </span>
                <span>HorseName</span>
                <span class="text-color--neutral">15/8</span>
                <span>F</span>
            </a>
        """
        link = runner_el.css("a.h7.a--plain.tooltip, a[class*=tooltip]", adaptive=True)
        if not link:
            return None
        link = link[0]

        # Use direct children only to avoid picking up nested spans (e.g. silk inside neutral)
        name = None
        odds_text = None
        position = None
        form = ""

        seen_neutral = 0
        for child in link.children:
            if child.tag != "span":
                continue
            cls = child.attrib.get("class", "") or ""
            txt = _text(child)

            if "silk" in cls or "icon" in cls:
                continue

            if "neutral" in cls:
                seen_neutral += 1
                if seen_neutral == 1:
                    pos_match = re.search(r"(1st|2nd|3rd|\d+th)", txt)
                    if pos_match:
                        position = pos_match.group(1)
                elif seen_neutral >= 2:
                    odds_match = re.search(r"\d+/\d+", txt)
                    if odds_match:
                        odds_text = odds_match.group(0)
                    elif "Evens" in txt or "Evens" in txt:
                        odds_text = "1/1"
                continue

            if not name and txt and len(txt) > 1:
                name = txt
            elif name and txt and len(txt) <= 3:
                form = txt

        if not odds_text:
            m = re.search(r"(\d+/\d+)", _text(link))
            if m:
                odds_text = m.group(1)
            elif "Evens" in _text(link) or "Evens" in _text(link):
                odds_text = "1/1"

        if not name:
            for part in _text(link).split():
                if len(part) > 2 and not re.match(r"^[\d./()]+$", part):
                    name = part
                    break

        if not name:
            return None

        return {
            "name": name,
            "position": position or "",
            "odds": odds_text or "",
            "odds_decimal": _parse_odds(odds_text),
            "form": form,
        }

    async def get_results(self, date: str = "yesterday") -> List[Dict]:
        """Scrape race results via Scrapling with self-healing selectors + retry.

        Timeout is 150s (not 60s): on a cold Modal container Tier 1 StealthyFetcher
        launches Chromium + solves the Fastly challenge (~40-60s) before Tier 2/3
        get a turn. Worst case 2×150s (yesterday+today) still fits the 600s cron.
        """
        results_path = "/results" if str(date or "").lower() in ("today", "") else f"/results/{date}"
        for attempt in range(3):
            try:
                html = await asyncio.wait_for(asyncio.to_thread(self._fetch, results_path), timeout=150)
            except asyncio.TimeoutError:
                logger.warning("ATR results fetch timed out after 150s: %s", date)
                return []

            if html and len(html) < 10_000:
                logger.debug("ATR response too small (%d bytes) — possible bot block, retrying %d/3", len(html), attempt + 1)
                await asyncio.sleep(5 * (attempt + 1))
                continue
            break

        if not html:
            return []

        page_day = self._page_date(html) or self._label_iso(date)
        sel = Selector(html, auto_save=True, adaptive=True)

        meeting_divs = sel.css(".push--x-small")
        if not meeting_divs:
            logger.warning("No meeting containers (.push--x-small) found on ATR page (%d bytes)", len(html))
            return []

        # The results page nests .push--x-small inside itself, so the same
        # meeting is visited several times and every race is appended again
        # (Nov-2026: 612 races for ~26 meetings, Doncaster alone 416). Key by
        # (course, race number) and keep the richest parse.
        by_race: Dict[Tuple[str, str], Dict[str, Any]] = {}
        courses_seen = set()
        articles_seen = 0
        unplaced = 0

        for meeting in meeting_divs:
            panel_header = meeting.css("a.panel-header h2", adaptive=True)
            if not panel_header:
                continue
            course = _text(panel_header[0]).replace("Results", "").strip()
            if not course:
                continue
            courses_seen.add(course.lower())

            for article in meeting.css("article.panel-content--medium", adaptive=True):
                header_h3 = article.css("header h3", adaptive=True)
                if not header_h3:
                    continue
                articles_seen += 1

                h3_text = _text(header_h3[0])
                time_match = re.match(r"\d+\s+(\d{2}:\d{2})", h3_text)
                race_time = time_match.group(1) if time_match else ""
                num_match = re.match(r"\s*(\d+)", h3_text)
                race_no = num_match.group(1) if num_match else race_time

                runner_list = article.css(".list.list--divided.list--padded", adaptive=True)
                runners = []
                if runner_list:
                    for row in runner_list[0].children:
                        if row.tag == "div" and row.css("a.h7", adaptive=True):
                            runner = self._parse_one_runner(row)
                            if runner:
                                runners.append(runner)

                if not runners:
                    continue
                # Only store races that actually ran. Before the off the same
                # page lists the card with zero placings (Nov-2026: 135 cards,
                # 0 positions at 05:18 UTC); writing those would fill the
                # snapshot with unrun races and hide the real evening results.
                if not any(str(r.get("position") or "").strip() for r in runners):
                    unplaced += 1
                    continue

                key = (course.lower(), str(race_no))
                prev = by_race.get(key)
                if prev is None or len(runners) > len(prev["runners"]):
                    by_race[key] = {
                        "course": course,
                        "date": page_day or date,
                        "time": race_time,
                        "title": h3_text,
                        "runners": runners,
                    }

        races = list(by_race.values())
        logger.info(
            "ATR results: %d races from %d meetings (%d articles, %d unplaced, %d bytes, day=%s)",
            len(races),
            len(courses_seen),
            articles_seen,
            unplaced,
            len(html),
            page_day or date,
        )
        return races

    async def get_results_for_track(self, track_name: str, date: str = "yesterday") -> List[Dict]:
        """Get results filtered to a specific track.

        Handles name matching: 'greyville' matches 'Greyville (RSA)' on ATR.
        Returns race list with runners, each runner having 'position' and 'name'.

        Cached per-process for a few minutes: callers settle bet-by-bet, and an
        uncached implementation re-fetched the whole results page once per open
        pick (Nov-2026: 32 page fetches inside two seconds, each burning the
        shared hourly browser allowance).
        """
        import time as _time

        cache = getattr(self, "_results_cache", None)
        if cache is None:
            cache = self._results_cache = {}
        hit = cache.get(date)
        ttl = self._RESULTS_CACHE_TTL if (hit and hit[1]) else self._RESULTS_CACHE_TTL_EMPTY
        if hit and (_time.time() - hit[0]) < ttl:
            all_results = hit[1]
        else:
            all_results = await self.get_results(date=date)
            cache[date] = (_time.time(), all_results)
        if not all_results:
            return []

        canonical = TRACK_NAME_ALIASES.get(track_name.lower(), track_name.title())
        filtered = []
        for race in all_results:
            course = race.get("course", "")
            if canonical.lower() in course.lower():
                filtered.append(race)

        if not filtered and all_results:
            looser = [r for r in all_results if track_name.lower() in r.get("course", "").lower()]
            filtered = looser

        return filtered

    async def get_winner_for_bet(
        self, track_name: str, race_number: int, date: str = "yesterday"
    ) -> Optional[Dict]:
        """Get the winner for a bet at a specific track and race number.

        Returns dict with 'horse', 'position', 'odds' or None if not found.
        Example:
            winner = await api.get_winner_for_bet("Greyville", 4, "yesterday")
            # {"horse": "Sommerstern", "position": "1st", "odds": "15/8"}
        """
        track_results = await self.get_results_for_track(track_name, date=date)
        if not track_results:
            return None

        for race in track_results:
            race_num_match = re.search(r"(\d+)\s+\d{2}:\d{2}", race.get("title", ""))
            if race_num_match:
                num = int(race_num_match.group(1))
                if num != race_number:
                    continue
            else:
                continue

            for runner in race.get("runners", []):
                if runner.get("position") == "1st":
                    return {
                        "horse": runner["name"],
                        "position": "1st",
                        "odds": runner.get("odds", ""),
                        "odds_decimal": runner.get("odds_decimal"),
                        "race_time": race.get("time", ""),
                        "course": race.get("course", ""),
                    }

        return None

    async def get_placing_for_bet(
        self, track_name: str, race_number: int, horse: str, date: str = "yesterday"
    ) -> Optional[str]:
        """Get our horse's official finishing position (ATR results).

        Returns "1st"/"2nd"/"3rd"/"4th"... or None when the track/race/
        horse can't be matched. Fuzzy name match mirrors the winner path —
        ATR names carry suffixes like " (IRE)".
        """
        track_results = await self.get_results_for_track(track_name, date=date)
        if not track_results:
            return None
        want = re.sub(r"[^a-z]", "", horse.lower())
        for race in track_results:
            race_num_match = re.search(r"(\d+)\s+\d{2}:\d{2}", race.get("title", ""))
            if not race_num_match or int(race_num_match.group(1)) != race_number:
                continue
            for runner in race.get("runners", []):
                name = str(runner.get("name", ""))
                norm = re.sub(r"[^a-z]", "", name.lower())
                if want and (want in norm or norm in want):
                    return runner.get("position") or None
        return None

    async def get_market_movers(self) -> List[Dict]:
        """Scrape /market-movers via table rows — columns: Horse, Race, Last Price, 1st Show, Mov.

        Meeting-group aware (Oct-2026): ATR groups tables under meeting headers,
        so each table inherits its meeting's course; the cell race-string is
        only a fallback. Previously 439/574 movers parsed empty course.
        """
        try:
            html = await asyncio.wait_for(asyncio.to_thread(self._fetch, "/market-movers"), timeout=150)
        except asyncio.TimeoutError:
            logger.warning("ATR market movers fetch timed out after 150s")
            return []
        if not html:
            return []

        sel = Selector(html, auto_save=True, adaptive=True)
        movers = []

        for meeting_title, table in self._iter_meeting_tables(sel, html=html):
            header_course = normalize_course(meeting_title)
            rows = table.css("tr", adaptive=True)
            if len(rows) < 2:
                continue
            for row in rows[1:]:
                cells = row.css("td", adaptive=True)
                if len(cells) < 3:
                    continue
                horse = _text(cells[0])
                race_str = _text(cells[1])
                last_price = _text(cells[2])
                first_show = _text(cells[3]) if len(cells) > 3 else ""
                movement = _text(cells[4]) if len(cells) > 4 else ""

                course = time = region = ""
                if header_course.get("track"):
                    course, region = header_course["track"], header_course["region"]
                if race_str:
                    parts = race_str.strip().split()
                    if len(parts) >= 2:
                        if not course:
                            cell = normalize_course(parts[0])
                            course, region = cell["track"], cell["region"]
                        time = parts[1]
                    elif len(parts) == 1 and not time:
                        maybe_time = re.match(r"^(\d{1,2}:\d{2})$", parts[0])
                        if maybe_time:
                            time = maybe_time.group(1)

                movers.append({
                    "horse": horse,
                    "course": course,
                    "region": region,
                    "time": time,
                    "current_odds": last_price,
                    "first_show": first_show,
                    "movement": movement,
                })

        return movers

    def _iter_meeting_tables(self, sel, html: bytes | None = None) -> List[Tuple[str, Any]]:
        """Yield (meeting_title, table) in document order.

        Meeting titles come ONLY from `a.panel-header h2` (the proven
        results-page pattern) or a `caption` inside the table itself.
        Page-level h2/h3 are deliberately ignored (Oct-2026: they caught
        "MARKET MOVERS SUMMARY…" and poisoned every row's course).
        When raw html is supplied, title-less tables inherit the nearest
        preceding heading via _segment_by_headings (titles still pass
        through normalize_course downstream — never displayed raw).
        Falls back to bare tables with an empty title so legacy layouts
        keep working. Logs distinct titles seen (DOM diagnostic).
        """
        out: List[Tuple[str, Any]] = []
        seen: set = set()

        def _sig(table) -> str:
            # Adaptive selectors return fresh objects per query, so id()
            # dedupe fails and grouped tables double-count. Signature on
            # row count + first rows' text instead.
            try:
                rows = table.css("tr", adaptive=True) or []
                head = "|".join(_text(r)[:60] for r in rows[:3])
                return f"{len(rows)}:{head}"
            except Exception:
                return f"id:{id(table)}"

        try:
            meetings = sel.css(".push--x-small") or []
        except Exception:
            meetings = []
        if not meetings:
            # Movers/predictor pages group differently — try generic
            # meeting sections before falling back to bare tables.
            for container_sel in ("section.meeting", "div.meeting",
                                  "section.panel", "div.panel",
                                  "main section", "main div"):
                try:
                    meetings = sel.css(container_sel) or []
                except Exception:
                    meetings = []
                if meetings:
                    break
        for meeting in meetings:
            try:
                headers = (meeting.css("a.panel-header h2", adaptive=True)
                           or meeting.css("table caption", adaptive=True)
                           or [])
            except Exception:
                headers = []
            title = _text(headers[0]).replace("Results", "").strip() if headers else ""
            try:
                tables = meeting.css("table", adaptive=True) or []
            except Exception:
                tables = []
            for table in tables:
                sig = _sig(table)
                if sig in seen:
                    continue
                seen.add(sig)
                out.append((title, table))
        try:
            bare = sel.css("table", adaptive=True) or []
        except Exception:
            bare = []
        for table in bare:
            sig = _sig(table)
            if sig not in seen:
                seen.add(sig)
                out.append(("", table))
        # Regex backfill: when the DOM walk found no titles at all, pair
        # tables positionally with nearest-preceding headings from raw html.
        # DOM titles always win when present; segment titles only fill blanks.
        if html and not any(t for t, _ in out):
            try:
                seg = _segment_by_headings(html)
            except Exception:
                seg = []
            if seg and len(seg) == len(out):
                out = [(st, tbl) for (st, _), (_, tbl) in zip(seg, out)]
        try:
            titles = sorted({t for t, _ in out if t})
            logger.info("ATR meeting titles seen: %s",
                        titles if titles else ["<none — bare tables only>"])
        except Exception:
            pass
        return out

    async def get_predictor(self) -> List[Dict]:
        """Scrape /predictor for AI predictions (table-based, meeting-aware).

        Oct-2026: previously scraped zero meeting context — every prediction
        was courseless. Tables now inherit their meeting header's course/time.
        """
        try:
            html = await asyncio.wait_for(asyncio.to_thread(self._fetch, "/predictor"), timeout=150)
        except asyncio.TimeoutError:
            logger.warning("ATR predictor fetch timed out after 150s")
            return []
        if not html:
            if getattr(self, "_self_throttled", False):
                logger.debug("ATR predictor: browser tier throttled — no fetch attempted")
            else:
                logger.warning("ATR predictor: fetch returned no HTML (host blocked or empty)")
            return []

        sel = Selector(html, auto_save=True, adaptive=True)
        predictions = []

        for meeting_title, table in self._iter_meeting_tables(sel, html=html):
            header = normalize_course(meeting_title)
            rows = table.css("tr", adaptive=True)
            if len(rows) < 2:
                continue
            for row in rows[1:]:
                cells = row.css("td", adaptive=True)
                if len(cells) < 2:
                    continue
                horse_raw = _text(cells[1]) if len(cells) > 1 else ""
                prediction = _text(cells[2]) if len(cells) > 2 else ""

                # Extract horse name from "(cloth) HorseName (odds)" format
                horse_name = horse_raw
                m = re.search(r"\)\s*(.+?)\s*\(", horse_raw)
                if m:
                    horse_name = m.group(1).strip()

                predictions.append({
                    "horse": horse_name,
                    "raw": horse_raw,
                    "prediction": prediction,
                    "course": header.get("track", ""),
                    "region": header.get("region", ""),
                })

        if not predictions:
            logger.warning(
                "ATR predictor: page fetched (%d bytes) but 0 predictions parsed",
                len(html or ""),
            )
        return predictions
