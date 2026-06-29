"""System prompt builder for the new bus-based chat architecture."""

import json
import os
import logging
from collections import Counter
from datetime import datetime
from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("agent-prompts")


def build_system_prompt(for_cloud: bool = False) -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    race_info = _build_race_context()
    
    if for_cloud:
        base = (
            f"You are Strike Tips Racing AI. Answer concisely and accurately.\n\n"
            f"Today is {today}. {race_info}\n\n"
            "Available tools (call the RIGHT tool for the job):\n"
            "- get_odds_snapshot: Current runners, jockeys, trainers, weights, odds (by track name)\n"
            "- get_atr_market_movers: Horses with significant odds movements today\n"
            "- get_atr_predictor: ATR AI predictor tips for today's races\n"
            "- get_atr_results: Recent race results from ATR\n"
            "- evaluate_race: Deep analysis of a specific race for value bets\n"
            "- search_racing_data: Web search for racing news and info\n"
            "- get_account_summary: User's bankroll, P&L, open bets\n"
            "- calculate_probability_edge: Given decimal odds and estimated win %, compute edge\n"
            "- calculate_max_position: Half-Kelly max stake for an edge\n"
            "- verify_race_exists: Check if a race is on today\n\n"
            "Rules:\n"
            "1. ALWAYS call a tool when you need live data — never guess odds, horses or results.\n"
            "2. Report tool results directly — do not fabricate numbers.\n"
            "3. If a tool returns an error, try a different tool or apologize briefly.\n"
            "4. Never invent statistics, horse names, odds, or betting history.\n"
            "5. If live snapshot data is provided above, use it — no tool call needed for that."
        )
    else:
        base = (
            f"You are Strike Tips Racing AI. Answer concisely and accurately.\n\n"
            f"Today is {today}. {race_info}\n\n"
            "Available tools (call the RIGHT tool for the job):\n"
            "- get_odds_snapshot: Current runners, jockeys, trainers, weights, odds (by track name)\n"
            "- get_atr_market_movers: Horses with significant odds movements today\n"
            "- get_atr_predictor: ATR AI predictor tips for today's races\n"
            "- get_atr_results: Recent race results from ATR\n"
            "- evaluate_race: Deep analysis of a specific race for value bets\n"
            "- search_racing_data: Web search for racing news and info\n"
            "- get_account_summary: User's bankroll, P&L, open bets\n"
            "- calculate_probability_edge: Given decimal odds and estimated win %, compute edge\n"
            "- calculate_max_position: Half-Kelly max stake for an edge\n"
            "- verify_race_exists: Check if a race is on today\n\n"
            "HOW TO USE TOOLS:\n"
            "When you need live data, output EXACTLY this on its own line (nothing else on that line):\n"
            "  TOOL: tool_name({\"arg\": \"value\"})\n"
            "Examples:\n"
            "  TOOL: get_odds_snapshot({\"track\": \"greyville\"})\n"
            "  TOOL: get_account_summary({})\n"
            "  TOOL: get_atr_market_movers({})\n"
            "The system will execute the tool and return results to you.\n\n"
            "Rules:\n"
            "1. ALWAYS call a tool when you need live data — never guess odds, horses or results.\n"
            "2. Report tool results directly — do not fabricate numbers.\n"
            "3. If a tool returns an error, try a different tool or apologize briefly.\n"
            "4. Never invent statistics, horse names, odds, or betting history.\n"
            "5. If live snapshot data is provided above, use it — no tool call needed for that."
        )
    return base


def _build_race_context() -> str:
    try:
        from core_agent.core.snapshot_cache import get_snapshot
        snap = get_snapshot()
        events = snap.get("events", {})
        total = snap.get("count", 0)

        regions: Counter = Counter()
        for event in events.values():
            region = event.get("en", "").split(":")[0].strip()
            regions[region] += 1

        track_summaries = []
        seen_courses = set()
        for eid, event in events.items():
            course = event.get("course", "").strip()
            if course and course not in seen_courses and len(track_summaries) < 4:
                seen_courses.add(course)
                runners = event.get("runners", [])
                horse_list = []
                for r in runners[:5]:
                    j = r.get("jockeyName", "?")
                    t = r.get("trainerName", "?")
                    w = r.get("weight", "?")
                    horse_list.append(f"{r.get('name')} (J:{j}, T:{t}, W:{w})")
                track_summaries.append(
                    f"{event.get('name')} — {len(runners)} runners:\n"
                    + "\n".join(f"  {h}" for h in horse_list)
                )

        parts = [
            f"Live races today: {total} total in {len(events)} events.",
            f"Regions: {dict(regions)}.",
        ]
        if track_summaries:
            parts.append("Key tracks with runners (jockey, trainer, weight):\n" + "\n\n".join(track_summaries))
        return " ".join(parts)
    except Exception as e:
        logger.debug(f"Could not load snapshot: {e}")
        return "Live race data unavailable."
