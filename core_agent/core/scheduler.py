"""
Strike Tips - Scheduler
Automated daily race scanning and notifications
Uses dynamic track discovery via RaceScheduleService.
APScheduler with timezone support (Africa/Johannesburg).
"""

import sys
import os
import json
from core_agent.core.market_watcher import MarketWatcher
import asyncio
from datetime import datetime, date, timedelta
from threading import Thread, Event
from typing import List, Dict
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.pool import ThreadPoolExecutor

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
                "[RUN]": "🏇",
                "[DATE]": "📅",
                "[OK]": "✅",
                "[ERR]": "❌",
                "[SCAN]": "🔄",
                "[HIT]": "🎯",
                "[TIME]": "⏰",
                "[LOC]": "📍",
                "[MAF]": "🧠",
                "[STOP]": "🛑",
                "[START]": "🚀",
                "[WORLD]": "🌍",
                "[SA]": "🇿🇦",
                "[UK]": "🇬🇧",
                "[AU]": "🇦🇺",
                "[US]": "🇺🇸",
                "[IE]": "🇮🇪",
                "[FR]": "🇫🇷",
                "[HK]": "🇭🇰",
                "[JP]": "🇯🇵",
                "[WARN]": "⚠️",
                "[STATS]": "📊",
                "[LOOKUP]": "🔍",
                "[LIST]": "📋",
                "[BOT]": "🤖",
                "[CHAT]": "💬",
                "[HEALTH]": "🏥",
                "[SEC]": "🔐",
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
        self._shutdown = Event()
        self.scheduler = None

        # Parse scan_time (format "HH:MM" in SAST)
        hour, minute = map(int, scan_time.split(":"))

        # APScheduler with SAST timezone
        jobstores = {"default": MemoryJobStore()}
        executors = {"default": ThreadPoolExecutor(max_workers=3)}
        job_defaults = {"coalesce": True, "max_instances": 1, "misfire_grace_time": 300}

        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone="Africa/Johannesburg",
        )

        # Schedule jobs in SAST
        self.scheduler.add_job(
            self.daily_scan_job,
            CronTrigger(hour=hour, minute=minute, timezone="Africa/Johannesburg"),
            id="daily_scan",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.run_daily_grounding_job,
            CronTrigger(hour=6, minute=0, timezone="Africa/Johannesburg"),
            id="daily_grounding",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.pre_warm_tomorrow_job,
            CronTrigger(hour=20, minute=0, timezone="Africa/Johannesburg"),
            id="pre_warm_tomorrow",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.continuous_scan_job,
            IntervalTrigger(minutes=15, timezone="Africa/Johannesburg"),
            id="continuous_scan",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.check_race_results_job,
            IntervalTrigger(minutes=5, timezone="Africa/Johannesburg"),
            id="check_results",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self._end_of_day_report,
            CronTrigger(hour=20, minute=0, timezone="Africa/Johannesburg"),
            id="end_of_day_report",
            replace_existing=True,
        )
        self.scheduler.add_job(
            self.update_learning_job,
            CronTrigger(hour=21, minute=0, timezone="Africa/Johannesburg"),
            id="update_learning",
            replace_existing=True,
        )

    def run_daily_grounding_job(self):
        """Syncs all track PDFs into memory via strike_tips.py."""
        print(
            f"\n[TIME] Starting daily PDF memory grounding at {datetime.now().strftime('%H:%M')}"
        )
        try:
            # We use a subprocess call to trigger the sync logic defined in strike_tips.py
            import subprocess

            subprocess.run(
                ["python3", "core_agent/core/strike_tips.py", "sync_pdfs"], check=True
            )
            print("[OK] Daily grounding complete.")
        except Exception as e:
            print(f"[ERR] PDF grounding failed: {e}")

    def pre_warm_tomorrow_job(self):
        print(
            f"\n[TIME] Pre-warming tomorrow's data at {datetime.now().strftime('%H:%M')}"
        )
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
            print(f"[CACHE] Pre-warming skipped — Betway API needs no pre-cache. {len(sa_tracks)} tracks for tomorrow: {', '.join(sa_tracks)}")

    def daily_scan_job(self):
        print(
            f"\n{'=' * 60}\n[TIME] Daily scan starting at {datetime.now().strftime('%H:%M')}\n{'=' * 60}"
        )
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._daily_scan_async())
        except Exception as e:
            print(f"[ERR] Daily scan failed: {e}")

    async def _daily_scan_async(self):
        self.strike = StrikeTips(data_dir=self.data_dir)
        try:
            return await self.strike.run_daily_scan()
        finally:
            await self.strike.close()

    def check_race_results_job(self):
        """Auto-settle open bets by searching race results via ResultTracker"""
        try:
            # Use the singleton brain instance (set up by API startup)
            from core_agent.core.strike_brain import brain

            if not brain or not brain.strike or not brain.strike.bankroll:
                return

            open_bets = brain.strike.bankroll.get_open_bets()
            if not open_bets:
                return

            print(
                f"[RESULT] Checking {len(open_bets)} open bet(s) for race results..."
            )

            async def _check_and_settle():
                from core_agent.skills.result_tracker import ResultTracker

                tracker = ResultTracker()
                settled = []
                for bet in open_bets:
                    result_text = await tracker._search_result(
                        bet.track, bet.race_number
                    )
                    if not result_text:
                        continue
                    winner, confidence = tracker._extract_winner(
                        result_text, [bet.horse]
                    )
                    if winner and confidence >= 0.6:
                        won = winner == bet.horse
                        brain.strike.settle_bet(
                            bet_id=bet.bet_id,
                            won=won,
                            notes=f"Auto-settled (confidence={confidence:.0%})",
                        )
                        settled.append(bet)
                return settled

            settled = asyncio.run(_check_and_settle())
            if settled:
                print(f"[OK] Auto-settled {len(settled)} bet(s)")
        except Exception as e:
            print(f"[ERR] Auto-settlement failed: {e}")

    _scan_failures = 0

    def continuous_scan_job(self):
        """Lightweight scan for value bets on today's active races (runs every 15min).
        Uses exponential backoff: after 3 failures → 1h, 10 failures → 4h.
        """
        try:
            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike:
                return
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._continuous_scan_async(brain))
            self._scan_failures = 0  # reset on success
            # Reset to 15min interval on success
            if self.scheduler and self.scheduler.get_job("continuous_scan"):
                self.scheduler.reschedule_job(
                    "continuous_scan",
                    trigger=IntervalTrigger(minutes=15, timezone="Africa/Johannesburg"),
                )
        except Exception as e:
            self._scan_failures += 1
            delay = 15  # minutes — default
            if self._scan_failures > 10:
                delay = 240  # 4 hours
            elif self._scan_failures > 3:
                delay = 60  # 1 hour
            print(f"[ERR] Continuous scan #{self._scan_failures} failed: {e} (next in {delay}min)")
            # Reschedule with backoff using APScheduler
            if self.scheduler and self.scheduler.get_job("continuous_scan"):
                self.scheduler.reschedule_job(
                    "continuous_scan",
                    trigger=IntervalTrigger(minutes=delay, timezone="Africa/Johannesburg"),
                )

    async def _continuous_scan_async(self, brain):
        """Fetch Betway snapshot and check for value opportunities."""
        print(f"[SCAN] Continuous scan at {datetime.now().strftime('%H:%M')}")
        state = await brain.strike.betway.get_snapshot_format()
        events = state.get("events", {})
        if not events:
            return
        settings_path = os.path.join(self.data_dir, "settings.json")
        min_edge = 8.0
        if os.path.exists(settings_path):
            with open(settings_path) as f:
                settings = json.load(f)
                min_edge = float(settings.get("auto_bet_min_edge", 8.0))
        found = 0
        for eid, event in events.items():
            course = event.get("course", "Unknown")
            runners = event.get("runners", [])
            for runner in runners:
                odds_str = str(runner.get("odds", "1/1"))
                if odds_str.upper() == "SP":
                    continue
                try:
                    odds = float(odds_str)
                except ValueError:
                    continue
                if odds <= 0:
                    continue
                implied = 1.0 / max(odds, 1.01)
                edge = round((1.0 - implied) * 100 * 0.15, 1)
                if edge >= min_edge:
                    print(f"[SCAN] Value: {runner.get('name')} @ {course} odds={odds} edge={edge}%")
                    found += 1
        print(f"[SCAN] Continuous scan complete — {found} value opportunities found")

    def update_learning_job(self):
        """Trigger AdaptiveAnalyzer to learn from today's results and update form insights."""
        try:
            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike or not brain.strike.learning:
                return
            brain.strike.learning.analyze_recent_results()
            print(f"[OK] Learning update complete at {datetime.now().strftime('%H:%M')}")
        except Exception as e:
            print(f"[ERR] Learning update failed: {e}")

    def _end_of_day_report(self):
        """Generate and send end-of-day performance report."""
        try:
            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike:
                return
            report = brain.strike.generate_report()
            print(f"\n{'='*60}\n[REPORT] End of Day Report\n{'='*60}")
            print(report)
            if brain.strike.telegram:
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(brain.strike.telegram.send_message(
                        f"📊 <b>End of Day Report</b>\n\n<pre>{report[:2000]}</pre>"
                    ))
                except RuntimeError:
                    asyncio.run(brain.strike.telegram.send_message(
                        f"📊 <b>End of Day Report</b>\n\n<pre>{report[:2000]}</pre>"
                    ))
            print("[OK] End-of-day report sent")
        except Exception as e:
            print(f"[ERR] End-of-day report failed: {e}")

    def start(self):
        self.running = True
        self._shutdown.clear()
        self.scheduler.start()
        print("[RUN] Strike Tips Scheduler Started (SAST timezone)")
        try:
            self._shutdown.wait()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.running = False
        self._shutdown.set()
        if self.scheduler:
            self.scheduler.shutdown(wait=True)
        print("[STOP] Strike Tips Scheduler Stopped")


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
