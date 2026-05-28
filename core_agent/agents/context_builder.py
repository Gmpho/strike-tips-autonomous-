"""
Context builder — injects today's date and live snapshot data into LLM prompts.
Single responsibility: build the system context string.
"""

import json
import logging
import os
from collections import Counter
from datetime import datetime
from typing import Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("context-builder")


def build_race_context() -> str:
    """Return a concise context string with today's date and live race data."""
    today = datetime.now().strftime("%A, %d %B %Y")

    try:
        from core_agent.core.snapshot_cache import get_snapshot
        snap = get_snapshot()

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

    return f"Today is {today}. {race_info} Use get_odds_snapshot to see runners and live odds."


def build_system_prompt(base: Optional[str] = None, intent: Optional[str] = None) -> str:
    """Full system prompt for any provider, trimmed based on intent."""
    base = base or "You are Strike Tips Racing AI. Answer concisely and accurately."
    
    # 🕵️ Intent-Aware Trimming
    # Skip heavy context for simple balance/utility queries
    is_bankroll = intent in ("get_account_summary", "calculate_max_position", "update_race_result")
    is_search = intent in ("search_racing_data", "search_past_races")

    if is_bankroll:
        context = f"Today is {datetime.now().strftime('%A, %d %B %Y')}."
        sa_schedule = ""
        heartbeat = ""
    else:
        context = build_race_context()
        sa_schedule = (
            "\nActive South Africa racing tracks: Turffontein, Kenilworth/Durbanville, "
            "Vaal, Greyville/Scottsville, Fairview."
        )
        
        # Inject heartbeat memory only for analysis/strategy tasks
        heartbeat = ""
        if not is_search:
            try:
                heartbeat_path = os.path.join("data", "heartbeat.md")
                if os.path.exists(heartbeat_path):
                    with open(heartbeat_path) as f:
                        content = f.read()
                    entries = [e.strip() for e in content.split("##") if e.strip() and not e.startswith("#")]
                    if entries:
                        heartbeat = "\n\nRecent AI insights (heartbeat memory):\n" + "\n".join(
                            f"- {e.splitlines()[2].replace('**Insight:** ', '') if len(e.splitlines()) > 2 else ''}"
                            for e in entries[:2]  # Reduced from 3 to 2 for even more speed
                        )
            except Exception:
                pass

    return (
        f"{base} {context} {sa_schedule}{heartbeat} "
        "Use search_racing_data ONCE if needed for tomorrow's races or results. "
        "Return direct answers — no trailing tool calls. "
        "CRITICAL: Never invent or guess statistics, betting history, horse names, win rates, "
        "or any data you cannot confirm from tool results or the system state provided above. "
        "If you lack the data to answer, say 'I don't have that information' — do not fabricate. "
        "For betting history, win rate, or performance stats: only report numbers from get_account_summary "
        "or get_odds_snapshot tool results. Never make up historical bet counts or win percentages."
    )
