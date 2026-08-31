import asyncio
import difflib
import glob
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

from core_agent.config.paths import MARKET_SNAPSHOT_PATH, INTEL_CACHE_DIR, ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH, DATA_DIR
from core_agent.core.alert_engine import AlertEngine
from core_agent.core.alert_digester import AlertDigester
from core_agent.skills.parsers.betway_api import BetwayAPI
try:
    from core_agent.skills.swarm_researcher import (
        enrich_snapshot_with_insights,
        run_swarm_loop,
    )
    _HAS_SWARM = True
except ImportError:
    _HAS_SWARM = False

    def enrich_snapshot_with_insights(state):  # no-op fallback
        return None

    async def run_swarm_loop(interval=600):
        return None
try:
    from core_agent.skills.parsers.racing_odds_api import RacingOddsAPI, _normalise
    _HAS_RACING_ODDS = True
except ImportError:
    _HAS_RACING_ODDS = False

    def _normalise(name: str) -> str:
        import re
        return re.sub(r"[^a-zA-Z0-9]", "", name).lower()

    class RacingOddsAPI:
        async def get_snapshot_format(self, target_date=None):
            return {"events": {}, "count": 0}

try:
    from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
    _HAS_ATR = True
except ImportError:
    _HAS_ATR = False

    class AtTheRacesAPI:
        async def get_results(self, date): return []
        async def get_market_movers(self): return []
        async def get_predictor(self): return []
try:
    from core_agent.skills.parsers.betfair_sa import BetfairSA, _normalise as _bf_normalise
    _HAS_BETFAIR_SA = True
except ImportError:
    _HAS_BETFAIR_SA = False

    def _bf_normalise(name: str) -> str:
        return "".join(c for c in name.lower() if c.isalnum())

    class BetfairSA:
        async def get_form_format(self) -> dict:
            return {"events": {}, "count": 0}
from core_agent.core.intelligence_cache_manager import IntelligenceCacheManager

HEALING_EVENTS_PATH = os.path.join("data", "healing_events.json")


def _norm_time(t: str) -> str:
    """Normalise race time to HH:MM format."""
    return t.replace("-", ":").replace(".", ":").strip()


def _parse_race_off_time(t_str: str, race_date: datetime = None) -> Optional[datetime]:
    """Parse HH:MM race time into a datetime for off-time comparison."""
    if not t_str or ":" not in t_str:
        return None
    try:
        parts = t_str.strip().split(":")
        h, m = int(parts[0]), int(parts[1])
        base = race_date or datetime.now()
        return base.replace(hour=h, minute=m, second=0, microsecond=0)
    except (ValueError, IndexError):
        return None


def _close_overdue_races(events: dict, max_minutes_after_off: int = 5) -> dict:
    """Remove races whose scheduled off-time has passed by > max_minutes_after_off.
    
    Catches races where Betway never sets isFinished (common for UK/Ireland tracks).
    """
    now = datetime.now()
    filtered = {}
    for eid, e in events.items():
        t_str = e.get("t") or e.get("st")
        off_time = _parse_race_off_time(t_str) if t_str else None
        if off_time and (now - off_time).total_seconds() > max_minutes_after_off * 60:
            logger.info(f"Race auto-closed by off-time: {e.get('en','?')} R{e.get('raceNumber','?')} (off {t_str}, now {now.strftime('%H:%M')})")
            continue
        filtered[eid] = e
    return filtered


def _norm_course(c: str) -> str:
    """Normalise course name for cross-source matching."""
    n = c.lower().strip()
    n = n.replace(" racecourse", "").replace(" park", "").strip()
    # Also normalise hyphens: "Lingfield Park" vs "lingfield-park"
    n = n.replace("-", " ").replace("_", " ").strip()
    return _normalise(n)


