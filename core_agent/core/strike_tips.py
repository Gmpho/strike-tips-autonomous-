"""
Strike Tips - South African Horse Racing Intelligence System
Main orchestrator that ties together all skills
"""

import json
import os
import sys
import argparse
import asyncio
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from dataclasses import asdict

os.environ.setdefault("ENABLE_LOKI", "false")
os.environ.setdefault("ENABLE_PROMETHEUS", "false")

try:
    import logging_loki
except ImportError:
    logging_loki = None
from prometheus_client import push_to_gateway, REGISTRY
from opentelemetry import trace

# Reduce httpx logging noise - only show warnings and errors
httpx_logger = logging.getLogger("httpx")
httpx_logger.setLevel(logging.WARNING)

tracer = trace.get_tracer("strike_tips.CLI")

# Initialize logger
logger = logging.getLogger("strike-tips-cli")
logger.setLevel(logging.INFO)

# Graceful Loki initialization - only add handler if Alloy is reachable
_loki_enabled = False
if os.getenv("ENABLE_LOKI", "true").lower() == "true":
    loki_url = os.getenv("LOKI_URL", "http://localhost:3100/loki/api/v1/push")
    try:
        from core_agent.core.http_client import get_sync_client
        client = get_sync_client(timeout=2)
        health_url = loki_url.replace("/push", "/ready")
        response = client.get(health_url)
        if logging_loki and response.status_code == 200:
            loki_handler = logging_loki.LokiHandler(
                url=loki_url,
                tags={"application": "strike-tips-cli"},
                version="1",
            )
            loki_handler.setLevel(logging.WARNING)
            logger.addHandler(loki_handler)
            _loki_enabled = True
            print("[OK] Loki logging enabled")
        else:
                if not logging_loki:
                    print("[INFO] logging_loki module missing, skipping log shipping")
                else:
                    print("[INFO] Loki not ready, skipping log shipping")
    except Exception:
        print("[INFO] Alloy/Loki not available, Loki logging disabled")
else:
    print("[INFO] Loki logging disabled via ENABLE_LOKI=false")

# Prometheus push enabled flag
_prometheus_enabled = os.getenv("ENABLE_PROMETHEUS", "true").lower() == "true"
if not _prometheus_enabled:
    print("[INFO] Prometheus metrics disabled via ENABLE_PROMETHEUS=false")

# Import skills
from core_agent.skills.race_analysis import RaceAnalyzer, RaceCard, Runner
from core_agent.skills.race_analysis.form_analyzer import FormAnalyzer, parse_sa_form
from core_agent.skills.bankroll_manager import BankrollGovernor
from core_agent.skills.parsers.tab4racing import (
    TAB4RacingScraper,
    ScrapedRunner,
    ScrapedRace,
)
from core_agent.skills.parsers.betway_api import BetwayAPI
from core_agent.skills.parsers.oddschecker_scraper import OddscheckerScraper
from core_agent.skills.parsers.self_healing import SelfHealingParser
from core_agent.skills.notifications.telegram_bot import TelegramNotifier
from core_agent.agents.ai_providers import AIProvider
from core_agent.skills.learning.analyzer import AdaptiveAnalyzer

import sys

if "/app" not in sys.path:
    sys.path.append("/app")

from core_agent.config.settings import BANKROLL, TRACKS


