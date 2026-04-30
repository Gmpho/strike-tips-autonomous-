import asyncio
import json
import logging
import sys
import os
import random
from datetime import datetime
from playwright.async_api import async_playwright

from core_agent.config.paths import MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR
from core_agent.core.alert_engine import AlertEngine
from core_agent.core.human_behavior import HumanBehaviorSimulator
from core_agent.skills.parsers.oddschecker_scraper import OddscheckerScraper
from core_agent.core.intelligence_cache_manager import IntelligenceCacheManager


# Persistent Identity Layer
BROWSER_PROFILE_DIR = "/app/data/browser_profile"

# User's Gold Standard Stealth JS
STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
window.chrome = { runtime: {} };
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
"""

CHROME_ARGS = [
    '--disable-blink-features=AutomationControlled',
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-infobars',
    '--ignore-certificate-errors',
    '--disable-gpu',
    '--disable-software-rasterizer',
    '--disable-extensions',
    '--disable-plugins',
    '--disable-images',
    '--blink-settings=imagesEnabled=false',
    '--disable-background-networking',
    '--disable-sync'
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("L7-Monitor")

class AdaptiveOddsMonitor:
    def __init__(self):
        self.intel_cache = IntelligenceCacheManager(MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR)
        self.alert_engine = AlertEngine()
        self.human = HumanBehaviorSimulator()
        
        self.monitoring_active = True
        self.oc_state = {"odds": {}}

    async def initialize(self):
        await self.alert_engine.initialize()
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
        self.events_cache = self.intel_cache.rehydrate()

    async def _fetch_oc_odds_loop(self):
        """Task to fetch Oddschecker odds."""
        scraper = OddscheckerScraper()
        while self.monitoring_active:
            try:
                odds = await scraper.get_latest_odds()
                if odds:
                    self.oc_state["odds"] = odds
            except Exception as e:
                logger.warning(f"⚠️ OC fetch error: {e}")
            await asyncio.sleep(90)

    async def stealth_fetch(self, page):
        """Executes JS-inline API calls."""
        # Note: This uses a simplified script structure for cleaner integration
        script = """
        async () => {
            const urls = [
                "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2",
                "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetNextOff?sportId=horse-racing&take=20&isVirtual=false&marketType=Race%20Winner&marketGroupname=Race%20Winner&countryCode=ZA"
            ];
            const responses = await Promise.all(urls.map(u => fetch(u).then(r => r.json())));
            const daily = responses[0];
            const nextOff = responses[1];
            
            const allPrices = {};
            const process = (p) => {
                if (Array.isArray(p)) p.forEach(item => { if (item.outcomeId) allPrices[item.outcomeId] = item; });
                else if (typeof p === 'object') Object.assign(allPrices, p);
            };
            if (daily.prices) process(daily.prices);
            if (nextOff.prices) process(nextOff.prices);

            const events = {};
            const mapEvent = (e) => {
                const det = e.raceEventDetails || e.details;
                if (!det || !det.racers) return null;
                return {
                    id: e.eventId,
                    en: e.league,
                    t: (e.name || "Unknown").split(" ")[0],
                    runners: det.racers.map(r => ({
                        name: r.outcomeName || r.name,
                        odds: (allPrices[r.outcomeId] && allPrices[r.outcomeId].priceDecimal) || 'SP'
                    }))
                };
            };
            
            (daily.regions || []).forEach(r => (r.sportEvents || []).forEach(e => {
                const m = mapEvent(e);
                if (m) events[m.id] = m;
            }));
            
            return { events, count: Object.keys(events).length };
        }
        """
        return await page.evaluate(script)

    async def run(self):
        await self.initialize()
        asyncio.create_task(self._fetch_oc_odds_loop())
        
        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                BROWSER_PROFILE_DIR, headless=True, args=CHROME_ARGS
            )
            page = ctx.pages[0] if ctx.pages else await ctx.new_page()
            await page.add_init_script(STEALTH_JS)
            
            while self.monitoring_active:
                try:
                    state = await self.stealth_fetch(page)
                    # Simple persist for now
                    with open(MARKET_SNAPSHOT_PATH, "w") as f:
                        json.dump(state, f)
                    logger.info(f"👻 Synchronized {state.get('count')} races.")
                except Exception as e:
                    logger.warning(f"⚠️ Sync error: {e}")
                await asyncio.sleep(20)

if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    asyncio.run(monitor.run())
