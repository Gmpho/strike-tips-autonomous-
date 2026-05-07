"""
Market Watcher - Real-time Sentry for Strike Tips.
Filters incoming market data and triggers deep AI analysis only when odds move significantly.
"""

import asyncio
import logging
from typing import Dict, List
from core_agent.core.strike_tips import StrikeTips

logger = logging.getLogger("market-watcher")


class MarketWatcher:
    def __init__(self, strike: StrikeTips):
        self.strike = strike
        self.last_snapshots: Dict[str, Dict] = {}
        self.threshold = 0.05  # 5% odds movement trigger

    async def _is_interesting(self, track: str, new_snapshot: Dict) -> bool:
        """Sentry Tier: Fast if/then logic to filter market noise."""
        old_snapshot = self.last_snapshots.get(track)
        if not old_snapshot:
            self.last_snapshots[track] = new_snapshot
            return False

        # Example logic: check for significant odds shifts
        # You can expand this with more complex price-action triggers
        return True  # Placeholder: triggers on any update for testing

    async def watch(self):
        """Continuous monitor loop."""
        logger.info("[WATCHER] Sentry active. Monitoring market...")
        while True:
            try:
                # 1. Fetch live snapshot
                current_market = await self.strike.get_odds_snapshot()

                # 2. Sentry filter per track
                for track, data in current_market.items():
                    if await self._is_interesting(track, data):
                        logger.info(
                            f"[SENTRY] Interesting movement on {track}. Waking Analyst."
                        )

                        # 3. Deep Tier: Wake MAF Specialist
                        analysis = await self.strike.evaluate_race(track, race_number=1)

                        # 4. Notify via Telegram if value found
                        if analysis.get("status") == "VALUE_FOUND":
                            await self.strike.telegram.send_message(
                                f"🎯 Value Found: {track} Race 1! Edge: {analysis['top_selection']['edge_percent']}%"
                            )

                self.last_snapshots = current_market
                await asyncio.sleep(30)  # Monitor frequency

            except Exception as e:
                logger.error(f"[WATCHER] Error: {e}")
                await asyncio.sleep(60)