class StrikeTips:
    """
    Main Strike Tips orchestrator.
    Coordinates scraping, analysis, bankroll management, and notifications.
    """

    def __init__(self, data_dir: Optional[str] = None, enable_telegram: bool = True):
        # 🛡️ Docker Resilience: Use env var if present, otherwise fallback to centralized config
        from core_agent.config.paths import DATA_DIR as PROJECT_DATA_DIR

        env_data_dir = os.getenv("DATA_DIR")
        if env_data_dir:
            self.data_dir = env_data_dir
        else:
            # Use absolute path to the centralized directory
            self.data_dir = data_dir or str(PROJECT_DATA_DIR)

        # Only attempt to create if it's not a root-level system path we don't own
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except PermissionError:
            # Fallback to local default if requested is inaccessible
            self.data_dir = os.path.abspath("./data")
            os.makedirs(self.data_dir, exist_ok=True)
            print(
                f"[WARN] Permission denied for data directory. Falling back to: {self.data_dir}"
            )

        # Initialize components
        self.analyzer = RaceAnalyzer()
        self.form_analyzer = FormAnalyzer()
        self.bankroll = BankrollGovernor(data_dir=self.data_dir)
        self.scraper = TAB4RacingScraper()
        self.betway = BetwayAPI()
        self.oddschecker = OddscheckerScraper()
        self.parser = SelfHealingParser()
        self.ai = AIProvider()
        self.learning = AdaptiveAnalyzer(data_dir=self.data_dir)

        # Initialize Memory
        from core_agent.skills.memory.chroma_memory import RacingMemory

        self.memory = RacingMemory(data_dir=os.path.join(self.data_dir, "chroma"))

        # 🛡️ Loop & Concurrency Protection
        self._processing_tracks = set()
        self._scraping_lock = asyncio.Lock()
        self._track_data_cache = {}  # Cache for raw race data during parallel runs

        # Initialize Telegram if configured
        self.telegram = None
        if enable_telegram:
            try:
                self.telegram = TelegramNotifier()
                print("SUCCESS: Telegram notifications enabled")
            except ValueError as e:
                print(f"WARN: Telegram not configured: {e}")

    async def scrape_and_analyze_track(
        self, track: str, date_str: Optional[str] = None
    ) -> List[Dict]:
        today_iso = date_str or date.today().isoformat()
        track_key = f"{track}_{today_iso}"

        if track_key in self._processing_tracks:
            print(
                f"[WARN] Track {track} is already being analyzed. Skipping to prevent loop."
            )
            return []

        self._processing_tracks.add(track_key)
        try:
            # 1. Fetch Raw Data (Primary: Betway + Oddschecker)
            async with self._scraping_lock:
                if track_key not in self._track_data_cache:
                    print(f"[BETWAY] Harvesting races for {track}...")
                    all_betway_races = await self.betway.get_races()

                    # Filter for specific track
                    races = [
                        r for r in all_betway_races if track.lower() in r.track.lower()
                    ]

                    if not races:
                        print(
                            f"[FALLBACK] No Betway data for {track}, trying TAB4Racing..."
                        )
                        races = await self.scraper.scrape_racecard(track, date_str)

                    self._track_data_cache[track_key] = races
                else:
                    races = self._track_data_cache[track_key]

            if not races:
                print(f"[WARN] No race data found for {track} after all attempts.")
                return []

            # 2. Dispatch Parallel AI Analysis
            print(
                f"[LIST] Found {len(races)} races. Dispatching parallel AI analysis..."
            )
            prompts = []
            for r in races:
                prompt = (
                    f"Analyze this single race for value (Edge > 5%): {json.dumps(asdict(r))}. "
                    f"Context: {track} Race {r.race_number}. "
                    "Return ONLY valid JSON: {'race_number': "
                    + str(r.race_number)
                    + ", 'summary': '...', 'value_bets': []}."
                )
                prompts.append(prompt)

            # Use the parallel provider if available
            # Dispatch in batches of 2 to protect 8GB RAM
            ai_responses = []
            for i in range(0, len(prompts), 2):
                batch = prompts[i : i + 2]
                logger.info(f"[SWARM] Processing batch {i//2 + 1}...")
                batch_responses = await self.ai._call_kimi_parallel(
                    batch, strike_instance=self
                )
                ai_responses.extend(batch_responses)
                await asyncio.sleep(2)  # Throttle delay for 8GB RAM

            results = []
            for i, r in enumerate(races):
                analysis_result = ai_responses[i].content
                # Parse Insight
                try:
                    # Robust cleaning
                    clean_text = (
                        analysis_result.replace("```json", "")
                        .replace("```", "")
                        .strip()
                    )

                    # Emergency fix: if LLM returns Python-style dict with single quotes outside keys
                    if "'" in clean_text and '"' not in clean_text:
                        # Very basic heuristic to swap types for JSON feasibility
                        import ast

                        try:
                            # Convert python string liteal to dict then to json string
                            data_dict = ast.literal_eval(clean_text)
                            clean_text = json.dumps(data_dict)
                        except:
                            pass

                    if "{" in clean_text and "}" in clean_text:
                        clean_text = clean_text[
                            clean_text.find("{") : clean_text.rfind("}") + 1
                        ]

                    insight = json.loads(clean_text)
                except Exception as e:
                    print(f"[DEBUG] AI Parse failed for {track} R{r.race_number}: {e}")
                    insight = {
                        "race_number": r.race_number,
                        "summary": analysis_result,
                        "value_bets": [],
                    }

                results.append(
                    {
                        "track": track,
                        "race_number": r.race_number,
                        "race_time": r.race_time,
                        "condition": r.track_condition,
                        "runners": [run.horse_name for run in r.runners],
                        "value_bets": insight.get("value_bets", []),
                        "ai_insight": insight.get("summary", analysis_result),
                    }
                )

            return results
        finally:
            self._processing_tracks.remove(track_key)
            # We keep track_data_cache for the duration of the track session

    def _convert_race_data(self, scraped_race: ScrapedRace) -> tuple:
        """
        Convert scraped race data to analysis format

        Returns:
            (RaceCard, probability_estimates dict, reasoning_map dict)
        """
        runners = []
        probability_estimates = {}
        reasoning_map = {}

        for sr in scraped_race.runners:
            # Parse form
            form_positions = []
            if sr.last_5_runs:
                form_positions = parse_sa_form(sr.last_5_runs)

            # Estimate probability from form
            est_prob, rating, reasoning = self.form_analyzer.estimate_win_probability(
                sr.horse_name,
                form_positions,
                target_track=scraped_race.track,
                target_distance=scraped_race.distance,
                track_condition=scraped_race.track_condition.lower(),
                field_size=len(scraped_race.runners),
            )

            runner = Runner(
                horse_name=sr.horse_name,
                odds_decimal=sr.odds_decimal,
                odds_fractional=sr.odds_fractional,
                jockey=sr.jockey,
                trainer=sr.trainer,
                barrier=sr.barrier,
                weight=sr.weight,
                last_5_runs=form_positions if sr.last_5_runs else None,
            )

            runners.append(runner)
            probability_estimates[sr.horse_name] = est_prob
            reasoning_map[sr.horse_name] = reasoning

        race_card = RaceCard(
            track=scraped_race.track,
            race_number=scraped_race.race_number,
            race_time=scraped_race.race_time,
            distance=scraped_race.distance,
            track_condition=scraped_race.track_condition,
            runners=runners,
            race_class=scraped_race.race_class,
            prize_money=scraped_race.prize_money,
        )

        return race_card, probability_estimates, reasoning_map

    def _notify_value_bet(self, value_bet):
        """Send Telegram notification for a value bet"""
        if not self.telegram:
            return

        try:
            self.telegram.send_value_bet(
                horse=value_bet.horse,
                track=value_bet.track,
                race_number=value_bet.race_number,
                race_time=value_bet.race_time,
                odds=value_bet.odds_decimal,
                edge_percent=value_bet.edge_percent,
                stake=value_bet.advised_stake,
                confidence=value_bet.confidence,
                reasoning=value_bet.reasoning,
            )
        except Exception as e:
            print(f"[ERR] Failed to send Telegram notification: {e}")

    def place_bet(
        self,
        track: str,
        race_number: int,
        horse: str,
        odds: float,
        edge_percent: float,
        confidence: str,
        override_stake: Optional[float] = None,
    ) -> Optional[Dict]:
        """
        Place a bet through the bankroll governor

        Returns:
            Bet record if successful
        """
        # Calculate stake if not provided
        if override_stake:
            stake = override_stake
        else:
            # Use Kelly-based stake from analyzer
            max_stake = self.bankroll.calculate_max_stake(edge_percent)
            stake = min(max_stake, BANKROLL.total_bankroll * 0.05)

        # Record the bet
        bet = self.bankroll.record_bet(
            track=track,
            race_number=race_number,
            horse=horse,
            odds=odds,
            stake=stake,
            edge_percent=edge_percent,
            confidence=confidence,
        )

        if bet:
            print(f"[OK] Bet recorded: {horse} @ {odds} for R{stake:.2f}")

            # Notify
            if self.telegram:
                self.telegram.send_message(
                    f"[NOTE] <b>Bet Placed</b>\n\n"
                    f"🐎 {horse}\n"
                    f"[LOC] {track} R{race_number}\n"
                    f"💰 Odds: {odds} | Stake: R{stake:.2f}\n"
                    f"[STATS] Edge: +{edge_percent}%"
                )

        return asdict(bet) if bet else None

    def settle_bet(self, bet_id: str, won: bool, notes: str = "") -> Dict:
        """
        Settle a bet with result

        Returns:
            Updated bankroll state
        """
        success = self.bankroll.settle_bet(bet_id, won, notes=notes)

        if success:
            bet = next(b for b in self.bankroll._bets if b.bet_id == bet_id)
            # Wire to learning engine so ROI-by-track is populated from real results
            self.learning.record_result(
                track=bet.track,
                distance=None,
                odds=bet.odds,
                stake=bet.stake,
                won=won,
                actual_return=bet.actual_return or 0.0,
            )
            profit_loss = (bet.actual_return or 0) - bet.stake

            print(f"[OK] Bet settled: {bet.horse} - {'Won' if won else 'Lost'}")

            # Notify
            if self.telegram:
                self.telegram.send_bet_result(
                    horse=bet.horse,
                    track=bet.track,
                    race_number=bet.race_number,
                    won=won,
                    stake=bet.stake,
                    returns=bet.actual_return or 0,
                    profit_loss=profit_loss,
                )

        return self.get_bankroll_status()

    def get_bankroll_status(self) -> Dict:
        """Get current bankroll status"""
        return {
            "current_bankroll": self.bankroll.current_bankroll,
            "peak_bankroll": self.bankroll.peak_bankroll,
            "total_profit_loss": self.bankroll.total_profit_loss,
            "drawdown_percent": self.bankroll.drawdown_percent,
            "today_stats": asdict(self.bankroll.get_today_stats()),
            "open_bets": len(self.bankroll.get_open_bets()),
            "performance": self.bankroll.get_performance_summary(),
        }

    def get_active_tracks(self) -> List[str]:
        """Return list of active SA track names"""
        return self.scraper.get_active_tracks()

    async def run_daily_scan(self, tracks: Optional[List[str]] = None) -> Dict:
        """
        Run daily scan for all tracks and SAVE to memory for RAG grounding.
        Uses MAF Workflow (Scrape→Analyse→Bankroll→Notify) when agents are available,
        falls back to legacy scrape_and_analyze_track otherwise.
        """
        tracks = tracks or list(TRACKS.keys())

        print("\n" + "=" * 60)
        print("STRIKE TIPS - Daily Racing Scan")
        print("=" * 60)
        print(f"[DATE] {datetime.now().strftime('%A, %d %B %Y')}")
        print(f"[LOC] Tracks: {', '.join(t.title() for t in tracks)}")
        print("=" * 60)

        # 1. Harvest Official PDF Tips FIRST
        from core_agent.skills.parsers.pdf_harvester import PDFHarvester

        pdf = PDFHarvester()
        pdf_res = await pdf.get_latest_racing_intelligence("Any", "Daily Tips")
        pdf_tips = pdf_res.get("parsed_tips", [])

        from core_agent.core.strike_brain import brain

        memory = brain.memory

        if memory and pdf_tips:
            today_str = date.today().isoformat()
            for tip in pdf_tips:
                memory.add_form_insight(
                    horse=f"Official_Tip_R{tip['race_number']}",
                    insight=f"OFFICIAL TAB TIP: For Race {tip['race_number']}, the official selection is {tip['selections']}.",
                    metadata={
                        "date": today_str,
                        "type": "official_tip",
                        "race": tip["race_number"],
                    },
                )
            print(f"  📜 {len(pdf_tips)} official PDF tips grounded in memory.")

        # 2. Try MAF Workflow if agents are initialized
        agents = getattr(getattr(brain, "pipeline", None), "_agents", None)
        if agents:
            try:
                from core_agent.agents.workflow import build_race_scan_workflow

                workflow = build_race_scan_workflow(self, agents)
                events = await workflow.run(tracks)
                outputs = events.get_outputs() or []
                total_value_bets = sum(
                    1
                    for item in outputs
                    if isinstance(item, dict)
                    and "RECORD" in str(item.get("decision", "")).upper()
                )
                print(
                    f"\n[OK] MAF Workflow scan complete! {total_value_bets} selections flagged."
                )
                return {
                    "date": date.today().isoformat(),
                    "tracks_scanned": len(tracks),
                    "total_value_bets": total_value_bets,
                    "results": outputs,
                }
            except Exception as e:
                print(f"[WARN] MAF Workflow failed ({e}), falling back to legacy scan.")

        # 3. Legacy fallback
        all_results = {}
        total_value_bets = 0
        for track in tracks:
            try:
                results = await self.scrape_and_analyze_track(track)
                all_results[track] = results
                if results:
                    total_value_bets += sum(
                        len(r.get("value_bets", []))
                        for r in results
                        if isinstance(r, dict)
                    )
                if memory and results:
                    today_str = date.today().isoformat()
                    for race in results:
                        memory.add_form_insight(
                            horse=f"Track_{race['track']}_R{race['race_number']}",
                            insight=(
                                f"OFFICIAL RACE CARD: {race['track']} Race {race['race_number']} at {race['race_time']}. "
                                f"Condition: {race['condition']}. Runners: {race['runners']}."
                            ),
                            metadata={
                                "date": today_str,
                                "track": race["track"],
                                "type": "official_card",
                            },
                        )
            except Exception as e:
                print(f"[ERR] Error processing {track}: {e}")
                all_results[track] = []

        if self.telegram:
            try:
                self.telegram.send_daily_tips(all_results)
            except Exception as e:
                print(f"[ERR] Failed to send daily summary: {e}")

        output_file = os.path.join(
            self.data_dir, f"daily_scan_{date.today().isoformat()}.json"
        )
        with open(output_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)

        if _prometheus_enabled:
            try:
                gateway_url = os.getenv("PROMETHEUS_PUSHGATEWAY", "localhost:9091")
                push_to_gateway(
                    gateway_url, job="strike_tips_daily_scan", registry=REGISTRY
                )
            except Exception:
                pass

        print(
            f"\n[OK] Scan complete! Found {total_value_bets} value bets across all tracks"
        )
        return {
            "date": date.today().isoformat(),
            "tracks_scanned": len(tracks),
            "total_value_bets": total_value_bets,
            "results": all_results,
        }

    def generate_report(self) -> str:
        """Generate daily report"""
        return self.bankroll.generate_daily_report()

    async def evaluate_race(
        self,
        track: str,
        race_number: int,
        horse_probabilities: Optional[Dict[str, float]] = None,
    ) -> Dict:
        """Evaluate a specific race for value opportunities."""
        if not horse_probabilities:
            # 🛡️ Recursion Check: If we're already processing this track, don't trigger another full scrape_and_analyze
            today_iso = date.today().isoformat()
            track_key = f"{track}_{today_iso}"

            if track_key in self._processing_tracks:
                # Try to get from cache if it exists, otherwise return a wait/busy message
                if track_key in self._track_data_cache:
                    races = self._track_data_cache[track_key]
                    for race in races:
                        if race.race_number == race_number:
                            return {
                                "status": "DATA_READY",
                                "message": f"Data for {track} R{race_number} is available. Suggesting analysis on cached card.",
                                "race_card": asdict(race),
                            }
                return {
                    "status": "BUSY",
                    "message": f"Track {track} is currently under analysis. Please wait 10 seconds.",
                }

            results = await self.scrape_and_analyze_track(track)
            for race in results:
                if race.get("race_number") == race_number:
                    return {
                        "status": (
                            "VALUE_FOUND" if race.get("value_bets") else "NO_VALUE"
                        ),
                        "top_selection": (
                            race["value_bets"][0] if race.get("value_bets") else None
                        ),
                        "all_selections": race.get("value_bets", []),
                        "insight": race.get("ai_insight", ""),
                    }
            return {
                "status": "NO_VALUE",
                "message": f"Race {race_number} at {track} not found",
            }

        # If they ARE provided (e.g. from an LLM estimate), run the edge analyzer
        # This part requires creating a temporary RaceCard
        # For simplicity, we'll use the existing analyzer logic
        from core_agent.skills.race_analysis.analyzer import RaceCard, Runner

        # We'd need actual odds here, but we'll assume current market odds if possible
        # For now, return a placeholder or use form-based estimates
        return {"status": "ANALYSIS_COMPLETE", "track": track, "race": race_number}

    async def get_odds_snapshot(self, track: Optional[str] = None) -> Dict:
        """Get the latest odds snapshot for a track or all tracks."""
        snapshot_path = os.path.join(self.data_dir, "market_snapshot_latest.json")
        if os.path.exists(snapshot_path):
            try:
                with open(snapshot_path, "r") as f:
                    data = json.load(f)
                    if track:
                        # Filter for specific track if provided
                        return {track: data.get(track, [])}
                    return data
            except Exception as e:
                logger.error(f"Error reading odds snapshot: {e}")

        return {"status": "no_snapshot_available"}

    async def verify_race_event(self, track: str, race_num: int) -> bool:
        """Verify if a specific race is scheduled for today."""
        logger.info(f"Verifying race {race_num} at {track}")
        try:
            today_iso = date.today().isoformat()
            # Fetch races for today from the specified track
            races = await self.scraper.scrape_racecard(track=track, date_str=today_iso)
            if races:
                for race in races:
                    if race.race_number == race_num:
                        return True
            return False
        except Exception as e:
            logger.error(f"Error verifying race {race_num} at {track}: {e}")
            return False  # Assume it doesn't exist if an error occurs

    async def close(self):
        """Clean up resources"""
        await self.scraper.close()
        if self.telegram:
            self.telegram.close()


