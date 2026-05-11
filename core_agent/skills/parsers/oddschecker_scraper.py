import logging
import json
from typing import Dict
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

logger = logging.getLogger("oddschecker-scraper")


class OddscheckerScraper:
    """Oddschecker scraper using Crawl4AI. Browser spawns and closes per call — no persistent process."""

    URL = "https://www.oddschecker.com/horse-racing/today"

    # Browser config: minimal footprint, no images, stealth
    _browser_conf = BrowserConfig(
        headless=True,
        light_mode=True,
        enable_stealth=True,
        text_mode=True,
        viewport_width=1280,
        viewport_height=720,
    )

    _schema = {
        "name": "OddscheckerRaces",
        "baseSelector": "tr.event-row, .runner-row, div.all-odds-click",
        "fields": [
            {"name": "horse_name", "selector": "a.runner-name, .horse-name, .name", "type": "text"},
            {"name": "fractional_odds", "selector": "span.odds, .odds-value, .price", "type": "text"},
            {"name": "race_name", "selector": "div.race-details h3, .event-name", "type": "text"},
        ],
    }

    @staticmethod
    def fractional_to_decimal(fraction_str: str) -> float:
        try:
            if not fraction_str or not isinstance(fraction_str, str):
                return 5.0
            fraction_str = fraction_str.strip()
            if "/" in fraction_str:
                num, den = map(int, fraction_str.split("/"))
                return round((num / den) + 1.0, 2)
            if "EVS" in fraction_str.upper():
                return 2.0
            return float(fraction_str)
        except Exception:
            return 5.0

    async def get_latest_odds(self) -> Dict:
        """Spawn browser, fetch OC odds, close browser. No persistent Chromium process."""
        run_conf = CrawlerRunConfig(
            extraction_strategy=JsonCssExtractionStrategy(self._schema),
            cache_mode=CacheMode.BYPASS,
            wait_until="domcontentloaded",
            page_timeout=60000,
            delay_before_return_html=2.0,
        )

        try:
            # `async with` ensures browser is fully closed after this block
            async with AsyncWebCrawler(config=self._browser_conf) as crawler:
                logger.info(f"🕸️ OC: fetching {self.URL}")
                result = await crawler.arun(url=self.URL, config=run_conf)

            if not result.success:
                logger.warning(f"⚠️ OC crawl failed: {result.error_message}")
                return {}

            raw_data = json.loads(result.extracted_content or "[]")
            fusion_map: Dict = {}
            for item in raw_data:
                race = item.get("race_name", "Unknown Race")
                horse = item.get("horse_name")
                odds_raw = item.get("fractional_odds")
                if horse and odds_raw:
                    fusion_map.setdefault(race, {})[horse] = self.fractional_to_decimal(odds_raw)

            if not fusion_map:
                logger.warning("⚠️ OC returned 0 races")
                return {}

            logger.info(f"✅ OC: {len(fusion_map)} races")
            return fusion_map

        except Exception as e:
            logger.warning(f"⚠️ OC error: {e}")
            return {}
