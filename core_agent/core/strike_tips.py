"""
Strike Tips - South African Horse Racing Intelligence System
Main orchestrator that ties together all skills
"""

import json
import os
import sys
import argparse
import asyncio
import difflib
import logging
from datetime import datetime, date
from typing import List, Dict, Optional
from dataclasses import asdict

os.environ.setdefault("ENABLE_LOKI", "false")
os.environ.setdefault("ENABLE_PROMETHEUS", "false")


_PENDING_TG_TASKS: List[asyncio.Task] = []

def _fire_async(coro):
    """Fire an async coroutine from sync code, tracking it for await on shutdown."""
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(coro)
        _PENDING_TG_TASKS.append(task)
    except RuntimeError:
        asyncio.run(coro)


def resolve_auto_bet_odds(value_bet: Dict) -> Optional[float]:
    """Return a bettable decimal odd for a value bet, or None if missing/invalid.

    Auto-betting must never assume a price (e.g. defaulting to 2.0): an
    assumed odd corrupts stake sizing, settlement math, and learning stats.
    """
    raw = (
        value_bet.get("odds_decimal")
        or value_bet.get("offered_odds")
        or value_bet.get("bookmaker_odds")
        or value_bet.get("odds")
    )
    if not raw:
        return None
    try:
        odds = float(raw)
    except (TypeError, ValueError):
        return None
    return odds if odds > 1.01 else None

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
# NOTE: OddscheckerScraper imported lazily in __init__ (crawl4ai hangs at module level)
from core_agent.skills.parsers.self_healing import SelfHealingParser
from core_agent.skills.notifications.telegram_bot import TelegramNotifier
from core_agent.core.alert_digester import AlertDigester
from core_agent.agents.ai_providers import AIProvider
from core_agent.skills.learning.analyzer import AdaptiveAnalyzer

import sys

if "/app" not in sys.path:
    sys.path.append("/app")

