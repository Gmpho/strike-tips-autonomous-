"""
Context builder — injects today's date and live snapshot data into LLM prompts.
Single responsibility: build the system context string.
"""

import json
import logging
from collections import Counter
from datetime import datetime
from typing import Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("context-builder")


def build_race_context() -> str:
    """Return a concise context string with today's date and live race data."""
    today = datetime.now().strftime("%A, %d %B %Y")

    try:
        with open(MARKET_SNAPSHOT_PATH) as f:
            snap = json.load(f)

        regions: Counter = Counter()
        courses: set = set()
        for event in snap.get("events", {}).values():
            region = event.get("en", "").split(":")[0].strip()
            regions[region] += 1
            courses.add(event.get("course", "").strip())

        race_info = (
            f"Live races today: {snap.get('count', 0)} total. "
            f"Regions: {dict(regions)}. "
            f"Courses: {', '.join(sorted(courses)[:20])}."
        )
    except Exception as e:
        logger.debug(f"Could not load snapshot: {e}")
        race_info = "Live race data unavailable."

    return f"Today is {today}. {race_info}"


def build_system_prompt(base: Optional[str] = None) -> str:
    """Full system prompt for any provider."""
    base = base or "You are Strike Tips Racing AI. Answer concisely and accurately."
    context = build_race_context()
    sa_schedule = (
        "Active South Africa racing tracks: Turffontein (Johannesburg), "
        "Kenilworth/Durbanville (Cape Town), Vaal (Vereeniging), "
        "Greyville/Scottsville (Durban/KZN), Fairview (Port Elizabeth). "
        "Always verify with search_racing_data for the actual schedule."
    )
    return (
        f"{base} {context} {sa_schedule} "
        "Use search_racing_data ONCE for tomorrow's races, future fixtures, or recent results. "
        "After receiving search results, give a direct answer — never call tools in your final response."
    )
