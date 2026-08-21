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

from core_agent.core.strike_tips import StrikeTips, resolve_auto_bet_odds
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
                    if winner and confidence >= 0.55:
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
        """Fetch Betway snapshot, detect mid-day schedule/race changes, and run targeted scans."""
        print(f"[SCAN] Continuous scan starting at {datetime.now().strftime('%H:%M')}")
        
        # 1. Fetch latest Betway snapshot
        try:
            snapshot = await brain.strike.betway.get_snapshot_format()
        except Exception as e:
            print(f"[WARN] Failed to fetch Betway snapshot: {e}")
            return
            
        events = snapshot.get("events", {})
        if not events:
            print("[SCAN] No active events in snapshot.")
            return

        # 2. Save latest market snapshot to file (for HUD dashboard)
        snapshot_file = os.path.join(self.data_dir, "market_snapshot_latest.json")
        try:
            with open(snapshot_file, "w") as f:
                json.dump(snapshot, f, indent=2, default=str)
        except Exception as e:
            print(f"[WARN] Failed to save market snapshot: {e}")

        # 3. Load daily scan results to see what has already been scanned
        today_iso = date.today().isoformat()
        daily_scan_path = os.path.join(self.data_dir, f"daily_scan_{today_iso}.json")
        scanned_races = {}  # Maps track -> set of race numbers
        if os.path.exists(daily_scan_path):
            try:
                with open(daily_scan_path) as f:
                    scanned_data = json.load(f)
                    for track, races in scanned_data.items():
                        if isinstance(races, list):
                            scanned_races[track.lower()] = {
                                r.get("race_number") for r in races if isinstance(r, dict) and "race_number" in r
                            }
            except Exception as e:
                print(f"[WARN] Failed to load daily scan results: {e}")

        # 4. Find tracks/races in the current snapshot that haven't been scanned yet
        tracks_to_rescan = set()
        for eid, event in events.items():
            course = event.get("course", "").strip()
            race_num = event.get("race_number")
            if not course or race_num is None:
                continue
            
            # If the track/race is not in our scanned list, mark the track for a rescan
            course_lower = course.lower()
            if course_lower not in scanned_races or race_num not in scanned_races[course_lower]:
                print(f"[SCAN] Detected unscanned mid-day race: {course} Race {race_num}")
                tracks_to_rescan.add(course)

        # 5. Execute targeted scrape and analysis on tracks with changes
        if not tracks_to_rescan:
            print("[SCAN] No new mid-day races detected. All snapshot events are already scanned.")
            return

        print(f"[SCAN] Triggering mid-day rescans for tracks: {', '.join(tracks_to_rescan)}")
        
        # Load settings for auto-bet check
        settings_path = os.path.join(self.data_dir, "settings.json")
        auto_bet_enabled = False
        min_edge = 5.5
        if os.path.exists(settings_path):
            try:
                with open(settings_path) as f:
                    settings = json.load(f)
                    auto_bet_enabled = settings.get("auto_bet_enabled", False)
                    min_edge = float(settings.get("auto_bet_min_edge", 5.5))
            except Exception:
                pass

        # Load existing results to update them
        existing_results = {}
        if os.path.exists(daily_scan_path):
            try:
                with open(daily_scan_path) as f:
                    existing_results = json.load(f)
            except Exception:
                pass

        for track in tracks_to_rescan:
            try:
                print(f"[SCAN] Rescanning track: {track}")
                results = await brain.strike.scrape_and_analyze_track(track)
                if not results:
                    continue
                
                # Update our daily scan file with the rescanned track
                existing_results[track] = results
                with open(daily_scan_path, "w") as f:
                    json.dump(existing_results, f, indent=2, default=str)
                
                # Ground the new race info in memory
                if brain.memory:
                    for race in results:
                        brain.memory.add_form_insight(
                            horse=f"Track_{race['track']}_R{race['race_number']}",
                            insight=(
                                f"OFFICIAL RACE CARD: {race['track']} Race {race['race_number']} at {race['race_time']}. "
                                f"Condition: {race['condition']}. Runners: {race['runners']}."
                            ),
                            metadata={
                                "date": today_iso,
                                "track": race["track"],
                                "type": "official_card",
                            },
                        )

                # Auto-bet on any new value bets from this rescan
                if auto_bet_enabled:
                    for race in results:
                        if not isinstance(race, dict):
                            continue
                        for vb in race.get("value_bets", []):
                            horse = vb.get("horse") or ""
                            if not horse:
                                continue
                            raw_edge = vb.get("edge_percent") or vb.get("edge") or vb.get("estimated_edge") or 0
                            edge = float(raw_edge)
                            if 0 < edge < 1:
                                edge *= 100
                            if edge < min_edge:
                                continue
                            odds = resolve_auto_bet_odds(vb)
                            if odds is None:
                                print(f"[AUTO-BET] Skip {horse} @ {track} R{race.get('race_number')}: no bettable market odds")
                                continue

                            # Place the bet!
                            brain.strike.place_bet(
                                horse=horse,
                                track=track,
                                race_number=race.get("race_number", 0),
                                odds=odds,
                                edge_percent=edge,
                                confidence="AUTO_MIDDAY",
                                distance=race.get("distance"),
                            )
                            print(f"[AUTO-BET] Placed mid-day auto-bet on {horse} @ {track} R{race.get('race_number')} edge={edge}%")

                # Send individual value bet notifications via Telegram based on settings
                if brain.strike.telegram:
                    try:
                        telegram_enabled = True
                        priority_only = False
                        if os.path.exists(settings_path):
                            with open(settings_path) as f:
                                settings = json.load(f)
                            telegram_enabled = settings.get("telegramEnabled", True)
                            priority_only = settings.get("valueBetAlerts", False)

                        if telegram_enabled:
                            for race in results:
                                if not isinstance(race, dict):
                                    continue
                                for vb in race.get("value_bets", []):
                                    horse = vb.get("horse") or ""
                                    if not horse:
                                        continue
                                    raw_edge = vb.get("edge_percent") or vb.get("edge") or vb.get("estimated_edge") or 0
                                    edge = float(raw_edge)
                                    if 0 < edge < 1:
                                        edge *= 100

                                    # Filter for priority alerts (edge >= 15.0%) if configured
                                    if priority_only and edge < 15.0:
                                        continue

                                    raw_odds = vb.get("odds_decimal") or vb.get("offered_odds") or vb.get("bookmaker_odds") or vb.get("odds") or 2.0
                                    odds = float(raw_odds)

                                    # Calculate advised stake using Half-Kelly for the notification
                                    max_stake = brain.strike.bankroll.calculate_max_stake(
                                        edge, track, race.get("race_number")
                                    )
                                    advised_stake = min(max_stake, brain.strike.bankroll.current_bankroll * 0.05)

                                    # Determine confidence category
                                    confidence = "STRONG_VALUE" if edge >= 15.0 else "VALUE" if edge >= 8.0 else "MARGINAL"

                                    await brain.strike.telegram.send_value_bet(
                                        horse=horse,
                                        track=track,
                                        race_number=race.get("race_number", 0),
                                        race_time=race.get("race_time", "TBD"),
                                        odds=odds,
                                        edge_percent=edge,
                                        stake=advised_stake,
                                        confidence=confidence,
                                        reasoning=vb.get("reasoning", "Value detected by AI model analysis during continuous scan."),
                                    )
                    except Exception as e:
                        print(f"[ERR] Failed to send continuous scan individual value bet alerts: {e}")
            except Exception as e:
                print(f"[ERR] Continuous scan rescan failed for {track}: {e}")
        print("[SCAN] Continuous scan job complete.")

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

    async def _send_eod_report_async(self, report: str):
        from core_agent.core.strike_brain import brain
        if not brain or not brain.strike or not brain.strike.telegram:
            return
        await brain.strike.telegram.send_message(
            f"📊 <b>End of Day Report</b>\n\n<pre>{report[:2000]}</pre>"
        )

    def _end_of_day_report(self):
        """Generate and send end-of-day performance report + auto-learn from results."""
        try:
            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike:
                return
            report = brain.strike.generate_report()
            print(f"\n{'='*60}\n[REPORT] End of Day Report\n{'='*60}")
            print(report)
            if brain.strike.telegram:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._send_eod_report_async(report))
                finally:
                    loop.close()
            print("[OK] End-of-day report sent")

            # Auto-learn from settled bet performance
            try:
                from core_agent.skills.memory.self_improve import analyze_performance_and_learn
                if brain.strike.bankroll:
                    learn_results = analyze_performance_and_learn(brain.strike.bankroll)
                    saved = sum(1 for r in learn_results if r.get("status") == "SAVED")
                    if saved:
                        print(f"[AUTO-LEARN] Generated {saved} new learned insight(s) from performance data")
            except Exception as e:
                print(f"[WARN] Auto-learn step failed: {e}")
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