from core_agent.config.settings import TRACKS


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
        self.digester = None
        if enable_telegram:
            try:
                self.telegram = TelegramNotifier()
                self.digester = AlertDigester(self.telegram)
                self.digester.start()
                print("SUCCESS: Telegram notifications enabled")
            except ValueError as e:
                print(f"WARN: Telegram not configured: {e}")

    async def scrape_and_analyze_track(
        self, track: str, date_str: Optional[str] = None
    ) -> List[Dict]:
        if self.digester:
            await self.digester.start_async()
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
                            f"[WARN] No Betway data for {track}. Falling back to TAB scraper..."
                        )
                        races = await self.scraper.scrape_racecard(
                            track, today_iso
                        )
                        if not races:
                            print(
                                f"[WARN] TAB also returned no data for {track}. Skipping."
                            )
                            self._track_data_cache[track_key] = []
                            return []

                    self._track_data_cache[track_key] = races
                else:
                    races = self._track_data_cache[track_key]

            # Enrich runners with PDF racecard data from ChromaDB
            await self._enrich_runners_from_pdf(races, track, today_iso)

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
                    f"Analyze this single race for value: {json.dumps(asdict(r))}. "
                    f"Context: {track} Race {r.race_number}. "
                    "Return ONLY valid JSON. Each value_bet MUST include these fields: "
                    "'horse' (string), 'edge_percent' (float, your edge = (est_prob - 1/odds) * 100), "
                    "'odds_decimal' (float), 'estimated_probability' (float 0-1), "
                    "'reasoning' (string). "
                    f"{{'race_number': {r.race_number}, 'summary': '...', 'value_bets': [...]}}"
                )
                prompts.append(prompt)

            # Use the parallel provider if available
            # Dispatch in batches of 1 to protect 8GB RAM (Sequential reasoning)
            ai_responses = []
            for i in range(0, len(prompts)):
                batch = prompts[i : i + 1]
                logger.info(f"[SWARM] Processing race {i+1}/{len(prompts)}...")
                batch_responses = await self.ai._call_kimi_parallel(batch)
                ai_responses.extend(batch_responses)
                await asyncio.sleep(3)  # Increased throttle delay for 8GB RAM

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
                        "value_bets": self._validate_value_bets(
                            insight.get("value_bets", []),
                            [run.horse_name for run in r.runners],
                        ),
                        "ai_insight": insight.get("summary", analysis_result),
                    }
                )

            return results
        finally:
            self._processing_tracks.remove(track_key)
            # We keep track_data_cache for the duration of the track session

    def _validate_value_bets(self, value_bets: List[Dict], valid_horses: List[str]) -> List[Dict]:
        """Cross-reference AI-generated value bets against actual scraped runners.
        Filters out hallucinated horse names using fuzzy matching."""
        validated = []
        for vb in value_bets:
            horse = vb.get("horse") or vb.get("name") or vb.get("horse_name") or ""
            if not horse:
                continue
            if horse in valid_horses:
                vb["horse"] = horse
                validated.append(vb)
                continue
            matches = difflib.get_close_matches(horse, valid_horses, n=1, cutoff=0.6)
            if matches:
                vb["horse"] = matches[0]
                validated.append(vb)
            else:
                print(f"[WARN] Rejected hallucinated horse '{horse}' — not in actual runners: {valid_horses}")
        return validated

    async def _enrich_runners_from_pdf(
        self, races: List[ScrapedRace], track: str, date_str: str
    ) -> int:
        """Populate ScrapedRunner.form with PDF racecard comments from ChromaDB.

        For TAB-fallback tracks that lack Betway form data, this provides
        the AI with form_flag (X/XX = recent winner) and comment text
        scraped from the Computaform PDF and stored in vector memory.
        """
        if not self.memory or not self.memory._is_ready:
            return 0
        try:
            rows = self.memory.get_pdf_racecards(track=track, date=date_str)
            if not rows:
                return 0

            pdf_by_horse = {}
            for row in rows:
                m = row["metadata"]
                name = m.get("horse_name", "").strip().upper()
                if name:
                    pdf_by_horse[name] = row

            enriched = 0
            for race in races:
                for runner in race.runners:
                    key = runner.horse_name.strip().upper()
                    match = pdf_by_horse.get(key)
                    if not match:
                        import difflib
                        close = difflib.get_close_matches(
                            key, list(pdf_by_horse.keys()), n=1, cutoff=0.7
                        )
                        match = pdf_by_horse.get(close[0]) if close else None
                    if not match:
                        continue
                    m = match["metadata"]

                    if not runner.jockey:
                        j = m.get("jockey", "")
                        if j:
                            runner.jockey = j

                    if not runner.trainer:
                        t = m.get("trainer", "")
                        if t:
                            runner.trainer = t

                    comment = m.get("comment", "")
                    flag = m.get("form_flag", "")
                    hmr = m.get("hmr", 0)
                    cmr = m.get("cmr", 0)
                    forecast = m.get("forecast_odds_decimal", 0)
                    parts = []
                    if flag:
                        parts.append(f"[PDF: {flag}]")
                    if comment:
                        parts.append(comment)
                    ratings = []
                    if hmr:
                        ratings.append(f"HMR={hmr}")
                    if cmr:
                        ratings.append(f"CMR={cmr}")
                    if forecast:
                        ratings.append(f"Fcst={forecast}")
                    if ratings:
                        parts.append(f"[{' '.join(ratings)}]")
                    if parts:
                        extra = " | " + " ".join(parts)
                        if runner.form:
                            runner.form += extra
                        else:
                            runner.form = extra

                    # Override placeholder odds (5.0 = SP) with Computaform forecast odds
                    if forecast and runner.odds_decimal in (0, 5.0):
                        runner.odds_decimal = float(forecast)
                        logger.debug(
                            "[PDF] Overrode odds for %s: 5.0 → %.1f (Computaform Fcst)",
                            runner.horse_name, float(forecast),
                        )

                    enriched += 1

            if enriched:
                logger.info(
                    "[PDF] Enriched %d runners with PDF comments for %s %s",
                    enriched, track, date_str,
                )
            return enriched
        except Exception as e:
            logger.warning("[PDF] Runner enrichment failed: %s", e)
            return 0

    async def _analyze_exotic_pools(self, all_results: Dict, pdf_races: Dict) -> List[Dict]:
        """Extract pool structure from PDF leg_info and run AI exotic analysis."""
        import re

        # 1. Extract pool starts from PDF leg_info
        pool_starts = {}
        for rn, race_data in pdf_races.items():
            if not isinstance(race_data, dict):
                continue
            leg = (race_data.get("leg_info") or "").upper()
            if not leg:
                continue
            for kw, mk in [("BIPOT", "BI"), ("JACKPOT", "JP"), ("PICK6", "P6"), ("PA", "PA")]:
                if kw not in leg:
                    continue
                lm = re.search(rf'{kw}\s+LEG\s+(\d+)', leg)
                if not lm:
                    continue
                pn = mk if mk in ("PA", "P6") else f"{mk}{lm.group(1)}"
                if pn not in pool_starts:
                    pool_starts[pn] = int(rn)

        if not pool_starts:
            return []

        # 2. Build full-card context from Betway data
        card_sections = []
        for track_name, track_results in all_results.items():
            if not track_results:
                continue
            card_sections.append(f"TRACK: {track_name}")
            for race in track_results:
                rn = race.get("race_number", "?")
                rt = race.get("race_time", "TBD")
                runners = race.get("runners", [])
                card_sections.append(f"\nRace {rn} ({rt}): {len(runners)} runners")
                card_sections.append(f"  Runners: {', '.join(runners)}")

        pool_summary = ", ".join(f"{k} starts R{v}" for k, v in sorted(pool_starts.items()))
        card_context = (
            "=== FULL RACE CARD EXOTIC ANALYSIS ===\n"
            + "\n".join(card_sections)
            + f"\n\nPOOL LAYOUT: {pool_summary}\n\n"
            + "YOUR TASK: Generate exotic pool combinations for each declared pool. "
            + "For each pool, pick banker and saver selections per leg based on horse quality, "
            + "form, and trainer/jockey strength. "
            + "Return ONLY valid JSON: "
            + '{"exotic_plays": [{"pool": "JACKPOT 1", "legs": [1,2,3,4], '
            + '"combinations": [{"legs": [4,8,2,1], "type": "banker"}, '
            + '{"legs": [4,8,2,3], "type": "saver"}], '
            + '"estimated_combinations": 2, "estimated_dividend": 850.0, '
            + '"reasoning": "..."}]}'
        )

        # 3. Send to AI as single extra analysis call via Groq / Gemini (direct HTTP)
        try:
            import httpx
            groq_key = os.getenv("GROQ_API_KEY", "")
            raw = None

            if groq_key:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                        json={
                            "model": "openai/gpt-oss-120b",
                            "messages": [{"role": "user", "content": card_context}],
                            "temperature": 0.2,
                            "max_tokens": 1200,
                            "response_format": {"type": "json_object"},
                        },
                    )
                    if resp.status_code == 200:
                        data_json = resp.json()
                        raw = data_json.get("choices", [{}])[0].get("message", {}).get("content", "")

            if raw:
                clean = raw.replace("```json", "").replace("```", "").strip()
                if "{" in clean:
                    clean = clean[clean.find("{"):clean.rfind("}") + 1]
                data = json.loads(clean)
                plays = data.get("exotic_plays", [])
                for p in plays:
                    p["_track"] = track_name
                print(f"[EXOTIC] AI returned {len(plays)} exotic play(s)")
                return plays
        except Exception as e:
            print(f"[EXOTIC] AI exotic analysis skipped/failed: {e}")

        # Deterministic Fallback: Generate structured exotic permutations from race runners
        fallback_plays = []
        try:
            from core_agent.skills.exotics.builder import resolve_pool_legs

            for pool_name, start_race in pool_starts.items():
                matched_pool, num_legs = resolve_pool_legs(pool_name)
                
                legs_list = list(range(start_race, start_race + num_legs))
                combinations = []
                
                for r_num in legs_list:
                    # Look up runners in track results
                    r_info = next((r for r in all_results.get(track_name, []) if r.get("race_number") == r_num), None)
                    r_runners = r_info.get("runners", []) if r_info else []
                    b_horse = r_runners[0] if len(r_runners) > 0 else f"Runner #{r_num}-1"
                    s_horses = r_runners[1:3] if len(r_runners) > 1 else []
                    combinations.append({
                        "race": r_num,
                        "banker": b_horse,
                        "savers": s_horses,
                    })

                fallback_plays.append({
                    "pool": matched_pool,
                    "legs": legs_list,
                    "combinations": combinations,
                    "estimated_combinations": max(1, 2 ** (num_legs - 2)),
                    "estimated_dividend": 450.0 * num_legs,
                    "reasoning": f"Algorithmic coverage blueprint covering {num_legs} legs starting at Race {start_race}.",
                    "_track": track_name,
                })
            print(f"[EXOTIC] Generated {len(fallback_plays)} structured fallback exotic play(s)")
            return fallback_plays
        except Exception as e:
            print(f"[EXOTIC] Fallback exotic generation error: {e}")
            return []

    def _convert_race_data(self, scraped_race: ScrapedRace) -> tuple:
        """
        Convert scraped race data to analysis format

        Returns:
            (RaceCard, probability_estimates dict, reasoning_map dict)
        """
        runners = []
        probability_estimates = {}
        reasoning_map = {}
        raw_strengths = {}

        for sr in scraped_race.runners:
            # Parse form
            form_positions = []
            if sr.form:
                form_positions = parse_sa_form(sr.form)

            # Estimate probability from form
            est_prob, rating, reasoning = self.form_analyzer.estimate_win_probability(
                sr.horse_name,
                form_positions,
                target_track=scraped_race.track,
                target_distance=scraped_race.distance,
                track_condition=scraped_race.track_condition.lower(),
                field_size=len(scraped_race.runners),
            )
            # Collect uncapped strength for field-wide normalization
            raw_strengths[sr.horse_name] = self.form_analyzer.estimate_win_strength(
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
                last_5_runs=form_positions if sr.form else None,
            )

            runners.append(runner)
            probability_estimates[sr.horse_name] = est_prob
            reasoning_map[sr.horse_name] = reasoning

        # Normalize per-horse estimates into a coherent distribution (sums to ~1.0)
        # so that edge = est_prob - 1/odds is a calibrated probability gap.
        if raw_strengths:
            normalized = FormAnalyzer.normalize_field(raw_strengths)
            for horse, prob in normalized.items():
                probability_estimates[horse] = round(prob, 4)

        # Apply LearningEngine adjustments to probability estimates
        if hasattr(self, 'learning') and self.learning:
            odds_map = {sr.horse_name: sr.odds_decimal for sr in scraped_race.runners}
            probability_estimates = self.learning.adjust_probabilities(
                probability_estimates,
                track=scraped_race.track,
                distance=scraped_race.distance,
                odds_map=odds_map,
            )

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
        """Send Telegram notification for a value bet (batched via digester)."""
        if not self.telegram or not self.digester:
            return

        try:
            icon = {
                "STRONG_VALUE": "🔥",
                "VALUE": "✅",
                "MARGINAL": "💛",
            }.get(value_bet.confidence, "📊")
            html = (
                f"{icon} <b>{value_bet.horse}</b> @ <b>{value_bet.track.title()}</b> "
                f"R{value_bet.race_number} ({value_bet.race_time})\n"
                f"💰 Odds: {value_bet.odds_decimal:.2f} | Edge: +{value_bet.edge_percent:.1f}%"
            )
            _fire_async(self.digester.push("value_bet", html))
        except Exception as e:
            print(f"[ERR] Failed to queue value bet notification: {e}")

    def place_bet(
        self,
        track: str,
        race_number: int,
        horse: str,
        odds: float,
        edge_percent: float,
        confidence: str,
        override_stake: Optional[float] = None,
        distance: Optional[int] = None,
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
            # Use Kelly-based stake from analyzer (DSI-scaled via track/race)
            max_stake = self.bankroll.calculate_max_stake(edge_percent, track, race_number)
            stake = min(max_stake, self.bankroll.current_bankroll * 0.05)

        # Record the bet
        bet = self.bankroll.record_bet(
            track=track,
            race_number=race_number,
            horse=horse,
            odds=odds,
            stake=stake,
            edge_percent=edge_percent,
            confidence=confidence,
            distance=distance,
        )

        if bet:
            actual_stake = getattr(bet, "stake", stake)
            print(f"[OK] Bet recorded: {horse} @ {odds} for R{actual_stake:.2f}")

            # Notify
            if self.telegram:
                _fire_async(self.telegram.send_message(
                    f"[NOTE] <b>Bet Placed</b>\n\n"
                    f"🐎 {horse}\n"
                    f"[LOC] {track} R{race_number}\n"
                    f"💰 Odds: {odds} | Stake: R{actual_stake:.2f}\n"
                    f"[STATS] Edge: +{edge_percent}%"
                ))

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
                distance=bet.distance,
                odds=bet.odds,
                stake=bet.stake,
                won=won,
                actual_return=bet.actual_return or 0.0,
            )
            profit_loss = (bet.actual_return or 0) - bet.stake

            print(f"[OK] Bet settled: {bet.horse} - {'Won' if won else 'Lost'}")

            # Notify
            if self.telegram:
                _fire_async(self.telegram.send_bet_result(
                    horse=bet.horse,
                    track=bet.track,
                    race_number=bet.race_number,
                    won=won,
                    stake=bet.stake,
                    returns=bet.actual_return or 0,
                    profit_loss=profit_loss,
                ))

        status = self.get_bankroll_status()
        status["settled"] = success
        return status

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

    async def get_active_tracks(self) -> List[str]:
        """Return list of active SA track names from Betway."""
        races = await self.betway.get_races()
        return list(set(r.track for r in races))

    async def run_daily_scan(
        self, tracks: Optional[List[str]] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict:
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

        # Start digester background loop if not already running
        if self.digester:
            await self.digester.start_async()

        # 1. Harvest Official PDF Tips FIRST
        from core_agent.skills.parsers.pdf_harvester import PDFHarvester

        pdf = PDFHarvester(memory=self.memory)
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

        # Store PDF race data for exotic analysis
        pdf_races = pdf_res.get("races", {})

        # 1b. Proactively harvest Computaform SA PDFs for ALL tracks
        # Ensures ChromaDB has trainer/jockey/ratings data for every track
        # before per-track analysis runs.
        print(f"\n  📥 Pre-fetching Computaform PDFs for {len(tracks)} tracks...")
        for track in tracks:
            try:
                cf_res = await pdf.get_latest_racing_intelligence(track, "Computaform SA")
                if cf_res.get("runners"):
                    print(f"    ✓ {track.title()}: {len(cf_res['runners'])} runners cached")
                else:
                    print(f"    - {track.title()}: no PDF (off-day or unavailable)")
            except Exception as e:
                print(f"    ✗ {track.title()}: {e}")
        print(f"  [PDF] Computaform harvest complete.\n")

        # 2. Legacy fallback
        all_results = {}
        total_value_bets = 0
        for i, track in enumerate(tracks):
            try:
                results = await self.scrape_and_analyze_track(track)
                all_results[track] = results
                if results:
                    total_value_bets += sum(
                        len(r.get("value_bets", []))
                        for r in results
                        if isinstance(r, dict)
                    )
                if progress_callback:
                    await progress_callback(track, i + 1, len(tracks))
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

        # 3. Exotic Analysis from PDF pool structure
        exotic_plays = []
        has_pool_structure = any(
            isinstance(r, dict) and r.get("leg_info")
            for r in pdf_races.values()
        )
        if has_pool_structure and all_results:
            print("\n[EXOTIC] Detected pool structure in PDF. Running exotic analysis...")
            exotic_plays = await self._analyze_exotic_pools(all_results, pdf_races)
            if exotic_plays:
                print(f"[EXOTIC] Found {len(exotic_plays)} exotic play(s)")
                if self.telegram:
                    try:
                        await self.telegram.send_exotic_plays(exotic_plays)
                    except Exception as e:
                        print(f"[ERR] Failed to send exotic alert: {e}")

        # Save exotic plays (empty or populated) to keep UI state in sync
        try:
            exotic_file = os.path.join(self.data_dir, "exotics_latest.json")
            with open(exotic_file, "w") as f:
                json.dump(exotic_plays, f, indent=2, default=str)
        except Exception as e:
            print(f"[WARN] Failed to save exotics_latest.json: {e}")

        if self.telegram:
            try:
                await self.telegram.send_daily_tips(all_results)
            except Exception as e:
                print(f"[ERR] Failed to send daily summary: {e}")

            # Send individual value bet notifications via Telegram based on settings
            try:
                settings_path = os.path.join(self.data_dir, "settings.json")
                telegram_enabled = True
                priority_only = False

                if os.path.exists(settings_path):
                    with open(settings_path) as f:
                        settings = json.load(f)
                    telegram_enabled = settings.get("telegramEnabled", True)
                    priority_only = settings.get("valueBetAlerts", False)

                if telegram_enabled:
                    for track, races in all_results.items():
                        for race in races:
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
                                max_stake = self.bankroll.calculate_max_stake(
                                    edge, track, race.get("race_number")
                                )
                                advised_stake = min(max_stake, self.bankroll.current_bankroll * 0.05)

                                # Determine confidence category
                                confidence = "STRONG_VALUE" if edge >= 15.0 else "VALUE" if edge >= 8.0 else "MARGINAL"

                                await self.telegram.send_value_bet(
                                    horse=horse,
                                    track=track,
                                    race_number=race.get("race_number", 0),
                                    race_time=race.get("race_time", "TBD"),
                                    odds=odds,
                                    edge_percent=edge,
                                    stake=advised_stake,
                                    confidence=confidence,
                                    reasoning=vb.get("reasoning", "Value detected by AI model analysis."),
                                )
            except Exception as e:
                print(f"[ERR] Failed to send individual value bet alerts: {e}")

        output_file = os.path.join(
            self.data_dir, f"daily_scan_{date.today().isoformat()}.json"
        )
        with open(output_file, "w") as f:
            json.dump(all_results, f, indent=2, default=str)

        # Save raw Betway snapshot for the HUD dashboard
        try:
            snapshot = await self.betway.get_snapshot_format()
            if snapshot.get("events"):
                snapshot_file = os.path.join(self.data_dir, "market_snapshot_latest.json")
                with open(snapshot_file, "w") as f:
                    json.dump(snapshot, f, indent=2, default=str)
                print(f"[OK] Saved market snapshot ({len(snapshot['events'])} events)")
        except Exception as e:
            print(f"[WARN] Could not save market snapshot: {e}")

        if _prometheus_enabled:
            try:
                gateway_url = os.getenv("PROMETHEUS_PUSHGATEWAY", "localhost:9091")
                push_to_gateway(
                    gateway_url, job="strike_tips_daily_scan", registry=REGISTRY
                )
            except Exception:
                pass

        # Auto-bet: place bets for qualifying value bets from daily scan
        auto_bets_placed = 0
        exotic_bets_placed = 0
        try:
            settings_path = os.path.join(self.data_dir, "settings.json")
            if os.path.exists(settings_path):
                with open(settings_path) as f:
                    settings = json.load(f)
                if settings.get("auto_bet_enabled", False):
                    min_edge = float(settings.get("auto_bet_min_edge", 5.5))
                    for track, races in all_results.items():
                        for race in races:
                            if not isinstance(race, dict):
                                continue
                            # Skip races where all value-bet odds are 5.0 placeholder (phantom value)
                            vb_odds = [
                                float(vb.get("odds_decimal", 0) or 0)
                                for vb in race.get("value_bets", [])
                            ]
                            real_vb_odds = [o for o in vb_odds if o > 0]
                            if real_vb_odds and all(o == 5.0 for o in real_vb_odds):
                                logger.info(
                                    "Auto-bet skip %s R%d: all value-bet odds are 5.0 placeholder",
                                    track, race.get("race_number", 0),
                                )
                                continue
                            for vb in race.get("value_bets", []):
                                horse = vb.get("horse") or ""
                                if not horse:
                                    continue
                                raw_edge = vb.get("edge_percent") or vb.get("edge") or vb.get("edge_percentage") or vb.get("estimated_edge") or 0
                                edge = float(raw_edge)
                                if 0 < edge < 1:
                                    edge *= 100
                                if edge < min_edge:
                                    continue
                                odds = resolve_auto_bet_odds(vb)
                                if odds is None:
                                    logger.info(
                                        "Auto-bet skip %s R%s: no bettable market odds for %s",
                                        track, race.get("race_number", 0), horse,
                                    )
                                    continue
                                bet = self.place_bet(
                                    horse=horse,
                                    track=track,
                                    race_number=race.get("race_number", 0),
                                    odds=odds,
                                    edge_percent=edge,
                                    confidence="AUTO",
                                )
                                if bet:
                                    auto_bets_placed += 1

                    # Auto-bet exotic plays
                    if exotic_plays:
                        ticket_cost = float(settings.get("exotic_ticket_cost", 1.2))
                        for play in exotic_plays:
                            pool = play.get("pool", "UNKNOWN")
                            legs = play.get("legs", [])
                            combos = play.get("combinations", [])
                            estimated_div = play.get("estimated_dividend", 2.0)
                            play_track = play.get("_track", list(all_results.keys())[0])
                            if not combos:
                                continue
                            bet = self.bankroll.record_exotic_bet(
                                track=play_track,
                                pool_type=pool,
                                pool_legs=legs,
                                combinations=combos,
                                ticket_cost=ticket_cost,
                                estimated_dividend=estimated_div,
                            )
                            if bet:
                                exotic_bets_placed += 1

                    if auto_bets_placed or exotic_bets_placed:
                        msg = f"🤖 <b>Daily Scan Auto-Bets</b>\n\n"
                        if auto_bets_placed:
                            msg += f"Placed {auto_bets_placed} value bet(s)\n"
                        if exotic_bets_placed:
                            msg += f"Placed {exotic_bets_placed} exotic play(s)"
                        print(f"[AUTO-BET] Placed {auto_bets_placed} win + {exotic_bets_placed} exotic bets")
                        if self.telegram:
                            await self.telegram.send_message(msg)
        except Exception as e:
            print(f"[ERR] Auto-bet placement failed: {e}")

        print(
            f"\n[OK] Scan complete! Found {total_value_bets} value bets across all tracks"
        )
        return {
            "date": date.today().isoformat(),
            "tracks_scanned": len(tracks),
            "total_value_bets": total_value_bets,
            "auto_bets_placed": auto_bets_placed,
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
        """Verify if a specific race is scheduled for today via Betway."""
        logger.info(f"Verifying race {race_num} at {track}")
        try:
            races = await self.betway.get_races()
            for race in races:
                if track.lower() in race.track.lower() and race.race_number == race_num:
                    return True
            return False
        except Exception as e:
            logger.error(f"Error verifying race {race_num} at {track}: {e}")
            return False

    async def close(self):
        """Clean up resources"""
        if self.digester:
            await self.digester.stop()
        if _PENDING_TG_TASKS:
            await asyncio.gather(*_PENDING_TG_TASKS, return_exceptions=True)
            _PENDING_TG_TASKS.clear()
        await self.scraper.close()
        if self.telegram:
            await self.telegram.close()


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
            print("\n Strike Tips AI - Interactive Mode")
            print("=" * 50)
            print("Type 'exit' or 'quit' to end session.")

            from core_agent.agent.providers.task_router import TaskRouter
            router = TaskRouter()

            while True:
                try:
                    user_input = input("\n> ").strip()
                    if user_input.lower() in ["exit", "quit"]:
                        break
                    if not user_input:
                        continue

                    messages = [
                        {"role": "system", "content": "You are Strike Tips AI, expert horse racing analyst."},
                        {"role": "user", "content": user_input},
                    ]
                    print("\n[AI] ", end="", flush=True)
                    async for chunk in router.stream(messages, None, None):
                        print(chunk, end="", flush=True)
                    print()
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
