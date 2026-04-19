import logging
import asyncio
import json
from typing import Dict, List, Optional
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

logger = logging.getLogger("oddschecker-scraper")

class OddscheckerScraper:
    """Production-grade scraper for Oddschecker using Crawl4AI."""
    URL = "https://www.oddschecker.com/horse-racing/today"

    def __init__(self):
        # Optimized configuration for CPU efficiency (as per crawl4ai config set.md)
        self.browser_conf = BrowserConfig(
            headless=True,
            light_mode=True,
            enable_stealth=True,
            text_mode=True,  # No images/heavy assets
            viewport_width=1280,
            viewport_height=720
        )
        
        # Schema for Oddschecker horse racing - Using more robust selectors
        self.schema = {
            "name": "OddscheckerRaces",
            "baseSelector": "tr.event-row, .runner-row, div.all-odds-click",
            "fields": [
                {"name": "horse_name", "selector": "a.runner-name, .horse-name, .name", "type": "text"},
                {"name": "fractional_odds", "selector": "span.odds, .odds-value, .price", "type": "text"},
                {"name": "race_name", "selector": "div.race-details h3, .event-name", "type": "text"}
            ]
        }
        self.extraction_strategy = JsonCssExtractionStrategy(self.schema)

    @staticmethod
    def fractional_to_decimal(fraction_str: str) -> float:
        """Utility to convert '9/4' -> 3.25"""
        try:
            if not fraction_str or not isinstance(fraction_str, str):
                return 5.0
            fraction_str = fraction_str.strip()
            if '/' in fraction_str:
                num, den = map(int, fraction_str.split('/'))
                return round((num / den) + 1.0, 2)
            if 'EVS' in fraction_str.upper():
                return 2.0
            return float(fraction_str)
        except:
            return 5.0

    async def get_latest_odds(self) -> Dict:
        """Fetch and parse live odds using Crawl4AI with high resilience."""
        run_conf = CrawlerRunConfig(
            extraction_strategy=self.extraction_strategy,
            cache_mode=CacheMode.BYPASS,
            # Use domcontentloaded for more reliability on heavy JS pages
            wait_until="domcontentloaded",
            page_timeout=90000,
            delay_before_return_html=5.0, # Increased delay for JS rendering
            # Ensure the table is present before extracting
            wait_for="css:tr.event-row, .runner-row"
        )

        try:
            async with AsyncWebCrawler(config=self.browser_conf) as crawler:
                logger.info(f"🕸️ Crawl4AI: Pulse fired at {self.URL}")
                result = await crawler.arun(url=self.URL, config=run_conf)
                
                if not result.success:
                    logger.warning(f"⚠️ Crawl4AI failed: {result.error_message}")
                    return {}

                logger.debug(f"🔍 Raw Extracted Content: {result.extracted_content[:500]}")
                raw_data = json.loads(result.extracted_content or "[]")
                
                # Fusion formatting: { race_name: { horse_name: decimal_odds } }
                fusion_map = {}
                for item in raw_data:
                    race = item.get("race_name", "Unknown Race")
                    horse = item.get("horse_name")
                    odds_raw = item.get("fractional_odds")
                    
                    if horse and odds_raw:
                        if race not in fusion_map:
                            fusion_map[race] = {}
                        fusion_map[race][horse] = self.fractional_to_decimal(odds_raw)

                logger.info(f"✅ Crawl4AI Success: Found {len(fusion_map)} races on Oddschecker.")
                return fusion_map

        except Exception as e:
            logger.error(f"❌ Crawl4AI Execution Error: {e}")
            return {}
