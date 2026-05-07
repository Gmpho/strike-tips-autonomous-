import random
import psutil
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

# Integrated with current settings
from core_agent.config.settings import SETTINGS

logger = logging.getLogger("APIHelpers")


def calculate_confidence_from_odds(odds_str: str) -> int:
    """
    Calculate confidence score from betting odds.
    Ported from User's Gold Standard Project.
    """
    try:
        if isinstance(odds_str, (int, float)):
            decimal_odds = float(odds_str)
        elif "/" in str(odds_str):
            numerator, denominator = odds_str.split("/")
            decimal_odds = float(numerator) / float(denominator) + 1
        else:
            decimal_odds = float(odds_str)

        # Convert to implied probability (confidence)
        implied_prob = (1 / decimal_odds) * 100
        # Add realistic variance (±5%)
        confidence = min(95, max(5, implied_prob + random.uniform(-5, 5)))
        return round(confidence)
    except:
        return 50  # Default baseline


def race_dict_to_response(race_dict: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Enrich raw race data for frontend consumption.
    """
    course = race_dict.get("course", "Unknown")
    # Generate stable ID
    race_dict["id"] = f"race-{index+1}-{course.replace(' ', '-').lower()}"
    race_dict["raceNumber"] = str(race_dict.get("raceNumber", index + 1))

    # Add default prize if missing
    if not race_dict.get("prize"):
        race_dict["prize"] = "R100,000"  # SA baseline

    # Map track conditions
    race_dict["trackCondition"] = race_dict.get(
        "conditions", race_dict.get("trackCondition", "Good")
    )

    # Enrich runners with confidence scores
    for horse in race_dict.get("runners", []):
        if "confidence" not in horse:
            horse["confidence"] = calculate_confidence_from_odds(horse.get("odds", 5.0))

    return race_dict


def check_system_resources() -> Dict[str, Any]:
    """
    Diagnostic health check for the L7 Intelligence process.
    """
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=None)  # Non-blocking

        return {
            "memory_usage_percent": memory.percent,
            "cpu_usage_percent": cpu_percent,
            "available_memory_mb": memory.available // (1024 * 1024),
            "status": (
                "HEALTHY" if memory.percent < 85 and cpu_percent < 90 else "DEGRADED"
            ),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        return {"status": "ERROR", "error": str(e)}


def calculate_uptime(start_time: Optional[datetime]) -> float:
    if not start_time:
        return 0.0
    return (datetime.now() - start_time).total_seconds()
