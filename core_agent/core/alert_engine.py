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
            "cooldown_prevents": 0
        }

    async def initialize(self):
        """Initialize the engine and load settings."""
        os.makedirs(self.data_dir, exist_ok=True)
        await self._load_alerts()
        logger.info(f"🚀 Alert Engine Active: Loaded {len(self.alerts_cache)} conditions.")

    async def _load_alerts(self):
        """Load alerts from local JSON storage."""
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, 'r') as f:
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
                notification_channels=["telegram", "websocket"]
            ),
            AlertCondition(
                id="global_value_bet",
                race_course="Any",
                horse_name=None,
                condition_type="value_bet",
                condition_value="5.0", # Odds > 5.0
                notification_channels=["telegram"]
            )
        ]
        for a in defaults:
            self.alerts_cache[a.id] = a

    async def _save_alerts(self):
        """Persist alert settings."""
        with open(self.alerts_file, 'w') as f:
            json.dump([asdict(a) for a in self.alerts_cache.values()], f, indent=4)

    async def evaluate_odds_update(self, race_data: Dict[str, Any]):
        """Evaluate a fresh race update against all conditions."""
        self.stats["total_evaluations"] += 1
        
        course = race_data.get("course", "Unknown")
        horses = race_data.get("runners", []) or race_data.get("horses", [])

        for alert in self.alerts_cache.values():
            if not alert.active:
                continue

            if alert.race_course != "Any" and alert.race_course.lower() != course.lower():
                continue

            for horse in horses:
                name = horse.get("name", "Unknown")
                
                if alert.horse_name and alert.horse_name.lower() != name.lower():
                    continue

                if await self._evaluate_condition(alert, horse, race_data):
                    await self._trigger_alert(alert, horse, race_data)

    async def _evaluate_condition(self, alert: AlertCondition, horse: Dict, race_data: Dict) -> bool:
        """Core math evaluation logic."""
        try:
            current_odds_str = str(horse.get("odds", "1/1"))
            current_odds = self._parse_odds(current_odds_str)
            val = alert.condition_value

            if alert.condition_type == "odds_drop":
                percentage = float(val.strip('%')) / 100
                # Comparative logic (requires history, defaulting to True for initial detection)
                # In full L7 we compare against MARKET_SNAPSHOT_LATEST
                return True # Placeholder for now, will link to market_watcher 

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
            "timestamp": now.isoformat()
        }

        logger.info(f"🚨 ALERT! [{alert.condition_type}] {name} @ {course} is {msg['odds']}")
        
        if self.notification_callback:
            await self.notification_callback(msg)
            self.stats["notifications_sent"] += 1
            
        await self._log_history(msg)

    async def _log_history(self, msg: Dict):
        """Write to rolling history log."""
        try:
            with open(self.history_file, 'a') as f:
                f.write(json.dumps(msg) + "\n")
        except:
            pass

    def get_stats(self) -> Dict:
        return self.stats