def _merge_ro_into(betway_state: dict, ro_snapshot: dict):
    """Inject racing-odds.com data into matching Betway events/runners.

    Matches by (date, course, time) with fuzzy fallbacks for
    date offsets (±1 day), course name variations, and horse name
    variations via difflib.
    """
    ro_events = ro_snapshot.get("events", {})
    if not ro_events:
        logger.info("Racing-Odds returned no events -- skipping merge")
        return

    # Build lookup keyed by (date, course)
    ro_lookup: Dict[str, Dict] = {}
    for e in ro_events.values():
        date = e.get("date", "")
        key = f"{date}|{_norm_course(e.get('course',''))}|{_norm_time(e.get('t',''))}"
        ro_lookup[key] = {
            "horses": {_normalise(r["name"]): r for r in e.get("runners", [])},
            "horse_names": [_normalise(r["name"]) for r in e.get("runners", [])],
            "original_horses": {_normalise(r["name"]): r["name"] for r in e.get("runners", [])},
        }

    today_str = datetime.now().strftime("%Y-%m-%d")
    # Also try yesterday / tomorrow for date-offset matching
    date_candidates = [today_str]
    try:
        dt = datetime.strptime(today_str, "%Y-%m-%d")
        date_candidates.append((dt - timedelta(days=1)).strftime("%Y-%m-%d"))
        date_candidates.append((dt + timedelta(days=1)).strftime("%Y-%m-%d"))
    except ValueError:
        pass

    merged_races = 0
    fuzzy_horse_matches = 0
    for event in betway_state.get("events", {}).values():
        bw_course = _norm_course(event.get("course", ""))
        bw_time = _norm_time(event.get("t", ""))
        ro_match = None

        # Try exact match across candidate dates
        for d in date_candidates:
            key = f"{d}|{bw_course}|{bw_time}"
            ro_match = ro_lookup.get(key)
            if ro_match:
                break

        # Fallback: try fuzzy course matching (strip more aggressively)
        if not ro_match:
            bw_course_stripped = bw_course.replace("park", "").replace("racecourse", "").replace(" ", "").strip()
            for d in date_candidates:
                for rok, rov in ro_lookup.items():
                    rok_course = _norm_course(rok.split("|")[1]) if "|" in rok else ""
                    rok_stripped = rok_course.replace("park", "").replace("racecourse", "").replace(" ", "").strip()
                    if rok_stripped == bw_course_stripped and rok.endswith(f"|{bw_time}"):
                        ro_match = rov
                        break
                if ro_match:
                    break

        if not ro_match:
            continue

        merged_races += 1
        for runner in event.get("runners", []):
            rn = _normalise(runner.get("name", ""))
            ro_horse = ro_match["horses"].get(rn)
            if not ro_horse:
                # Fuzzy horse name matching
                matches = difflib.get_close_matches(rn, ro_match["horse_names"], n=1, cutoff=0.6)
                if matches:
                    ro_horse = ro_match["horses"].get(matches[0])
                    fuzzy_horse_matches += 1
            if ro_horse:
                runner["ro_odds"] = ro_horse.get("odds")
                runner["ro_bookmakers"] = ro_horse.get("ro_bookmakers", {})

    logger.info(
        "Racing-Odds merged into %d/%d Betway races (fuzzy horse matches: %d)",
        merged_races, len(betway_state.get("events", {})), fuzzy_horse_matches,
    )


