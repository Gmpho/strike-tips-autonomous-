import asyncio
import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

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

    def __init__(self, notification_callback=None, data_dir="/app/data"):
        self.notification_callback = notification_callback
        self.data_dir = data_dir
        self.alerts_file = os.path.join(data_dir, "alert_conditions.json")
        self.history_file = os.path.join(data_dir, "alert_history.json")

        self.alerts_cache: Dict[str, AlertCondition] = {}
        self.last_trigger_times: Dict[str, datetime] = {}

        self.stats = {
            "total_evaluations": 0,
            "alerts_triggered": 0,
            "notifications_sent": 0,
            "cooldown_prevents": 0,
        }

    async def initialize(self):
        """Initialize the engine and load settings."""
        os.makedirs(self.data_dir, exist_ok=True)
        await self._load_alerts()
        logger.info(
            f"🚀 Alert Engine Active: Loaded {len(self.alerts_cache)} conditions."
        )

    async def _load_alerts(self):
        """Load alerts from local JSON storage."""
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, "r") as f:
                    data = json.load(f)
                    for item in data:
                        alert = AlertCondition(**item)
                        self.alerts_cache[alert.id] = alert
            except Exception as e:
                logger.error(f"Failed to load alerts: {e}")

        # Default alerts if none exist
        if not self.alerts_cache:
            self._add_default_alerts()
            await self._save_alerts()

    def _add_default_alerts(self):
        """Standard L7 baseline alerts."""
        defaults = [
            AlertCondition(
                id="global_odds_drop",
                race_course="Any",
                horse_name=None,
                condition_type="odds_drop",
                condition_value="15%",
                notification_channels=["telegram", "websocket"],
            ),
            AlertCondition(
                id="global_value_bet",
                race_course="Any",
                horse_name=None,
                condition_type="value_bet",
                condition_value="5.0",  # Odds > 5.0
                notification_channels=["telegram"],
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

                if await self._evaluate_condition(alert, horse, race_data, cache):
                    await self._trigger_alert(alert, horse, race_data)

    async def _evaluate_condition(
        self, alert: AlertCondition, horse: Dict, race_data: Dict, cache=None
    ) -> bool:
        """Core math evaluation logic."""
        try:
            current_odds_str = str(horse.get("odds", "1/1"))
            # Skip SP — no real price yet
            if current_odds_str.upper() == "SP":
                return False
            current_odds = self._parse_odds(current_odds_str)
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

        now = datetime.now()
        last = self.last_trigger_times.get(key)

        if last and (now - last) < timedelta(minutes=alert.cooldown_minutes):
            self.stats["cooldown_prevents"] += 1
            return

        self.last_trigger_times[key] = now
        self.stats["alerts_triggered"] += 1

        msg = {
            "alert_id": alert.id,
            "type": alert.condition_type,
            "course": course,
            "horse": name,
            "odds": horse.get("odds", "TBD"),
            "timestamp": now.isoformat(),
        }

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
        """Write to rolling JSONL history log."""
        try:
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
            min_edge = float(settings.get("auto_bet_min_edge", 8.0))

            from core_agent.core.strike_brain import brain
            if not brain or not brain.strike or not brain.strike.bankroll:
                return

            odds = self._parse_odds(str(horse.get("odds", "1/1")))
            # Edge = (1/implied_prob - 1) * 100 as a rough estimate
            implied_prob = 1.0 / max(odds, 1.01)
            edge = round((1.0 - implied_prob) * 100 * 0.15, 1)  # conservative 15% of margin
            if edge < min_edge:
                return

            track = race_data.get("course", "Unknown")
            race_number = int(race_data.get("raceNumber", race_data.get("race_number", 1)))
            horse_name = horse.get("name", "Unknown")

            bet = brain.strike.bankroll.record_bet(
                track=track,
                race_number=race_number,
                horse=horse_name,
                odds=odds,
                stake=brain.strike.bankroll.calculate_max_stake(edge),
                edge_percent=edge,
                confidence="AUTO",
            )
            if bet:
                bet.notes = (bet.notes + " AUTO").strip() if bet.notes else "AUTO"
                brain.strike.bankroll._save_state()
                logger.info(f"[AUTO-BET] Placed: {horse_name} @ {track} R{race_number} odds={odds:.2f} edge={edge}%")
        except Exception as e:
            logger.warning(f"Auto-bet failed: {e}")

    def get_stats(self) -> Dict:
        return self.stats
