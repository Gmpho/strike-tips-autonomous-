import asyncio
import json
import logging
import sys
import os
import random
import time
from datetime import datetime
from difflib import get_close_matches
from typing import Dict, Optional, List, Any
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
    level=logging.DEBUG,
    format='%(asctime)s - [%(levelname)s] - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger("L7-Monitor")


class AdaptiveOddsMonitor:
    def __init__(self):
        self.events_cache = {}
        self.last_update = datetime.now()
        self.intel_cache = IntelligenceCacheManager(MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR)
        self.alert_engine = AlertEngine()
        self.human = HumanBehaviorSimulator()
        self.monitoring_active = True
        self.oc_state = {"odds": {}}

    async def initialize(self):
        await self.alert_engine.initialize()
        os.makedirs(BROWSER_PROFILE_DIR, exist_ok=True)
        # Rehydrate intelligence cache (survival across restarts)
        self.events_cache = self.intel_cache.rehydrate()

    async def _fetch_oc_odds_background(self):
        """Background task to fetch Oddschecker odds every 90 seconds (Staggered)."""
        oddschecker = OddscheckerScraper()
        # Stagger start to avoid initial CPU spike
        await asyncio.sleep(10)
        
        while self.monitoring_active:
            try:
                logger.info("🔭 Fusion Layer: Fetching Oddschecker prices...")
                odds = await oddschecker.get_latest_odds()
                if odds:
                    self.oc_state["odds"] = odds
                    logger.info(f"✅ Fusion Sync: Updated market snapshot with OC data.")
            except Exception as e:
                logger.warning(f"⚠️ Oddschecker fusion fetch failed: {e}")
            
            # Heavy pulse: 90 seconds
            await asyncio.sleep(90)

    async def stealth_fetch(self, page):
        """L7 Stealth Fetch: Executes JS-inline API calls to Betway endpoints."""
        script = """
        async () => {
            try {
                const urls = [
                    "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2",
                    "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetNextOff?sportId=horse-racing&take=20&isVirtual=false&marketType=Race%20Winner&marketGroupname=Race%20Winner&countryCode=ZA"
                ];
                
                const responses = await Promise.all(urls.map(u => fetch(u).then(r => r.json())));
                const daily = responses[0];
                const nextOff = responses[1];
                
                // Build price lookup map (handles both array and object formats)
                const allPrices = {};
                const processPrices = (prices) => {
                    if (Array.isArray(prices)) {
                        prices.forEach(p => { if (p.outcomeId) allPrices[p.outcomeId] = p; });
                    } else if (typeof prices === 'object' && prices !== null) {
                        Object.assign(allPrices, prices);
                    }
                };
                
                if (daily.prices) processPrices(daily.prices);
                if (nextOff.prices) processPrices(nextOff.prices);

                const events = {};
                
                const mapEvent = (event, region) => {
                    const details = event.raceEventDetails || event.details;
                    if (!details || !details.racers) return null;
                    
                    const raceName = event.name || event.displayName || "Unknown Race";
                    const raceTime = raceName.split(" ")[0];
                    
                    return {
                        id: event.eventId,
                        en: region ? `${region}: ${event.league}` : event.league,
                        course: event.league,
                        t: raceTime,
                        st: raceTime,
                        isFinished: event.isFinished,
                        raceNumber: (event.sportSpecificProperties && event.sportSpecificProperties.raceNumber) || "1",
                        runners: details.racers.map(r => {
                            const pId = (r.outcomeIds && r.outcomeIds[0]) || r.outcomeId;
                            const p = allPrices[pId];
                            
                            // High-fidelity price extraction
                            let odds = 'SP'; // Default to SP
                            if (p) {
                                odds = parseFloat(p.priceDecimal || p.decimalPrice || p.odds);
                                if (isNaN(odds)) odds = 'SP';
                            }
                            
                            return {
                                outcomeIds: r.outcomeIds || [pId],
                                name: r.outcomeName || r.name || "Unknown Horse",
                                jockeyName: r.jockeyName || "TBA",
                                trainerName: r.trainerName || "TBA",
                                age: r.age || "Unknown",
                                weight: r.weight || "0",
                                form: r.form || "",
                                number: r.number || "0",
                                starRating: r.starRating || 0,
                                draw: r.draw || 0,
                                timeForm: r.timeForm || "",
                                outcomeName: r.outcomeName || r.name || "",
                                odds: odds,
                                outcomeId: pId
                            };
                        })
                    };
                };

                // Process regional/daily races
                if (daily.regions) {
                    daily.regions.forEach(reg => {
                        if (reg.sportEvents) {
                            reg.sportEvents.forEach(e => {
                                const mapped = mapEvent(e, reg.name);
                                if (mapped) events[e.eventId] = mapped;
                            });
                        }
                    });
                }
                
                // Process 'Next Off' races
                if (nextOff.events) {
                    nextOff.events.forEach(e => {
                        if (!events[e.eventId]) {
                            const mapped = mapEvent(e);
                            if (mapped) events[e.eventId] = mapped;
                        }
                    });
                } else if (nextOff.sportEvents) {
                    nextOff.sportEvents.forEach(e => {
                        if (!events[e.eventId]) {
                            const mapped = mapEvent(e);
                            if (mapped) events[e.eventId] = mapped;
                        }
                    });
                }

                // EVENT-DEEP-DIVE: If runners have missing prices (odds: 'SP'), fetch specific event details
                const findMissing = (evs) => Object.values(evs).filter(e => e.runners.some(r => r.odds === 'SP')).slice(0, 30);
                const missing = findMissing(events);
                
                if (missing.length > 0) {
                    const eventResults = await Promise.all(
                        missing.map(e => 
                            fetch(`https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventId=${e.id}&marketType=Race%20Winner&marketGroupname=Race%20Winner&isVirtual=false&countryCode=ZA`)
                            .then(r => r.json())
                            .catch(() => null)
                        )
                    );
                    
                    eventResults.forEach(res => {
                        if (res && res.prices) {
                            processPrices(res.prices);
                            // Re-map the specific event now that we have its prices
                            const rawEventDaily = daily.regions ? daily.regions.flatMap(r => r.sportEvents || []) : [];
                            const rawEventNext = nextOff.events || nextOff.sportEvents || [];
                            const rawEvent = rawEventDaily.find(e => e.eventId === res.eventId) || 
                                             rawEventNext.find(e => e.eventId === res.eventId);
                            if (rawEvent) {
                                const mapped = mapEvent(rawEvent, "DeepDive");
                                if (mapped) events[res.eventId] = mapped;
                            }
                        }
                    });
                }

                const active = Object.fromEntries(
                    Object.entries(events)
                        .filter(([_, v]) => !v.isFinished)
                        .sort((a, b) => a[1].t.localeCompare(b[1].t))
                );
                
                return { events: active, count: Object.keys(active).length, status: "online" };
            } catch (e) {
                return { status: "error", error: e.message };
            }
        }
        """
        try:
            # Ghost Move before fetch
            if random.random() < 0.2:
                await self.human.scroll_naturally(page)
                
            state = await page.evaluate(script)
            if state.get("status") == "error":
                raise Exception(state["error"])
            return state
        except Exception as e:
            logger.warning(f"⚠️ Ghost Scraper throttled: {e}")
            return {"status": "throttled"}

    def save_snapshot(self, state):
        """Atomic persist logic."""
        try:
            tmp = f"{MARKET_SNAPSHOT_PATH}.tmp"
            with open(tmp, "w") as f:
                json.dump(state, f, indent=2)
            os.rename(tmp, MARKET_SNAPSHOT_PATH)
        except Exception as e:
            logger.error(f"❌ Snapshot persistence error: {e}")

    async def inject_stealth(self, page):
        """Deep Masking Tier: Human-like browser fingerprints."""
        try:
            await page.add_init_script("""
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                  if (parameter === 37445) return 'Intel Open Source Technology Center';
                  if (parameter === 37446) return 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)';
                  return getParameter(parameter);
                };
            """)
            await page.add_init_script("Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });")
            await page.add_init_script("Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 4 });")
            logger.info("🛡️ Stealth Identity: Fingerprint Masking Active.")
        except Exception as e:
            logger.warning(f"⚠️ Stealth Jitter: {e}")

    async def run(self):
        await self.initialize()
        logger.info("🚀 L7 Ghost Monitor Active (V1 Fusion Logic - Betway Internal APIs)")
        
        # Start Fusion Layer (Oddschecker)
        asyncio.create_task(self._fetch_oc_odds_background())
        
        async with async_playwright() as p:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=BROWSER_PROFILE_DIR,
                headless=True,
                args=CHROME_ARGS,
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            
            page = context.pages[0] if context.pages else await context.new_page()
            await self.inject_stealth(page)
            await page.add_init_script(STEALTH_JS)
            
            # Navigate to base page to set origin/cookies
            try:
                await page.goto("https://www.betway.co.za/sport/horse-racing", wait_until="commit", timeout=60000)
            except Exception as e:
                logger.warning(f"⚠️ Initial Betway navigation timeout, continuing anyway: {e}")
            
            while self.monitoring_active:
                try:
                    logger.info("📡 Ghost Sync: Fetching Internal Betway APIs...")
                    state = await self.stealth_fetch(page)
                    
                    if state.get("status") == "online":
                        state["timestamp"] = datetime.now().isoformat()
                        
                        # Merge Oddschecker odds safely using Fuzzy Matching (Fusion Layer)
                        oc_data = self.oc_state.get("odds", {})
                        events = state.get("events") or {}

                        if oc_data:
                            oc_races = list(oc_data.keys())
                            for event_id, event in events.items():
                                race_name = event.get("en", "")
                                clean_race_name = race_name.split(":")[-1].strip()
                                
                                # Fuzzy match race
                                race_match = get_close_matches(clean_race_name, oc_races, n=1, cutoff=0.5)
                                if race_match:
                                    race_oc_odds = oc_data[race_match[0]]
                                    oc_horses = list(race_oc_odds.keys())

                                    for runner in event.get("runners", []):
                                        horse_name = runner["name"]
                                        horse_match = get_close_matches(horse_name, oc_horses, n=1, cutoff=0.5)
                                        if horse_match:
                                            # Average the odds for better baseline or prefer OC if available
                                            runner["odds"] = float(race_oc_odds[horse_match[0]])
                                            runner["provider"] = "Fusion (Betway + OC)"

                    self.save_snapshot(state)
                    logger.info(f"👻 Ghost Pulse: Synchronized {state['count']} Active Races.")
                    
                    # Intelligence Baseline Sync (Keep history for AlertEngine)
                    active_ids = list(events.keys())
                    for event_id, event in events.items():
                        self.intel_cache.update_baseline(event_id, event.get("runners", []))
                    
                    # Periodic Pruning (Clean up finished races from disk)
                    self.intel_cache.prune_stale_data(active_ids)
                    
                    # Intelligence Evaluation
                    for event_id, event in events.items():
                        await self.alert_engine.evaluate_odds_update(event, cache=self.intel_cache)

                except Exception as e:
                    logger.warning(f"⚠️ Flicker (Recovering): {e}")
                
                # Fast pulse: 20 seconds (staggered from heavy OC pulse)
                await asyncio.sleep(20)

if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    try:
        asyncio.run(monitor.run())
    except KeyboardInterrupt:
        logger.info("🛑 Ghost Monitor deactivated.")