def _merge_bf_into(betway_state: dict, bf_snapshot: dict) -> None:
    """Inject Betfair SA form data (gear + days since last run) into matching
    Betway events/runners. Adds two optional fields per runner; never modifies
    existing snapshot fields, never raises.

    Matching: scope per (course, time). Horse names: exact-first (whitespace/
    case-normalized) then ``difflib`` fuzzy (0.6 cutoff). One-to-one
    assignment: already-matched Betfair runners are excluded from later
    candidate pools so two SA horses with similar names can't swap gear.
    """
    bf_events = bf_snapshot.get("events") if isinstance(bf_snapshot, dict) else None
    if not bf_events:
        logger.info("Betfair SA returned no events -- skipping merge")
        return

    merged_races = 0
    fuzzy_horse_matches = 0
    for event in betway_state.get("events", {}).values():
        course_key = _norm_course(event.get("course", ""))
        time_key = _norm_time(event.get("t", ""))
        if not course_key or not time_key:
            continue

        bf_match = None
        for bf in bf_events.values():
            if not isinstance(bf, dict):
                continue
            if _norm_course(bf.get("course", "")) != course_key:
                continue
            if _norm_time(bf.get("t", "")) != time_key:
                continue
            bf_match = bf
            break
        if not bf_match:
            continue

        bf_runners = bf_match.get("runners") or []
        if not bf_runners:
            continue

        matched_bf_indices: set = set()
        for bw_runner in event.get("runners") or []:
            bw_name = (bw_runner.get("name") or bw_runner.get("outcomeName") or "").strip()
            if not bw_name:
                continue
            bw_norm = _bf_normalise(bw_name)

            # 1. Exact match (case + whitespace insensitive)
            chosen_idx = -1
            for i, r in enumerate(bf_runners):
                if i in matched_bf_indices:
                    continue
                bf_name = (r.get("name") or "").strip()
                if bf_name and _bf_normalise(bf_name) == bw_norm:
                    chosen_idx = i
                    break

            # 2. Fuzzy fallback (0.6 cutoff, one-to-one)
            if chosen_idx < 0:
                candidates = [
                    (i, _bf_normalise(r.get("name") or ""))
                    for i, r in enumerate(bf_runners)
                    if i not in matched_bf_indices and r.get("name")
                ]
                if not candidates:
                    continue
                matches = difflib.get_close_matches(
                    bw_norm,
                    [n for _, n in candidates],
                    n=1,
                    cutoff=0.6,
                )
                if matches:
                    target_norm = matches[0]
                    for i, n in candidates:
                        if n == target_norm:
                            chosen_idx = i
                            fuzzy_horse_matches += 1
                            break

            if chosen_idx < 0:
                continue
            matched_bf_indices.add(chosen_idx)
            bf_runner = bf_runners[chosen_idx]

            # 3. Attach (additive only; never overwrite existing fields)
            gear = bf_runner.get("gear")
            days = bf_runner.get("daysSinceRun")
            if gear and "gear" not in bw_runner:
                bw_runner["gear"] = gear
            if days is not None and "daysSinceRun" not in bw_runner:
                bw_runner["daysSinceRun"] = days
        merged_races += 1

    logger.info(
        "Betfair SA merged into %d/%d Betway races (fuzzy horse matches: %d)",
        merged_races, len(betway_state.get("events", {})), fuzzy_horse_matches,
    )


