"""at-the-races.com Scraper -- Results, Market Movers, and Predictor
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
"""

import asyncio
import logging
import re
from typing import Dict, Any, List, Optional

_SCRAPLING_AVAILABLE = False
_STEALTH_AVAILABLE = False

try:
    from scrapling.fetchers import Fetcher, StealthyFetcher
    from scrapling.parser import Selector
    _SCRAPLING_AVAILABLE = True
    _STEALTH_AVAILABLE = True
except ImportError:
    try:
        from scrapling.fetchers import Fetcher
        from scrapling.parser import Selector
        _SCRAPLING_AVAILABLE = True
    except ImportError:
        class Fetcher:
            @staticmethod
            def get(url, **kwargs):
                return type("Page", (), {"status": 200, "body": b"", "headers": {}})()

BROWSER_PROFILE = "/app/data/browser_profile"

logger = logging.getLogger("at-the-races")
logging.getLogger("scrapling").setLevel(logging.ERROR)


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

    def _fetch(self, path: str) -> Optional[bytes]:
        """Fetch page with tiered fallback: StealthyFetcher → Fetcher → None."""
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
                if page and page.status == 200:
                    return page.body
            except Exception as e:
                logger.debug("Stealth fetch failed for %s: %s", path, e)

        # Tier 2: Basic Fetcher — fast HTTP impersonation (curl_cffi)
        if _SCRAPLING_AVAILABLE:
            try:
                page = Fetcher.get(url, impersonate="chrome131", timeout=15)
                if page and page.status == 200:
                    return page.body
            except Exception as e:
                logger.debug("Basic fetch failed for %s: %s", path, e)

        logger.debug("All fetch tiers failed for %s", url)
        return None

    def _parse_one_runner(self, runner_el) -> Optional[Dict]:
        link = runner_el.css("a.h7.a--plain.tooltip, a[class*=tooltip]", adaptive=True)
        if not link:
            return None
        link = link[0]
        spans = link.css("span", adaptive=True)

        name = None
        odds_text = None
        position = None
        form = ""

        for s in spans:
            cls = s.attrib.get("class", "")
            txt = _text(s)

            if "silk" in cls or "icon" in cls:
                continue

            if "neutral" in cls:
                pos_match = re.search(r"(1st|2nd|3rd|\d+th)", txt)
                if pos_match:
                    position = pos_match.group(1)
                odds_match = re.search(r"\d+/\d+", txt)
                if odds_match:
                    odds_text = odds_match.group(0)
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
        """Scrape race results via Scrapling with self-healing selectors."""
        try:
            html = await asyncio.wait_for(asyncio.to_thread(self._fetch, f"/results/{date}"), timeout=60)
        except asyncio.TimeoutError:
            logger.warning("ATR results fetch timed out after 60s: %s", date)
            return []
        if not html:
            return []

        sel = Selector(html, auto_save=True, adaptive=True)
        races = []

        meeting_divs = sel.css(".push--x-small")
        if not meeting_divs:
            logger.warning("No meeting containers (.push--x-small) found on ATR page")
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
