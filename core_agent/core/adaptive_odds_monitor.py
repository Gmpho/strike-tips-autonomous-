"""
Strike Tips - Adaptive Odds Monitor (L7 Ghost Edition)
Virtually undetectable scraping using fingerprint masking and human behavior simulation.
Strict Purge logic for finished races + Stealth Browser Piggybacking.
"""
import asyncio
import time
import json
import os
import random
import math
from datetime import datetime
from difflib import get_close_matches
from typing import Dict, Optional
from playwright.async_api import async_playwright
from core_agent.skills.parsers.oddschecker_scraper import OddscheckerScraper

# Use specialized stealth
try:
    from playwright_stealth import stealth_async
except ImportError:
    stealth_async = None

# Import performance tracker
try:
    from performance_tracker import tracker
except ImportError:
    tracker = None

class AdaptiveOddsMonitor:
    def __init__(self, data_dir: Optional[str] = None):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.data_dir = data_dir or os.path.join(base_dir, "data")
        self.monitoring_active = True
        self.error_count = 0
        self.browser_lock = asyncio.Lock()  # Prevent simultaneous scraping
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ]
        
    def match_horse(self, name, oc_list):
        names = [o.get("horse") for o in oc_list if o.get("horse")]
        match = get_close_matches(name, names, n=1, cutoff=0.5)
        if match:
            return next((o for o in oc_list if o["horse"] == match[0]), None)
        return None
        
    async def simulate_human(self, page):
        """Ghost Protocol: Perform subtle, non-intrusive human actions."""
        try:
            # Random subtle scroll
            scroll_amt = random.randint(100, 400)
            await page.mouse.wheel(0, scroll_amt)
            await asyncio.sleep(random.uniform(0.5, 1.5))
            await page.mouse.wheel(0, -scroll_amt)
            
            # Random mouse move
            width, height = 1920, 1080
            await page.mouse.move(random.randint(0, width), random.randint(0, height))
        except:
            pass

    async def stealth_fetch(self, page) -> Dict:
        """L7 Stealth: JS-Context Fetching with dynamic headers."""
        async with self.browser_lock:
            script = """
            async () => {
                const fetchConfig = {
                    headers: {
                        "sec-ch-ua": '"Chromium";v="122", "Not(A:Brand";v="24", "Google Chrome";v="122"',
                        "sec-ch-ua-mobile": "?0",
                        "sec-ch-ua-platform": '"Windows"',
                        "X-Requested-With": "XMLHttpRequest"
                    }
                };
                
                const urls = [
                    "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetDaily?sportId=horse-racing&period=Today&isVirtual=false&countryCode=ZA&timeZoneOffset=2",
                    "https://www.betway.co.za/sportsapi/v1/TrackRacing/GetNextOff?sportId=horse-racing&take=20&isVirtual=false&marketType=Race%20Winner&marketGroupname=Race%20Winner&countryCode=ZA"
                ];
                
                try {
                    const results = await Promise.all(urls.map(url => fetch(url, fetchConfig).then(r => r.json())));
                    const daily = results[0] || { regions: [] };
                    const nextOff = results[1] || { events: [], prices: [] };
                    
                    const saEvents = [];
                    daily.regions?.forEach(reg => {
                        if (reg.name.toLowerCase().includes('south africa')) {
                            reg.sportEvents?.forEach(e => {
                                if (!e.isFinished) saEvents.push(e.eventId);
                            });
                        }
                    });
                    
                    const eventResults = await Promise.all(
                        saEvents.slice(0, 10).map(id => 
                            fetch(`https://www.betway.co.za/sportsapi/v1/TrackRacing/GetEvent?eventId=${id}&marketType=Race%20Winner&marketGroupname=Race%20Winner&isVirtual=false&countryCode=ZA`, fetchConfig)
                            .then(r => r.json())
                            .catch(() => null)
                        )
                    );

                    const safePrices = (p) => {
                        const obj = {};
                        if (Array.isArray(p)) {
                            p.forEach(price => {
                                if (price.outcomeId) obj[price.outcomeId] = price;
                            });
                        } else if (p && typeof p === 'object') {
                            Object.assign(obj, p);
                        }
                        return obj;
                    };

                    let allPrices = { ...safePrices(daily.prices), ...safePrices(nextOff.prices) };
                    eventResults.forEach(er => {
                        if (er?.result?.prices) {
                            allPrices = { ...allPrices, ...safePrices(er.result.prices) };
                        }
                    });
                    const events = {};
                    
                    const mapEvent = (event, region) => {
                        if (!event.raceEventDetails?.racers) return null;
                        return {
                            id: event.eventId,
                            en: `${region || "International"}: ${event.league}`,
                            t: event.name.split(" ")[0],
                            st: event.name.split(" ")[0],
                            isFinished: event.isFinished,
                            raceNumber: event.sportSpecificProperties?.raceNumber || "1",
                            runners: event.raceEventDetails.racers.map(r => {
                                const p = allPrices[r.outcomeIds[0]];
                                return {
                                    name: r.outcomeName || r.name || "Unknown Horse",
                                    jockey: r.jockeyName,
                                    trainer: r.trainerName,
                                    draw: r.draw,
                                    odds: (p?.priceDecimal || p?.decimalPrice) ? parseFloat(p.priceDecimal || p.decimalPrice) : 5.0
                                };
                            })
                        };
                    };

                    daily.regions?.forEach(reg => {
                        reg.sportEvents?.forEach(e => {
                            const mapped = mapEvent(e, reg.name);
                            if (mapped) events[e.eventId] = mapped;
                        });
                    });
                    
                    nextOff.events?.forEach(e => {
                        if (!events[e.eventId]) {
                            const mapped = mapEvent(e);
                            if (mapped) events[e.eventId] = mapped;
                        }
                    });

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
            start_time = time.time()
            try:
                # Ghost Move before fetch
                if random.random() < 0.3:
                    await self.simulate_human(page)
                    
                state = await page.evaluate(script)
                if state.get("status") == "error":
                    raise Exception(state["error"])
                    
                if tracker:
                    tracker.track_request("Ghost_Stealth_Fetch", time.time() - start_time, 0.0, True)
                return state
            except Exception as e:
                if tracker:
                    tracker.track_request("Ghost_Stealth_Fetch", time.time() - start_time, 0.0, False)
                print(f"[WARN] Ghost Scraper throttled: {e}")
                return {"status": "throttled"}

    async def _fetch_oc_odds_background(self, oddschecker, state_container):
        """Background task to fetch OC odds every 20 minutes."""
        while self.monitoring_active:
            try:
                odds = await oddschecker.get_latest_odds()
                if odds:
                    state_container["odds"] = odds
                    print(f"[OC] Successfully updated market snapshot with {len(odds)} prices.")
            except Exception as e:
                print(f"[WARN] Oddschecker background fetch failed: {e}")
            await asyncio.sleep(1200) # Poll every 20 minutes

    async def monitor_loop(self):
        print(f"👻 Ghost Scraper Active - Persistent Browser Mode Engaging...")
        oddschecker = OddscheckerScraper()
        oc_state = {"odds": []}
        asyncio.create_task(self._fetch_oc_odds_background(oddschecker, oc_state))
        
        async with async_playwright() as p:
            # Ghost hardware profiles - Randomize initial fingerprint
            ua = random.choice(self.user_agents)
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context(
                user_agent=ua,
                viewport={'width': random.randint(1366, 1920), 'height': random.randint(768, 1080)},
                device_scale_factor=random.choice([1, 2]),
                locale=random.choice(['en-ZA', 'en-US', 'en-GB'])
            )
            page = await context.new_page()
            
            # Apply L7 Stealth Patches
            if stealth_async:
                await stealth_async(page)
            
            await page.goto("https://www.betway.co.za/sport/horse-racing", wait_until="domcontentloaded")
            
            while self.monitoring_active:
                try:
                    state = await self.stealth_fetch(page)
                    
                    if state.get("status") == "online":
                        state["timestamp"] = datetime.now().isoformat()
                        
                        # Merge OC odds safely using Fuzzy Matching
                        oc_data = oc_state.get("odds", {})
                        events = state.get("events") or {}

                        if oc_data:
                            # Extract OC race names
                            oc_races = list(oc_data.keys())

                            for event_id, event in events.items():
                                race_name = event.get("en", "")
                                # Pre-process race name to strip regional prefixes for better matching
                                # e.g. "International: Ireland: Dundalk" -> "Dundalk"
                                clean_race_name = race_name.split(":")[-1].strip()
                                
                                # Fuzzy match race
                                race_match = get_close_matches(clean_race_name, oc_races, n=1, cutoff=0.5)
                                if race_match:
                                    race_oc_odds = oc_data[race_match[0]]
                                    oc_horses = list(race_oc_odds.keys())

                                    for runner in event.get("runners", []):
                                        horse_name = runner["name"]
                                        # Fuzzy match horse with lower cutoff for international name variations
                                        horse_match = get_close_matches(horse_name, oc_horses, n=1, cutoff=0.5)
                                        if horse_match:
                                            runner["odds"] = float(race_oc_odds[horse_match[0]])
                                            runner["provider"] = "Oddschecker"
                                            print(f"[FUSION] Matched '{horse_name}' at '{clean_race_name}'")

                        print(f"👻 [{datetime.now().strftime('%H:%M:%S')}] Ghost Sync: {state['count']} Active Races.")                        
                        from core_agent.config.paths import MARKET_SNAPSHOT_PATH
                        with open(MARKET_SNAPSHOT_PATH, "w") as f:
                            json.dump(state, f, indent=2)
                        self.error_count = 0
                except Exception as e:
                    print(f"[ERR] Monitor Loop error: {e}")
                
                await asyncio.sleep(random.uniform(20, 30))
            
            await browser.close()

if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    try:
        asyncio.run(monitor.monitor_loop())
    except KeyboardInterrupt:
        print("\n[STOP] Ghost Scraper deactivated.")
