import logging
import asyncio
import random
from crawl4ai import AsyncWebCrawler
from typing import Dict, List, Optional
from bs4 import BeautifulSoup

logger = logging.getLogger("oddschecker-scraper")

class OddscheckerScraper:
    """Scraper for Oddschecker using Crawl4AI for structured extraction."""
    URL = "https://www.oddschecker.com/horse-racing/today"

    def __init__(self):
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        ]

    @staticmethod
    def fractional_to_decimal(fraction_str: str) -> float:
        try:
            if '/' in fraction_str:
                num, den = map(int, fraction_str.split('/'))
                return round((num / den) + 1.0, 2)
            return float(fraction_str)
        except:
            return 5.0

    async def get_latest_odds(self) -> Dict:
        """Fetch all odds and group them by race/track for exact matching."""
        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(
                    url=self.URL,
                    js_code="""
                        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                        window.navigator.chrome = { runtime: {} };
                        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                    """,
                    css_selector='.border-wrap',
                    timeout=30000 
                )
                
                if not result or not result.html:
                    return {}

                soup = BeautifulSoup(result.html, 'html.parser')
                
                odds_map = {} # { "Race Context": { "Horse": Odds } }
                
                for c in soup.select('.border-wrap'):
                    name_el = c.select_one('.beta-callout')
                    odds_el = c.select_one('.odds.basket-add')
                    # Look for the race title in a more robust way
                    race_el = c.find_previous(class_='race-header') or c.find_previous(class_='event-title') or c.find_parent().find_previous(class_='event-title')
                    
                    if name_el and odds_el:
                        race_context = race_el.text.strip() if race_el else "Unknown Race"
                        # Clean up common debris in race titles
                        race_context = race_context.replace('\n', ' ').strip()
                        if race_context not in odds_map:
                            odds_map[race_context] = {}
                        
                        odds_map[race_context][name_el.text.strip()] = self.fractional_to_decimal(odds_el.text.strip())
                return odds_map
        except Exception:
            # Silent fail to keep monitor logs clean
            return {}