def _merge_daily_scan_into(state: dict):
    """Merge today's daily scan value bets, favorites, and outsiders into active events."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    daily_scan_file = os.path.join(str(DATA_DIR), f"daily_scan_{today_str}.json")

    scan_data = {}
    if os.path.exists(daily_scan_file):
        try:
            with open(daily_scan_file, "r") as f:
                scan_data = json.load(f)
        except Exception as e:
            logger.debug("Failed to read daily scan JSON: %s", e)

    # Normalize track keys in scan_data
    scan_lookup = {}
    if isinstance(scan_data, dict):
        for track_name, races in scan_data.items():
            if isinstance(races, list):
                scan_lookup[track_name.lower().replace(" ", "")] = races

    for event in state.get("events", {}).values():
        course_norm = _norm_course(event.get("course", ""))
        race_num = event.get("raceNumber")
        if race_num is None:
            continue
        try:
            race_num = int(race_num)
        except ValueError:
            continue

        # Extract runners from event
        runners_list = event.get("runners", [])
        if not runners_list:
            continue

        # 1. Determine Favourite from live market odds (lowest decimal odds > 1.0)
        fav_runner = None
        min_odds = 9999.0
        for r in runners_list:
            try:
                odds_val = float(r.get("odds", 9999.0))
                if 1.0 < odds_val < min_odds:
                    min_odds = odds_val
                    fav_runner = r
            except (ValueError, TypeError):
                pass
        if not fav_runner:
            fav_runner = runners_list[0]

        # 2. Determine Outsider from live market odds (highest decimal odds)
        max_live_odds = -1.0
        live_outsider_runner = None
        for r in runners_list:
            try:
                odds_val = float(r.get("odds", 0.0))
                if odds_val > max_live_odds:
                    max_live_odds = odds_val
                    live_outsider_runner = r
            except (ValueError, TypeError):
                pass
        if not live_outsider_runner:
            live_outsider_runner = runners_list[-1]

        # Look up track and race in scan data
        scanned_race = None
        races_list = scan_lookup.get(course_norm.replace(" ", ""))
        if races_list:
            scanned_race = next((r for r in races_list if r.get("race_number") == race_num), None)

        val_runner = None
        outsider_runner = None

        if scanned_race:
            value_bets = scanned_race.get("value_bets", [])
            max_edge = 0.0
            max_outsider_odds = 0.0

            for vb in value_bets:
                vb_horse = _normalise(vb.get("horse", ""))
                edge = float(vb.get("edge_percent", 0.0) or vb.get("edge", 0.0))
                odds_dec = float(vb.get("odds_decimal", 0.0) or vb.get("odds", 0.0) or 2.0)

                # Match with runner in event
                matched_r = None
                for r in runners_list:
                    if _normalise(r.get("name", "")) == vb_horse:
                        matched_r = r
                        break
                
                if not matched_r:
                    # Fuzzy fallback
                    import difflib
                    names = [r.get("name", "") for r in runners_list]
                    norm_names = [_normalise(n) for n in names]
                    matches = difflib.get_close_matches(vb_horse, norm_names, n=1, cutoff=0.7)
                    if matches:
                        matched_idx = norm_names.index(matches[0])
                        matched_r = runners_list[matched_idx]

                if matched_r:
                    # Set runner's edge and probability
                    matched_r["edge"] = edge
                    matched_r["winProbability"] = float(vb.get("estimated_probability", 0.0))

                    # Track highest edge for the "Value Bet" option
                    if edge > max_edge:
                        max_edge = edge
                        val_runner = matched_r

                    # Track "Shout-Outsider" (value bet with odds >= 8.0)
                    if odds_dec >= 8.0 and odds_dec > max_outsider_odds:
                        max_outsider_odds = odds_dec
                        outsider_runner = matched_r

        # Populate payload with strict fallbacks
        event["aiSelections"] = {
            "value": val_runner or runners_list[0],
            "favourite": fav_runner or runners_list[0],
            "outsider": outsider_runner or live_outsider_runner or runners_list[-1]
        }


def _atomic_write_json(path: str, data: any, indent: int = 2):
    """Write data to a JSON file atomically to prevent corruption on crash"""
    tmp_path = str(path) + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=indent, default=str)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception as e:
        print(f"[WARN] Failed atomic write to {path}: {e}")


def _write_healing_event(action: str, details: str, agent: str = "OddsMonitor", status: str = "SUCCESS"):
    """Append a healing event to the shared log file atomically."""
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
        _atomic_write_json(HEALING_EVENTS_PATH, events[-50:])  # keep last 50
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
        self._telegram_notifier: Optional[TelegramNotifier] = None
        try:
            from core_agent.skills.notifications.telegram_bot import TelegramNotifier
            self._telegram_notifier = TelegramNotifier()
        except Exception:
            pass

        self._digester: Optional[AlertDigester] = None
        if self._telegram_notifier:
            self._digester = AlertDigester(self._telegram_notifier)
            self._digester.start()

        self.alert_engine = AlertEngine(
            notification_callback=self._on_alert
        )
        self.betway = BetwayAPI()
        self.racing_odds = RacingOddsAPI()
        self.betfair = BetfairSA()
        self.at_races = AtTheRacesAPI()
        # Last-good cache path for Betfair form data (used when a cycle fails
        # so the snapshot still carries gear/days from the most recent good fetch).
        self._bf_last_good_path = os.path.join(str(DATA_DIR), "betfair_form_last_good.json")

        self.monitoring_active = True
        self._last_alert_ts: float = 0
        self._alert_cooldown: float = 120.0

    async def _fetch_betfair_form_safely(self) -> dict:
        """Fetch Betfair SA form data with last-good-cache reuse.

        On success: persist to ``_bf_last_good_path`` so a future failed cycle
        can fall back to the most recent good snapshot. On failure: read the
        last-good cache; if missing or stale (>6h), log a healing event and
        return an empty snapshot so the merge is a no-op (never breaks the
        main cycle).
        """
        empty = {"events": {}, "count": 0}
        cache_max_age = 6 * 60 * 60  # 6 hours
        try:
            form = await self.betfair.get_form_format()
        except Exception as e:
            _write_healing_event(
                "BETFAIR_FETCH_FAIL",
                f"Betfair SA fetch raised: {e!r}",
                agent="OddsMonitor",
                status="WARN",
            )
            return self._load_bf_last_good(cache_max_age) or empty

        if not form or not form.get("events"):
            _write_healing_event(
                "BETFAIR_EMPTY",
                "Betfair SA returned no events this cycle",
                agent="OddsMonitor",
                status="WARN",
            )
            return self._load_bf_last_good(cache_max_age) or empty

        # Persist the good snapshot for fallback on future failure.
        try:
            import json as _json
            with open(self._bf_last_good_path, "w") as f:
                _json.dump(
                    {"saved_at": datetime.now().isoformat(), "events": form.get("events", {})},
                    f,
                )
        except Exception as e:
            logger.debug("Betfair SA last-good cache write failed: %s", e)
        return form

    def _load_bf_last_good(self, max_age_secs: int) -> Optional[dict]:
        try:
            import json as _json
            import time as _time
            if not os.path.exists(self._bf_last_good_path):
                return None
            with open(self._bf_last_good_path) as f:
                cached = _json.load(f)
            saved_at = cached.get("saved_at")
            ts = (
                datetime.fromisoformat(saved_at).timestamp() if saved_at else 0
            )
            if _time.time() - ts > max_age_secs:
                _write_healing_event(
                    "BETFAIR_CACHE_STALE",
                    f"Betfair SA last-good cache older than {max_age_secs}s",
                    agent="OddsMonitor",
                    status="WARN",
                )
                return None
            return {
                "events": cached.get("events") or {},
                "count": len(cached.get("events") or {}),
            }
        except Exception as e:
            logger.debug("Betfair SA last-good cache read failed: %s", e)
            return None

    async def _on_alert(self, msg: dict):
        """Callback fired by AlertEngine when a condition triggers."""
        if not self._telegram_notifier or not self._digester:
            return
        now = datetime.now().timestamp()
        if now - self._last_alert_ts < self._alert_cooldown:
            logger.info(f"Alert rate-limited: {msg.get('type')} {msg.get('horse')} @ {msg.get('course')}")
            return
        self._last_alert_ts = now
        tag = msg.get("type", "alert")
        horse = msg.get("horse", "?")
        course = msg.get("course", "?")
        odds = msg.get("odds", "?")
        html = (
            f"🐎 {horse} @ {course}\n"
            f"💰 Odds: {odds}"
        )
        if tag in ("odds_drop", "value_bet"):
            await self._digester.push(tag, html)
        else:
            await self._digester.push_critical(tag, html)

    async def initialize(self):
        await self.alert_engine.initialize()
        self.events_cache = self.intel_cache.rehydrate()

    async def run(self):
        await self.initialize()
        if self._digester:
            await self._digester.start_async()

        # Start heartbeat loop — generates dreams + saves to ChromaDB every 5min
        from core_agent.core.heartbeat import run_heartbeat_loop
        from core_agent.skills.memory.chroma_memory import RacingMemory
        _memory = RacingMemory()
        asyncio.create_task(run_heartbeat_loop(_memory))

        # Start swarm researcher — fills missing form insights across all regions + polls news
        if _HAS_SWARM:
            asyncio.create_task(run_swarm_loop(interval=600))

        logger.info("🚀 L7 Monitor Active (Refactored: Pure Python Mode)")
        self._atr_cycle = 0

        active_count = 0

        while self.monitoring_active:
            self._atr_cycle += 1
            try:
                today_str = datetime.now().strftime("%Y-%m-%d")
                # 1. Fetch Betway + Racing-Odds in parallel
                bw_task = asyncio.create_task(self.betway.get_snapshot_format())
                ro_task = asyncio.create_task(self.racing_odds.get_snapshot_format(target_date=today_str))
                bf_task = asyncio.create_task(self._fetch_betfair_form_safely())
                state = await bw_task
                try:
                    ro_snapshot = await ro_task
                except Exception:
                    ro_snapshot = {"events": {}, "count": 0}
                    logger.debug("Racing-Odds snapshot failed, skipping merge")

                try:
                    bf_snapshot = await bf_task
                except Exception:
                    bf_snapshot = {"events": {}, "count": 0}
                    logger.debug("Betfair SA form fetch failed, skipping merge")

                # 1b. Merge Racing-Odds data into Betway events where race/horse match
                _merge_ro_into(state, ro_snapshot)

                # 1c. Merge Betfair SA form (gear + days since last run) -- additive only
                _merge_bf_into(state, bf_snapshot)

                # 2. Persistence & Pruning
                # Remove Betway-finished races and normalize names
                active = {
                    eid: {**e, "en": " ".join(e.get("en", "").split())}
                    for eid, e in state.get("events", {}).items()
                    if not e.get("isFinished")
                }
                # Off-time closure — catches races Betway never flags (common for UK/Ireland)
                state["events"] = _close_overdue_races(active)
                state["count"] = len(state["events"])
                state["timestamp"] = datetime.now().isoformat()
                active_ids = list(state["events"].keys())
                active_count = len(active_ids)

                _merge_daily_scan_into(state)
                _atomic_write_json(MARKET_SNAPSHOT_PATH, state)
                # Swarm enrichment: zero-cost field insights for every region without
                # Betway timeForm (USA/Japan/SA/...). Runs inline, never blocks the loop.
                try:
                    enrich_snapshot_with_insights(state)
                except Exception as e:
                    logger.debug(f"Swarm enrichment skipped: {e}")
                try:
                    from core_agent.core.snapshot_cache import set_snapshot, publish_snapshot
                    from core_agent.core.task_queue import get_redis
                    set_snapshot(state)
                    redis_client = await get_redis()
                    await publish_snapshot(redis_client, state)
                except Exception:
                    pass

                # Push snapshot to Cloudflare KV (free, always-on reads for HUD/Telegram)
                try:
                    import httpx
                    cf_url = os.environ.get("CLOUDFLARE_MCP_URL", "")
                    cf_key = os.environ.get("CLOUDFLARE_API_KEY", "")
                    if cf_url and cf_key:
                        async with httpx.AsyncClient(timeout=15) as client:
                            resp = await client.post(
                                f"{cf_url.rstrip('/')}/api/ingest-snapshot",
                                headers={"x-api-key": cf_key, "content-type": "application/json"},
                                json=state,
                            )
                            if resp.status_code not in (200, 201):
                                logger.warning("Cloudflare push returned %d: %.100s", resp.status_code, resp.text)
                            else:
                                logger.debug("Cloudflare snapshot pushed (%d events)", state.get("count", 0))
                except Exception as exc:
                    logger.debug("Cloudflare push skipped: %s", exc)

                # 1c. ATR data — fetch every cycle for maximum freshness
                if True:
                    try:
                        atr_results_yesterday = await self.at_races.get_results("yesterday")
                    except Exception as e:
                        atr_results_yesterday = None
                        logger.debug("ATR yesterday results fetch skipped: %s", e)
                    try:
                        atr_results_today = await self.at_races.get_results("today")
                    except Exception as e:
                        atr_results_today = None
                        logger.debug("ATR today results fetch skipped: %s", e)
                    all_results = (atr_results_yesterday or []) + (atr_results_today or [])
                    if all_results:
                        _atomic_write_json(ATR_RESULTS_PATH, {"results": all_results, "timestamp": datetime.now().isoformat()})

                    try:
                        atr_movers = await self.at_races.get_market_movers()
                        if atr_movers:
                            _atomic_write_json(ATR_MOVERS_PATH, {"movers": atr_movers, "timestamp": datetime.now().isoformat()})
                    except Exception as e:
                        logger.debug("ATR movers fetch skipped: %s", e)

                    try:
                        atr_predictions = await self.at_races.get_predictor()
                        if atr_predictions:
                            _atomic_write_json(ATR_PREDICTOR_PATH, {"predictions": atr_predictions, "timestamp": datetime.now().isoformat()})
                    except Exception as e:
                        logger.debug("ATR predictor fetch skipped: %s", e)
                else:
                    logger.debug("Skipping ATR fetches (no active races, cycle %d)", self._atr_cycle)

                # Check ATR snapshot staleness and alert if needed
                await self._check_atr_staleness()

                # TTL-based cleanup of old ATR snapshots (keep last 7 days)
                await self._cleanup_atr_snapshots()

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

            # Dynamic sleep — poll aggressively when races are live, back off when idle
            sleep_secs = 15 if active_count > 0 else 300
            logger.debug("Monitor sleep %ds (active_races=%d)", sleep_secs, active_count)
            await asyncio.sleep(sleep_secs)

    async def _check_atr_staleness(self, max_age_hours: int = 3) -> None:
        """Alert if ATR snapshots haven't been updated within max_age_hours."""
        from core_agent.config.paths import ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH
        import json
        now = datetime.now()
        stale_alerts = []
        for path, name in [
            (ATR_RESULTS_PATH, "ATR Results"),
            (ATR_MOVERS_PATH, "ATR Market Movers"),
            (ATR_PREDICTOR_PATH, "ATR Predictor"),
        ]:
            if path.exists():
                try:
                    data = json.loads(path.read_text())
                    ts_str = data.get("timestamp")
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str)
                        age_hours = (now - ts).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            stale_alerts.append(f"{name} stale ({age_hours:.1f}h old, last: {ts_str[:19]})")
                    else:
                        stale_alerts.append(f"{name} missing timestamp")
                except Exception:
                    stale_alerts.append(f"{name} unreadable")
            else:
                stale_alerts.append(f"{name} missing file")
        if stale_alerts:
            msg = " | ".join(stale_alerts)
            logger.warning(f"🚨 ATR STALENESS: {msg}")
            try:
                from core_agent.core.alert_engine import AlertEngine
                if not hasattr(self, "_staleness_alerted"):
                    self._staleness_alerted = set()
                alert_key = f"atr_staleness_{hash(msg)}"
                if alert_key not in self._staleness_alerted:
                    self._staleness_alerted.add(alert_key)
                    # Fire a one-time alert via alert engine (non-blocking)
                    from core_agent.core.alert_engine import AlertEngine
                    alert_engine = AlertEngine()
                    await alert_engine._fire_async(
                        "atr_staleness", msg, {"max_age_hours": max_age_hours, "details": stale_alerts}
                    )
            except Exception:
                pass

    async def _cleanup_atr_snapshots(self, ttl_days: int = 7) -> None:
        """Remove ATR snapshot files older than ttl_days (keeps latest, removes backup copies if any)."""
        from core_agent.config.paths import DATA_DIR
        import glob
        from datetime import datetime
        now = datetime.now()
        for pattern in ["atr_*_snapshot.json", "atr_*_snapshot.json.*"]:
            for path_str in glob.glob(str(DATA_DIR / pattern)):
                try:
                    path = Path(path_str)
                    # Keep the main snapshot files
                    if path.name in ["atr_results_snapshot.json", "atr_movers_snapshot.json", "atr_predictor_snapshot.json"]:
                        continue
                    # Remove backup/old copies older than TTL
                    mtime = datetime.fromtimestamp(path.stat().st_mtime)
                    age_days = (now - mtime).days
                    if age_days > ttl_days:
                        path.unlink()
                        logger.info(f"🧹 Cleaned up old ATR snapshot: {path.name} ({age_days}d old)")
                except Exception as e:
                    logger.debug(f"ATR cleanup skipped {path_str}: {e}")

    async def close(self):
        """Clean up resources (digester, etc.)."""
        self.monitoring_active = False
        if self._digester:
            await self._digester.stop()


if __name__ == "__main__":
    monitor = AdaptiveOddsMonitor()
    asyncio.run(monitor.run())
