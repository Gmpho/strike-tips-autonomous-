"""System prompt builder for the new bus-based chat architecture."""

import json
import os
import logging
from collections import Counter
from datetime import datetime
from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("agent-prompts")


def build_system_prompt() -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    race_info = _build_race_context()
    base = (
        f"You are Strike Tips Racing AI. Answer concisely and accurately.\n\n"
        f"Today is {today}. {race_info}\n\n"
        "Use get_odds_snapshot to see runners and live odds. "
        "Return direct answers — no trailing tool calls. "
        "CRITICAL: Never invent or guess statistics, betting history, horse names, win rates, "
        "or any data you cannot confirm from tool results or the system state provided above. "
        "If you lack the data to answer, say 'I don't have that information' — do not fabricate. "
        "For betting history, win rate, or performance stats: only report numbers from "
        "get_account_summary or get_odds_snapshot tool results. "
        "Never make up historical bet counts or win percentages."
    )
    return base


def _build_race_context() -> str:
    try:
        from core_agent.core.snapshot_cache import get_snapshot
        snap = get_snapshot()
        regions: Counter = Counter()
        courses: set = set()
        for event in snap.get("events", {}).values():
            region = event.get("en", "").split(":")[0].strip()
            regions[region] += 1
            courses.add(event.get("course", "").strip())
        return (
            f"Live races today: {snap.get('count', 0)} total. "
            f"Regions: {dict(regions)}. "
            f"Courses: {', '.join(sorted(courses)[:20])}."
        )
    except Exception as e:
        logger.debug(f"Could not load snapshot: {e}")
        return "Live race data unavailable."