async def main_async():
    """CLI interface"""
    parser = argparse.ArgumentParser(
        description="Strike Tips - SA Horse Racing Intelligence"
    )
    parser.add_argument(
        "command",
        choices=["scan", "track", "bet", "settle", "status", "report", "chat"],
        help="Command to run",
    )
    parser.add_argument("--track", "-t", help="Track name (for track command)")
    parser.add_argument("--date", "-d", help="Date (YYYY-MM-DD)")
    parser.add_argument("--horse", help="Horse name (for bet command)")
    parser.add_argument("--race", "-r", type=int, help="Race number")
    parser.add_argument("--odds", type=float, help="Odds (for bet command)")
    parser.add_argument("--edge", type=float, help="Edge percent (for bet command)")
    parser.add_argument("--stake", type=float, help="Stake amount (optional)")
    parser.add_argument("--bet-id", help="Bet ID (for settle command)")
    parser.add_argument(
        "--won", action="store_true", help="Bet won (for settle command)"
    )
    parser.add_argument("--no-telegram", action="store_true", help="Disable Telegram")

    args = parser.parse_args()

    # Initialize Strike Tips
    strike = StrikeTips(enable_telegram=not args.no_telegram)

    try:
        if args.command == "scan":
            result = await strike.run_daily_scan()
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "track":
            if not args.track:
                print("[ERR] --track required")
                sys.exit(1)
            result = await strike.scrape_and_analyze_track(args.track, args.date)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "bet":
            if not all([args.track, args.race, args.horse, args.odds]):
                print("[ERR] --track, --race, --horse, --odds required")
                sys.exit(1)

            result = strike.place_bet(
                track=args.track,
                race_number=args.race,
                horse=args.horse,
                odds=args.odds,
                edge_percent=args.edge or 0,
                confidence="VALUE",
                override_stake=args.stake,
            )
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "settle":
            if not args.bet_id:
                print("[ERR] --bet-id required")
                sys.exit(1)

            result = strike.settle_bet(args.bet_id, args.won)
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "status":
            result = strike.get_bankroll_status()
            print(json.dumps(result, indent=2, default=str))

        elif args.command == "report":
            print(strike.generate_report())

        elif args.command == "chat":
            print("\n[MAF] Strike Tips AI - Interactive Mode")
            print("=" * 50)
            print("Type 'exit' or 'quit' to end session.")

            from core_agent.agents.ai_pydantic import UnifiedOrchestrator

            orchestrator = UnifiedOrchestrator(strike)

            while True:
                try:
                    # Check for prompt input
                    user_input = input("\n> ").strip()
                    if user_input.lower() in ["exit", "quit"]:
                        break
                    if not user_input:
                        continue

                    result = await orchestrator.chat(user_input)
                    print(f"\n[AI] {result.summary}")
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"[ERR] Chat error: {e}")

    finally:
        await strike.close()


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
