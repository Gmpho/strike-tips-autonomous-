"""System prompt builder for the new bus-based chat architecture."""

import json
import os
import logging
import re
from collections import Counter
from datetime import datetime
from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("agent-prompts")

# Retired provider names that still live in old ChromaDB learned insights.
# The model parrots them back as self-description ("I am powered by Groq's
# llama-3.3-70b-versatile") — Sep-2026: identity answers were months stale.
_RETIRED_MODEL_RE = re.compile(
    r"llama-?3\.?[13][-\w.]*|deepseek[-\w.]*|kimi[-\w.]*|mixtral[-\w.]*",
    re.IGNORECASE,
)
_SANITIZE_MAP = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.3-70b": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
    "llama-3.1-70b": "openai/gpt-oss-120b",
    "deepseek-r1-distill": "openai/gpt-oss-120b",
}


def sanitize_model_text(text: str) -> str:
    """Rewrite retired model names in memory-derived text to the live pool."""
    if not text:
        return text
    out = str(text)
    for dead, live in _SANITIZE_MAP.items():
        out = re.sub(re.escape(dead), live, out, flags=re.IGNORECASE)
    # Anything else that still looks like a retired family: name the pool.
    out = _RETIRED_MODEL_RE.sub("openai/gpt-oss-120b", out)
    return out


def _identity_block() -> str:
    """Self-description from the live ModelConfig pool (never stale memory)."""
    try:
        from core_agent.config.model_config import ModelConfig as _MC

        primary = _MC.ORCHESTRATOR
        fast = getattr(_MC, "GROQ_FAST", "openai/gpt-oss-20b")
        fallback = getattr(_MC, "CLOUD_FALLBACK", "gemini-2.5-flash")
    except Exception:
        primary, fast, fallback = "openai/gpt-oss-120b", "openai/gpt-oss-20b", "gemini-2.5-flash"
    return (
        "Identity (authoritative — overrides any older memory note):\n"
        f"- If asked which model/LLM powers you, answer: primary {primary} on Groq, "
        f"fast tier {fast}, fallback {fallback} on Google Gemini.\n"
        "- Never claim a retired model (llama-3.3, llama-3.1, deepseek, kimi) — "
        "older stored notes mentioning them are outdated.\n"
    )


def build_system_prompt(for_cloud: bool = False, user_message: str = "") -> str:
    today = datetime.now().strftime("%A, %d %B %Y")
    # Card-intent gate: live race context only rides along when the turn is
    # about racing data. Casual/identity turns keep the prompt small so the
    # model stops parroting the meeting list mid-conversation (Sep-2026).
    try:
        from core_agent.agent.context import wants_live_card as _wants

        include_races = _wants(user_message) if user_message else True
    except Exception:
        include_races = True
    race_info = _build_race_context() if include_races else (
        "Live race card withheld for this conversational turn — call a tool "
        "or ask about a track if race data is needed."
    )
    learned_info = _build_learned_context()
    identity = _identity_block()
    
    tools_str = (
        "Available tools (call the RIGHT tool for the job):\n"
        "- evaluate_race: Deep analysis of a specific race for value bets.\n"
        "- run_daily_analysis: Run a full daily scan across all tracks for value selections.\n"
        "- get_odds_snapshot: Return the latest odds snapshot for one or all tracks.\n"
        "- get_atr_market_movers: Return ATR market movers - horses with significant odds movement.\n"
        "- get_atr_predictor: Return ATR AI predictions for upcoming races.\n"
        "- get_atr_results: Return ATR race results.\n"
        "- get_account_summary: Return current bankroll balance, peak, P&L, open bets.\n"
        "- record_selection: Record a new bet selection through the bankroll governor.\n"
        "- update_race_result: Settle an open selection with a WON or LOST result.\n"
        "- calculate_probability_edge: Calculate edge from decimal odds and estimated probability.\n"
        "- calculate_max_position: Calculate maximum allowed stake using Half-Kelly criterion.\n"
        "- search_past_races: Semantic search over historical race data and form insights.\n"
        "- search_racing_data: Search for racing information via DuckDuckGo web search.\n"
        "- search_racing_keywords: Keyword search over indexed race data using BM25.\n"
        "- search_hybrid: Hybrid search combining BM25 keyword search + semantic vector search.\n"
        "- verify_race_exists: Verify if a specific race is scheduled at a track today.\n"
        "- get_dream_context: Return recent AI dreams/insights generated from live race data.\n"
        "- simulate_race_scenarios: Force on-demand scenario simulation (wind, going, scratch).\n"
        "- query_racing_dreams: Query ChromaDB for background scenario simulations.\n"
        "- save_learned_insight: Save a learned analysis pattern after a multi-step tool chain.\n\n"
    )

    if for_cloud:
        base = (
            f"You are Strike Tips Racing AI. Answer concisely and accurately.\n\n"
            f"Today is {today}. {race_info}\n\n"
            f"{identity}\n"
            f"{tools_str}"
            f"{learned_info}"
            "Rules:\n"
            "1. ALWAYS call a tool when you need live data — never guess odds, horses or results.\n"
            "2. Report tool results directly — do not fabricate numbers.\n"
            "3. If a tool returns an error, try a different tool or apologize briefly.\n"
            "4. Never invent statistics, horse names, odds, or betting history.\n"
            "5. If live snapshot data is provided above, use it — no tool call needed for that.\n"
            "6. Match the user's mode: casual message → brief casual reply (no card dump). "
            "Pasted race card or racing question → full analysis. Never volunteer race "
            "meetings or odds the user did not ask about."
        )
    else:
        base = (
            f"You are Strike Tips Racing AI. Answer concisely and accurately.\n\n"
            f"Today is {today}. {race_info}\n\n"
            f"{identity}\n"
            f"{tools_str}"
            f"{learned_info}"
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
            "5. If live snapshot data is provided above, use it — no tool call needed for that.\n"
            "6. Match the user's mode: casual message → brief casual reply (no card dump). "
            "Pasted race card or racing question → full analysis. Never volunteer race "
            "meetings or odds the user did not ask about."
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


def _build_learned_context() -> str:
    """Query ChromaDB for saved learned_insight entries and format as prompt context.
    Returns empty string if memory unavailable or no insights found.

    Descriptions are sanitized: stored insights predate the Sep-2026 model
    migration and still name retired providers (llama-3.3, deepseek, kimi).
    Fed raw, the model repeats them as its own identity.
    """
    try:
        from core_agent.core.strike_brain import brain
        if brain and brain.memory and brain.memory._is_ready:
            results = brain.memory.search_form_insights(
                query="learned insight analysis feature",
                n_results=12,
                where={"type": "learned_insight"},
            )
            if not results:
                return ""
            lines = ["=== LEARNED PATTERNS FROM PAST ANALYSIS ==="]
            seen = set()
            for r in results:
                meta = r.get("metadata", {})
                name = meta.get("pattern_name", "")
                if name and name not in seen:
                    seen.add(name)
                    content = r.get("content", "")
                    desc = ""
                    for line in content.split("\n"):
                        if line.startswith("Description:"):
                            desc = line[len("Description:"):].strip()
                            break
                    lines.append(f"  • {name}: {sanitize_model_text(desc)[:150]}")
            lines.append("")
            return "\n".join(lines)
        return ""
    except Exception as e:
        logger.debug(f"Could not load learned context: {e}")
        return ""
