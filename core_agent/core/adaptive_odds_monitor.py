import asyncio
import json
import logging
import os
import sys
import difflib
from datetime import datetime

from core_agent.config.paths import MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR
from core_agent.core.alert_engine import AlertEngine
from core_agent.skills.parsers.betway_api import BetwayAPI
from core_agent.skills.parsers.oddschecker_scraper import OddscheckerScraper
from core_agent.core.intelligence_cache_manager import IntelligenceCacheManager

HEALING_EVENTS_PATH = os.path.join("data", "healing_events.json")


def _write_healing_event(action: str, details: str, agent: str = "OddsMonitor", status: str = "SUCCESS"):
    """Append a healing event to the shared log file."""
    try:
        events = []
        if os.path.exists(HEALING_EVENTS_PATH):
            with open(HEALING_EVENTS_PATH) as f:
                events = json.load(f)
        events.append({
            "id": f"{action.lower()}-{int(datetime.now().timestamp())}",
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "details": details,
            "agent": agent,
            "status": status,
        })
        with open(HEALING_EVENTS_PATH, "w") as f:
            json.dump(events[-50:], f, indent=2)  # keep last 50
    except Exception:
        pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("L7-Monitor")


class AdaptiveOddsMonitor:
    def __init__(self):
        self.intel_cache = IntelligenceCacheManager(
            MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR
        )
        self.alert_engine = AlertEngine()
        self.betway = BetwayAPI()
        self.oc_scraper = OddscheckerScraper()

        self.monitoring_active = True
        self.oc_state = {"odds": {}}

    async def initialize(self):
        await self.alert_engine.initialize()
        self.events_cache = self.intel_cache.rehydrate()

    async def _fetch_oc_odds_loop(self):
        """Fetch Oddschecker best odds periodically (lightweight httpx, no browser)."""
        while self.monitoring_active:
            try:
                odds = await self.oc_scraper.get_latest_odds()
                if odds:
                    self.oc_state["odds"] = odds
            except Exception as e:
                logger.warning(f"⚠️ OC fetch error: {e}")
            await asyncio.sleep(300)

    async def run(self):
        await self.initialize()
        # Start Oddschecker in background
        asyncio.create_task(self._fetch_oc_odds_loop())

        logger.info("🚀 L7 Monitor Active (Refactored: Pure Python Mode)")

        while self.monitoring_active:
            try:
                # 1. Fetch Betway Snapshot (using TrackRacing/TAB API)
                state = await self.betway.get_snapshot_format()

                # 2. Merge Oddschecker odds for value analysis
                oc_odds = self.oc_state.get("odds", {})
                if oc_odds:
                    # Flatten OC odds for easier matching
                    flat_oc_odds = {}
                    for oc_race, oc_horses in oc_odds.items():
                        flat_oc_odds.update(oc_horses)

                    for eid, e in state.get("events", {}).items():
                        for r in e.get("runners", []):
                            horse_name = r.get("name", "")
                            # Try exact match
                            if horse_name in flat_oc_odds:
                                r["odds"] = flat_oc_odds[horse_name]
                            else:
                                # Try fuzzy match
                                matches = difflib.get_close_matches(
                                    horse_name.lower(),
                                    [h.lower() for h in flat_oc_odds.keys()],
                                    n=1,
                                    cutoff=0.8,
                                )
                                if matches:
                                    matched_key = next(
                                        (
                                            k
                                            for k in flat_oc_odds.keys()
                                            if k.lower() == matches[0]
                                        ),
                                        None,
                                    )
                                    if matched_key:
                                        r["odds"] = flat_oc_odds[matched_key]

                # 3. Persistence & Pruning
                # Remove finished races and normalize names
                state["events"] = {
                    eid: {**e, "en": " ".join(e.get("en", "").split())}
                    for eid, e in state.get("events", {}).items()
                    if not e.get("isFinished")
                }
                state["count"] = len(state["events"])
                state["timestamp"] = datetime.now().isoformat()

                with open(MARKET_SNAPSHOT_PATH, "w") as f:
                    json.dump(state, f, indent=2)

                active_ids = list(state["events"].keys())

                # Update Intelligence Cache for AlertEngine baselines
                for event_id in active_ids:
                    self.intel_cache.update_baseline(
                        event_id, state["events"][event_id].get("runners", [])
                    )

                # Prune old data
                self.intel_cache.prune_stale_data(active_ids)

                logger.info(
                    f"👻 Synchronized {state.get('count')} races ({len(active_ids)} active)."
                )

                # Write healing event for this sync
                _write_healing_event(
                    action="SYNC_COMPLETE",
                    details=f"Synchronized {state.get('count')} races across {len(set(e.get('en','').split(':')[0].strip() for e in state['events'].values()))} regions.",
                    agent="OddsMonitor",
                )

                # 4. Alert Evaluation
                for event in state.get("events", {}).values():
                    await self.alert_engine.evaluate_odds_update(
                        event, cache=self.intel_cache
                    )

            except Exception as e:
                logger.warning(f"⚠️ Sync error: {e}")
                import traceback

                logger.debug(traceback.format_exc())

            await asyncio.sleep(45)


if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    asyncio.run(monitor.run())
