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


class AtTheRacesAPI:
    BASE_URL = "https://www.attheraces.com"

    @staticmethod
    def _is_challenge_page(body: bytes) -> bool:
        """Detect bot-challenge shells (Fastly/Cloudflare) with no real content."""
        if not body:
            return True
        low = body[:8000].lower()
        markers = (b"_fs-ch-", b"just a moment", b"cf-challenge", b"attention required", b"enable javascript to proceed")
        return any(m in low for m in markers)

    def _fetch(self, path: str) -> Optional[bytes]:
        """Fetch page with tiered fallback: StealthyFetcher → Fetcher → httpx.

        Each tier must return HTTP 200 with a non-challenge body, otherwise the
        next tier is tried. A 200 challenge shell (e.g. Fastly 3KB page) is NOT
        accepted as success.
        """
        url = f"{self.BASE_URL}{path}"

        # DNS pre-check — skip Scrapling entirely if domain can't resolve (avoids noisy retries)
        import socket as _socket
        try:
            _socket.setdefaulttimeout(3)
            _socket.gethostbyname("www.attheraces.com")
        except Exception:
            logger.debug("ATR DNS resolution failed — skipping %s", path)
            return None

        # Tier 1: StealthyFetcher — headless Chromium with Cloudflare solver + persistent profile
        if _STEALTH_AVAILABLE:
            try:
                page = StealthyFetcher.fetch(
                    url,
                    headless=True,
                    solve_cloudflare=True,
                    user_data_dir=BROWSER_PROFILE,
                    timeout=30000,
                    disable_resources=True,
                    retries=1,
                    retry_delay=1,
                )
                if page and page.status == 200 and not self._is_challenge_page(page.body):
                    return page.body
                if page and page.status == 200:
                    logger.debug("Stealth fetch returned challenge shell for %s — trying next tier", path)
            except Exception as e:
                logger.debug("Stealth fetch failed for %s: %s", path, e)

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

        # Tier 3: httpx fallback (Modal-friendly, no Chromium, no curl impersonation)
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
                        logger.debug("httpx fallback returned challenge shell for %s", path)
                    else:
                        return resp.content
        except Exception as e:
            logger.debug("httpx fallback failed for %s: %s", path, e)

        logger.debug("All fetch tiers failed for %s", url)
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
        for attempt in range(3):
            try:
                html = await asyncio.wait_for(asyncio.to_thread(self._fetch, f"/results/{date}"), timeout=150)
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

        sel = Selector(html, auto_save=True, adaptive=True)
        races = []

        meeting_divs = sel.css(".push--x-small")
        if not meeting_divs:
            logger.warning("No meeting containers (.push--x-small) found on ATR page (%d bytes)", len(html))
            return races

        for meeting in meeting_divs:
            panel_header = meeting.css("a.panel-header h2", adaptive=True)
            if not panel_header:
                continue
            course = _text(panel_header[0]).replace("Results", "").strip()
            if not course:
                continue

            for article in meeting.css("article.panel-content--medium", adaptive=True):
                header_h3 = article.css("header h3", adaptive=True)
                if not header_h3:
                    continue

                h3_text = _text(header_h3[0])
                time_match = re.match(r"\d+\s+(\d{2}:\d{2})", h3_text)
                race_time = time_match.group(1) if time_match else ""

                runner_list = article.css(".list.list--divided.list--padded", adaptive=True)
                runners = []
                if runner_list:
                    for row in runner_list[0].children:
                        if row.tag == "div" and row.css("a.h7", adaptive=True):
                            runner = self._parse_one_runner(row)
                            if runner:
                                runners.append(runner)

                if runners:
                    races.append({
                        "course": course,
                        "date": date,
                        "time": race_time,
                        "title": h3_text,
                        "runners": runners,
                    })

        logger.info(
            "ATR results: %d races from %d meetings",
            len(races),
            len([m for m in meeting_divs if m.css("a.panel-header h2", adaptive=True)]),
        )
        return races

    async def get_results_for_track(self, track_name: str, date: str = "yesterday") -> List[Dict]:
        """Get results filtered to a specific track.

        Handles name matching: 'greyville' matches 'Greyville (RSA)' on ATR.
        Returns race list with runners, each runner having 'position' and 'name'.
        """
        all_results = await self.get_results(date=date)
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

    async def get_market_movers(self) -> List[Dict]:
        """Scrape /market-movers via table rows — columns: Horse, Race, Last Price, 1st Show, Mov."""
        try:
            html = await asyncio.wait_for(asyncio.to_thread(self._fetch, "/market-movers"), timeout=60)
        except asyncio.TimeoutError:
            logger.warning("ATR market movers fetch timed out after 60s")
            return []
        if not html:
            return []

        sel = Selector(html, auto_save=True, adaptive=True)
        movers = []

        for table in sel.css("table", adaptive=True):
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

                course = time = ""
                if race_str:
                    parts = race_str.strip().split()
                    if len(parts) >= 2:
                        course = parts[0]
                        time = parts[1]

                movers.append({
                    "horse": horse,
                    "course": course,
                    "time": time,
                    "current_odds": last_price,
                    "first_show": first_show,
                    "movement": movement,
                })

        return movers

    async def get_predictor(self) -> List[Dict]:
        """Scrape /predictor for AI predictions (table-based)."""
        try:
            html = await asyncio.wait_for(asyncio.to_thread(self._fetch, "/predictor"), timeout=60)
        except asyncio.TimeoutError:
            logger.warning("ATR predictor fetch timed out after 60s")
            return []
        if not html:
            return []

        sel = Selector(html, auto_save=True, adaptive=True)
        predictions = []

        for table in sel.css("table", adaptive=True):
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
                })

        return predictions
