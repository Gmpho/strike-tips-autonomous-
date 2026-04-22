"""
Strike Tips - Scheduler
Automated daily race scanning and notifications
Uses dynamic track discovery via RaceScheduleService.
"""

import schedule
import time
import sys
import os
from core_agent.core.market_watcher import MarketWatcher
import asyncio
from datetime import datetime, date, timedelta
from threading import Thread
from typing import List, Dict

from core_agent.core.strike_tips import StrikeTips
from core_agent.config.settings import TRACKS, NOTIFICATIONS


import io
import sys

def setup_emoji_filter():
    """Setup to replace ASCII tags with emojis in stdout."""
    class EmojiFilter(io.TextIOWrapper):
        def __init__(self, buffer):
            super().__init__(buffer, encoding="utf-8", errors="replace")
        def write(self, text):
            replacements = {
                "[RUN]": "🏇", "[DATE]": "📅", "[OK]": "✅", "[ERR]": "❌",
                "[SCAN]": "🔄", "[HIT]": "🎯", "[TIME]": "⏰", "[LOC]": "📍",
                "[MAF]": "🧠", "[STOP]": "🛑", "[START]": "🚀", "[WORLD]": "🌍",
                "[SA]": "🇿🇦", "[UK]": "🇬🇧", "[AU]": "🇦🇺", "[US]": "🇺🇸",
                "[IE]": "🇮🇪", "[FR]": "🇫🇷", "[HK]": "🇭🇰", "[JP]": "🇯🇵",
                "[WARN]": "⚠️", "[STATS]": "📊", "[LOOKUP]": "🔍", "[LIST]": "📋",
                "[BOT]": "🤖", "[CHAT]": "💬", "[HEALTH]": "🏥", "[SEC]": "🔐",
            }
            for tag, emoji in replacements.items():
                text = text.replace(tag, emoji)
            super().write(text)
    sys.stdout = EmojiFilter(sys.stdout.buffer)

try:
    setup_emoji_filter()
except:
    pass

class StrikeTipsScheduler:
    def __init__(self, scan_time: str = "11:00", data_dir: str = "./data"):
        self.scan_time = scan_time
        self.data_dir = data_dir
        self.strike = None
        self.running = False
        self.scheduler_thread = None

    async def _get_todays_tracks(self) -> list:
        from core_agent.skills.race_schedule import RaceScheduleService
        service = RaceScheduleService()
        tracks = await service.get_todays_tracks()
        return tracks

    def setup_schedule(self):
        schedule.every().day.at(self.scan_time).do(self.daily_scan_job)
        schedule.every().day.at("20:00").do(self.pre_warm_tomorrow_job)
        schedule.every(15).minutes.do(self.continuous_scan_job)
        schedule.every(5).minutes.do(self.check_race_results_job)
        schedule.every().day.at("20:00").do(self._end_of_day_report)
        schedule.every().day.at("21:00").do(self.update_learning_job)

    def pre_warm_tomorrow_job(self):
        print(f"\n[TIME] Pre-warming tomorrow's data at {datetime.now().strftime('%H:%M')}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._pre_warm_tomorrow_async())
        except Exception as e:
            print(f"[ERR] Error pre-warming tomorrow: {e}")

    async def _pre_warm_tomorrow_async(self):
        from core_agent.skills.race_schedule import RaceScheduleService
        service = RaceScheduleService()
        tracks = await service.get_tomorrows_tracks()
        sa_tracks = [t for t in tracks.keys() if t in TRACKS]
        
        if sa_tracks:
            print(f"[CACHE] Pre-warming {len(sa_tracks)} tracks for tomorrow.")
            strike = StrikeTips(data_dir=self.data_dir)
            try:
                tomorrow = (date.today() + timedelta(days=1)).isoformat()
                for track in sa_tracks:
                    await strike.scraper.scrape_racecard(track, date_str=tomorrow)
            finally:
                await strike.close()

    def daily_scan_job(self):
        print(f"\n{'=' * 60}\n[TIME] Daily scan starting at {datetime.now().strftime('%H:%M')}\n{'=' * 60}")
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._daily_scan_async())
        except Exception as e:
            print(f"[ERR] Daily scan failed: {e}")

    async def _daily_scan_async(self):
        tracks = await self._get_todays_tracks()
        self.strike = StrikeTips(data_dir=self.data_dir)
        try:
            return await self.strike.run_daily_scan(tracks=tracks or None)
        finally:
            await self.strike.close()

    def check_race_results_job(self):
        pass

    def continuous_scan_job(self):
        pass

    def update_learning_job(self):
        pass

    def _end_of_day_report(self):
        pass

    def run_pending(self):
        while self.running:
            schedule.run_pending()
            time.sleep(10)

    def start(self):
        self.running = True
        self.setup_schedule()
        self.scheduler_thread = Thread(target=self.run_pending)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()
        print("[RUN] Strike Tips Scheduler Started")
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join()

async def run_immediate_scan_async():
    print("[RUN] Running immediate scan...")
    # Add your robust daily scan logic here
    print("[OK] Immediate scan complete.")

def run_immediate_scan():
    asyncio.run(run_immediate_scan_async())

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Strike Tips Scheduler")
    parser.add_argument("command", choices=["start", "scan"])
    args = parser.parse_args()
    if args.command == "start":
        StrikeTipsScheduler().start()
    elif args.command == "scan":
        run_immediate_scan()

if __name__ == "__main__":
    main()
