import asyncio
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from core_agent.config.paths import DATA_DIR

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AlertEngine")


@dataclass
class AlertCondition:
    """Represents a betting alert condition."""

    id: str
    race_course: str
    horse_name: Optional[str]
    condition_type: str  # 'odds_drop', 'odds_rise', 'value_bet', 'threshold'
    condition_value: str
    notification_channels: List[str]
    active: bool = True
    cooldown_minutes: int = 5


class AlertEngine:
    """
    Intelligence system evaluating odds changes for value opportunities.
    Ported from User's Gold Standard Project.
    """

    def __init__(self, notification_callback=None, data_dir=None):
        self.notification_callback = notification_callback
        self.data_dir = data_dir or str(DATA_DIR)
        self.alerts_file = os.path.join(self.data_dir, "alert_conditions.json")
        self.history_file = os.path.join(self.data_dir, "alert_history.json")
        # Odds-journey store (Alert Digest v2): first-seen odds per
        # (day, course, race, horse) so digests show open → latest trails.
        # Day-scoped (pruned on load); persisted on every alert push so
        # container churn never loses the morning's opens.
        self.journey_file = os.path.join(self.data_dir, "odds_journey.json")
        self._journey: Dict[str, dict] = {}

        self.alerts_cache: Dict[str, AlertCondition] = {}
        self.last_trigger_times: Dict[str, datetime] = {}
        self.last_alerted_odds: Dict[str, float] = {}  # Track last odds we alerted on for each key
        # Per-race cooldown to prevent alert bursts from same race
        self.last_race_alert_time: Dict[str, datetime] = {}
        self.race_cooldown_minutes = 10  # Minimum minutes between alerts for same race

        self.stats = {
            "total_evaluations": 0,
            "alerts_triggered": 0,
            "notifications_sent": 0,
            "cooldown_prevents": 0,
            "race_cooldown_prevents": 0,
        }

    async def initialize(self):
        """Initialize the engine and load settings."""
        os.makedirs(self.data_dir, exist_ok=True)
        await self._load_alerts()
        await self.clear_history()
        self._load_journey()
        logger.info(
            f"🚀 Alert Engine Active: Loaded {len(self.alerts_cache)} conditions."
        )

    def _journey_key(self, course: str, race: str, horse: str) -> str:
        return f"{datetime.now().date().isoformat()}|{course}|{race}|{horse}"

    def _load_journey(self) -> None:
        """Load today's journey entries; drop any other day (self-cleans)."""
        try:
            with open(self.journey_file) as f:
                data = json.load(f)
            today = datetime.now().date().isoformat()
            if isinstance(data, dict):
                self._journey = {
                    k: v for k, v in data.items()
                    if isinstance(k, str) and k.startswith(today + "|")
                }
        except Exception:
            self._journey = {}

    def _save_journey(self) -> None:
        try:
            with open(self.journey_file, "w") as f:
                json.dump(self._journey, f)
        except Exception as e:
            logger.debug("Journey persist failed: %s", e)

    def _record_sighting(self, course: str, race: str, horse: str,
                         odds: Optional[float]) -> dict:
        """Record one observation; return the journey entry (creates the
        open on first sighting of the day). Never raises."""
        try:
            key = self._journey_key(course, race, horse)
            now = datetime.now().isoformat(timespec="minutes")
            entry = self._journey.get(key)
            if entry is None:
                entry = {"open": odds, "open_at": now, "min": odds,
                         "max": odds, "latest": odds, "latest_at": now}
                self._journey[key] = entry
            elif odds is not None:
                entry["latest"] = odds
                entry["latest_at"] = now
                try:
                    if entry.get("min") is None or odds < entry["min"]:
                        entry["min"] = odds
                    if entry.get("max") is None or odds > entry["max"]:
                        entry["max"] = odds
                except TypeError:
                    pass
            return entry
        except Exception:
            return {}

    @staticmethod
    def _race_context(race_data: Dict[str, Any]) -> Dict[str, Any]:
        """Race number + off-time + minutes-to-off from monitor event shape.
        Best-effort: anything unparseable is omitted, never fatal."""
        out: Dict[str, Any] = {}
        try:
            rn = race_data.get("raceNumber", race_data.get("race_number"))
            if rn is not None:
                out["race"] = str(rn)
        except Exception:
            pass
        off_raw = None
        for k in ("bf_off_time", "off_time", "offTime", "time", "start_time"):
            try:
                v = race_data.get(k)
            except Exception:
                v = None
            if v:
                off_raw = str(v)
                break
        if off_raw:
            out["off"] = off_raw
            try:
                import re as _re
                m = _re.search(r"(\d{1,2}):(\d{2})", off_raw)
                if m:
                    now = datetime.now()
                    off = now.replace(hour=int(m.group(1)),
                                      minute=int(m.group(2)),
                                      second=0, microsecond=0)
                    mins = int((off - now).total_seconds() // 60)
                    if -120 <= mins <= 600:
                        out["mins_to_off"] = mins
            except Exception:
                pass
        return out

    # Allowlisted enrichment fields (Betfair snapshot shape → digest rows).
    # Anything absent is skipped at render, never crashes.
    ENRICH_KEYS = (
        "trainer_name", "trainer", "jockey_claim", "jockey",
        "form", "days_since_last_run", "days", "official_rating",
        "rating", "edge",
    )

    @classmethod
    def _enrichment(cls, horse: Dict[str, Any]) -> Dict[str, Any]:
        out: Dict[str, Any] = {}
        try:
            for k in cls.ENRICH_KEYS:
                v = horse.get(k)
                if v is None or v == "":
                    continue
                out[k] = v
        except Exception:
            pass
        return out

    async def clear_history(self):
        """Wipe triggered alert history (call at startup to flush stale entries)."""
        try:
            if os.path.exists(self.history_file):
                os.remove(self.history_file)
                logger.info("Cleared stale alert history")
        except Exception as e:
            logger.warning("Failed to clear alert history: %s", e)

    async def _load_alerts(self):
        """Load alerts from local JSON storage, overriding stale default conditions."""
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, "r") as f:
                    data = json.load(f)
                for item in data:
                    alert = AlertCondition(**item)
                    if alert.condition_type == "value_bet":
                        continue
                    self.alerts_cache[alert.id] = alert
            except Exception as e:
                logger.error(f"Failed to load alerts: {e}")

        if not self.alerts_cache:
            self._add_default_alerts()
            await self._save_alerts()

    def _add_default_alerts(self):
        """Standard L7 baseline alerts — conservative to avoid spam."""
        defaults = [
            AlertCondition(
                id="global_odds_drop",
                race_course="Any",
                horse_name=None,
                condition_type="odds_drop",
                condition_value="15%",
                notification_channels=["telegram", "websocket"],
            ),
        ]
        for a in defaults:
            self.alerts_cache[a.id] = a

    async def _save_alerts(self):
        """Persist alert settings."""
        with open(self.alerts_file, "w") as f:
            json.dump([asdict(a) for a in self.alerts_cache.values()], f, indent=4)

    async def evaluate_odds_update(self, race_data: Dict[str, Any], cache=None):
        """Evaluate a fresh race update against all conditions."""
        self.stats["total_evaluations"] += 1

        course = race_data.get("course", "Unknown")
        horses = race_data.get("runners", []) or race_data.get("horses", [])

        for alert in self.alerts_cache.values():
            if not alert.active:
                continue

            if (
                alert.race_course != "Any"
                and alert.race_course.lower() != course.lower()
            ):
                continue

            for horse in horses:
                name = horse.get("name", "Unknown")

                if alert.horse_name and alert.horse_name.lower() != name.lower():
                    continue

                # Journey sighting (Alert Digest v2): record every observed
                # price so opens exist before any alert fires. Read-only w.r.t.
                # alert behavior — failures are swallowed inside.
                try:
                    _ctx0 = self._race_context(race_data)
                    _o0 = self._parse_odds(str(horse.get("odds", "")))
                    self._record_sighting(course, _ctx0.get("race", "?"),
                                          name, _o0)
                except Exception:
                    pass

                if await self._evaluate_condition(alert, horse, race_data, cache):
                    await self._trigger_alert(alert, horse, race_data)

    async def _evaluate_condition(
        self, alert: AlertCondition, horse: Dict, race_data: Dict, cache=None
    ) -> bool:
        """Core math evaluation logic with race status awareness and odds-change threshold."""
        try:
            # Skip if race is not upcoming (prevents alerts on finished races)
            status = race_data.get("status", race_data.get("race_status", "")).lower()
            # Expanded list of statuses that indicate race is not available for betting
            finished_statuses = [
                "in progress", "finished", "result", "result", "completed", "off",
                "closed", "settled", "voided", "non-runner", "withdrawn",
                "race completed", "race off", "postponed", "cancelled", "void"
            ]
            if status in finished_statuses:
                return False
                
            # Create unique key for this alert condition
            key = f"{alert.id}_{race_data.get('course', 'Unknown')}_{horse.get('name', 'Unknown')}"
            current_odds_str = str(horse.get("odds", "1/1"))
            
            # Skip SP — no real price yet
            if current_odds_str.upper() == "SP":
                return False
            current_odds = self._parse_odds(current_odds_str)
            
            # ODDS-CHANGE THRESHOLD: Require meaningful change before re-alerting
            # Only apply to odds-based alerts (odds_drop, odds_rise, threshold)
            if alert.condition_type in ["odds_drop", "odds_rise", "threshold"]:
                last_alerted = self.last_alerted_odds.get(key)
                if last_alerted is not None:
                    # Require at least 5% change in odds or 0.5 minimum absolute change
                    odds_change_pct = abs(current_odds - last_alerted) / last_alerted if last_alerted > 0 else float('inf')
                    odds_change_abs = abs(current_odds - last_alerted)
                    if odds_change_pct < 0.05 and odds_change_abs < 0.5:
                        # Odds haven't changed enough to warrant re-alerting
                        return False
            val = alert.condition_value

            # GLOBAL GUARD: Check if race has placeholder odds (all odds equal)
            runners = race_data.get("runners", [])
            all_odds = [
                float(r.get("odds", 0)) for r in runners if r.get("odds") != "SP"
            ]
            if all_odds and len(set(all_odds)) == 1 and all_odds[0] == 5.0:
                return False  # Placeholder race, do not alert

            if alert.condition_type == "odds_drop":
                percentage = float(val.strip("%")) / 100
                event_id = race_data.get("id")
                historical_odds = cache.get_historical_odds(event_id) if cache else {}
                baseline = historical_odds.get(horse.get("name"))

                if baseline and float(baseline) > 0:
                    return current_odds <= (float(baseline) * (1 - percentage))

                # No baseline yet — store current as baseline and skip alert this cycle
                if cache and event_id:
                    cache.update_baseline(
                        event_id, [{"name": horse.get("name"), "odds": current_odds}]
                    )
                return False

            elif alert.condition_type == "value_bet":
                threshold = float(val)
                return current_odds >= threshold

            elif alert.condition_type == "threshold":
                target = self._parse_odds(val)
                return current_odds <= target

            return False
        except Exception as e:
            logger.debug(f"Evaluation error: {e}")
            return False

    def _parse_odds(self, odds_str: str) -> float:
        """Parse fractional or decimal odds."""
        try:
            if "/" in odds_str:
                p = odds_str.split("/")
                return (float(p[0]) / float(p[1])) + 1
            return float(odds_str)
        except:
            return 1.0

    async def _trigger_alert(self, alert: AlertCondition, horse: Dict, race_data: Dict):
        """Trigger the signal with cooldown deduplication."""
        course = race_data.get("course", "Unknown")
        name = horse.get("name", "Unknown")
        key = f"{alert.id}_{course}_{name}"
        race_key = f"{course}"

        now = datetime.now()
        # Per-race cooldown to prevent alert bursts from same race
        last_race = self.last_race_alert_time.get(race_key)
        if last_race and (now - last_race) < timedelta(minutes=self.race_cooldown_minutes):
            self.stats["race_cooldown_prevents"] += 1
            return

        last = self.last_trigger_times.get(key)

        if last and (now - last) < timedelta(minutes=alert.cooldown_minutes):
            self.stats["cooldown_prevents"] += 1
            return

        self.last_trigger_times[key] = now
        self.last_race_alert_time[race_key] = now
        self.stats["alerts_triggered"] += 1
        
        # Track the odds at which we triggered this alert for change-threshold logic
        if alert.condition_type in ["odds_drop", "odds_rise", "threshold"]:
            current_odds_str = str(horse.get("odds", "1/1"))
            if current_odds_str.upper() != "SP":
                try:
                    current_odds = self._parse_odds(current_odds_str)
                    self.last_alerted_odds[key] = current_odds
                except (ValueError, ZeroDivisionError):
                    pass  # Keep existing value if parsing fails

        msg = {
            "alert_id": alert.id,
            "type": alert.condition_type,
            "course": course,
            "horse": name,
            "odds": horse.get("odds", "TBD"),
            "timestamp": now.isoformat(),
        }
        # Alert Digest v2 context (additive only — existing keys untouched).
        try:
            ctx = self._race_context(race_data)
            if ctx.get("race"):
                msg["race"] = ctx["race"]
            if ctx.get("off"):
                msg["off"] = ctx["off"]
            if ctx.get("mins_to_off") is not None:
                msg["mins_to_off"] = ctx["mins_to_off"]
            try:
                _cur = self._parse_odds(str(horse.get("odds", "")))
            except (ValueError, ZeroDivisionError):
                _cur = None
            journey = self._record_sighting(
                course, ctx.get("race", "?"), name, _cur)
            if journey:
                msg["journey"] = {
                    k: journey.get(k) for k in
                    ("open", "open_at", "latest", "latest_at")
                    if journey.get(k) is not None
                }
            self._save_journey()
            enrich = self._enrichment(horse if isinstance(horse, dict) else {})
            if enrich:
                msg["enrich"] = enrich
        except Exception:
            pass

        logger.info(
            f"🚨 ALERT! [{alert.condition_type}] {name} @ {course} is {msg['odds']}"
        )

        if self.notification_callback:
            await self.notification_callback(msg)
            self.stats["notifications_sent"] += 1

        # Autonomous betting: place bet if auto_bet_enabled and this is a value_bet alert
        if alert.condition_type == "value_bet":
            await self._maybe_auto_bet(alert, horse, race_data)

        await self._log_history(msg)

    async def _log_history(self, msg: Dict):
        """Write to rolling JSONL history log with size-based rotation."""
        try:
            MAX_HISTORY_SIZE = 5 * 1024 * 1024
            if os.path.exists(self.history_file):
                if os.path.getsize(self.history_file) >= MAX_HISTORY_SIZE:
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    rotated_file = f"{self.history_file}.{timestamp}"
                    os.rename(self.history_file, rotated_file)
                    logger.info(f"Rotated alert history to {rotated_file}")
            with open(self.history_file, "a") as f:
                f.write(json.dumps(msg) + "\n")
        except Exception as e:
            logger.error(f"Failed to log alert history: {e}")

    async def _maybe_auto_bet(self, alert: AlertCondition, horse: Dict, race_data: Dict):
        """Place an autonomous bet if auto_bet_enabled in settings."""
        try:
            import json as _json, os as _os
            settings_path = _os.path.join(self.data_dir, "settings.json")
            if not _os.path.exists(settings_path):
                return
            with open(settings_path) as f:
                settings = _json.load(f)
            if not settings.get("auto_bet_enabled", False):
                return
            min_edge = float(settings.get("auto_bet_min_edge", 5.5))

            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike:
                return

            odds = self._parse_odds(str(horse.get("odds", "1/1")))
            implied_prob = 1.0 / max(odds, 1.01)
            edge = round((1.0 - implied_prob) * 100 * 0.15, 1)
            if edge < min_edge:
                return

            track = race_data.get("course", "Unknown")
            race_number = int(race_data.get("raceNumber", race_data.get("race_number", 1)))
            horse_name = horse.get("name", "Unknown")

            bet = brain.strike.place_bet(
                track=track,
                race_number=race_number,
                horse=horse_name,
                odds=odds,
                edge_percent=edge,
                confidence="AUTO",
            )
            if bet:
                logger.info(f"[AUTO-BET] Placed: {horse_name} @ {track} R{race_number} odds={odds:.2f} edge={edge}%")
        except Exception as e:
            logger.warning(f"Auto-bet failed: {e}")

    def get_stats(self) -> Dict:
        return self.stats
