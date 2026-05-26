"""
MAF Tool Registry - 11 Gambling-Free Tools for Strike Bot
Each tool is a plain Python function callable by the agent pipeline.
Tool names follow the func_gemma-compatible naming convention.
"""

import asyncio
import logging
import re
from dataclasses import asdict
from datetime import date
from typing import Any, Callable, Dict, List, Optional

from core_agent.core.redis_cache import get_cache, set_cache

logger = logging.getLogger("maf-tool-registry")

KNOWN_SAFE_DOMAINS = {
    "sportingpost.co.za", "tabonline.co.za",
    "sport24.co.za", "sabra.co.za", "sahracing.com",
    "sportinglife.com", "goldcircle.co.za",
    "bloodhorse.com", "thoroughbredracing.com",
    "sportingnews.com", "espn.com", "espn.co.uk",
}

SUSPICIOUS_PATTERNS = re.compile(
    r"(https?://\d+\.\d+\.\d+\.\d+)"  # IP-based URLs
    r"|(\.(?:gq|ml|cf|ga|tk|xyz|top|download|review|bid|date|racing|bet|click|loan|men|stream|trade|webcam|work|site|win|party|racing))/",  # suspicious TLDs
    re.I,
)


def _is_url_safe(url: str) -> bool:
    if SUSPICIOUS_PATTERNS.search(url):
        return False
    from urllib.parse import urlparse
    parsed = urlparse(url)
    domain = parsed.hostname or ""
    return any(domain.endswith(f".{safe}") or domain == safe for safe in KNOWN_SAFE_DOMAINS)

# ─── Tool Metadata ─────────────────────────────────────────────────────────────

TOOL_INFO: Dict[str, Dict] = {
    "evaluate_race": {
        "description": "Evaluate a specific race for value opportunities using probability edge analysis.",
        "specialist": "lfm_racing",
        "category": "analysis",
        "speed": "~3-5s",
        "use_case": "Analyse Race 3 at Turffontein for value",
    },
    "run_daily_analysis": {
        "description": "Run a full daily scan across all tracks and return value selections.",
        "specialist": "lfm_racing",
        "category": "analysis",
        "speed": "~30-60s",
        "use_case": "Run today's full scan",
    },
    "calculate_probability_edge": {
        "description": "Calculate the betting edge given decimal odds and estimated probability.",
        "specialist": "racing_qwen",
        "category": "calculation",
        "speed": "~1s",
        "use_case": "What is the edge on Horse X at 6.5 odds if I estimate 25%?",
    },
    "calculate_max_position": {
        "description": "Calculate maximum allowed stake for a given edge using Half-Kelly criterion.",
        "specialist": "racing_qwen",
        "category": "calculation",
        "speed": "~1s",
        "use_case": "What is my max stake for a 12% edge?",
    },
    "get_account_summary": {
        "description": "Return current bankroll balance, peak, P&L, open bets, and performance stats.",
        "specialist": "racing_qwen",
        "category": "account",
        "speed": "~1s",
        "use_case": "What is my current balance and performance?",
    },
    "record_selection": {
        "description": "Record a new bet selection through the bankroll governor with all discipline checks.",
        "specialist": "func_gemma",
        "category": "write",
        "speed": "~1-2s",
        "use_case": "Record a R50 bet on Storm Chaser at Turffontein Race 3",
    },
    "update_race_result": {
        "description": "Settle an open selection with a WON or LOST result and update the bankroll.",
        "specialist": "func_gemma",
        "category": "write",
        "speed": "~1-2s",
        "use_case": "Settle bet ABC123 as WON",
    },
    "search_past_races": {
        "description": "Semantic search over historical race data and form insights in ChromaDB memory.",
        "specialist": "racing_qwen",
        "category": "search",
        "speed": "~2-3s",
        "use_case": "Show me past results at Turffontein over 1600m",
    },
    "search_racing_data": {
        "description": "Search for racing information via DuckDuckGo web search.",
        "specialist": "racing_llama",
        "category": "data",
        "speed": "~3-5s",
        "use_case": "Find today's Greyville race results",
    },
    "verify_race_exists": {
        "description": "Verify if a specific race is scheduled at a track for today.",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~2-3s",
        "use_case": "Is Race 5 at Vaal happening today?",
    },
    "get_odds_snapshot": {
        "description": "Return the latest odds snapshot for one or all tracks.",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "What are the current odds at Kenilworth?",
    },
}


# ─── Tool Implementations ─────────────────────────────────────────────────────


def get_account_summary(strike=None, **kwargs) -> Dict:
    """Return bankroll status and performance summary."""
    if not strike:
        return {"error": "StrikeTips not initialized"}
    try:
        status = strike.get_bankroll_status()
        return {
            "current_balance": status.get("current_bankroll", 0),
            "peak_balance": status.get("peak_bankroll", 0),
            "total_profit_loss": status.get("total_profit_loss", 0),
            "drawdown_percent": status.get("drawdown_percent", 0),
            "open_bets": status.get("open_bets", 0),
            "performance": status.get("performance", {}),
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_probability_edge(
    odds_decimal: float, estimated_probability: float, **kwargs
) -> Dict:
    """Calculate edge = (estimated_prob - implied_prob) × 100."""
    try:
        implied = 1.0 / max(odds_decimal, 1.01)
        edge = (estimated_probability - implied) * 100.0
        return {
            "implied_probability": round(implied, 4),
            "estimated_probability": round(estimated_probability, 4),
            "edge_percent": round(edge, 2),
            "has_value": edge >= 5.0,
            "confidence": (
                "STRONG_VALUE"
                if edge >= 15
                else "VALUE" if edge >= 8 else "MARGINAL" if edge >= 5 else "NO_VALUE"
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def calculate_max_position(edge_percent: float, strike=None, **kwargs) -> Dict:
    """Calculate max stake using Half-Kelly, capped at 5% of bankroll."""
    if not strike:
        return {"error": "StrikeTips not initialized"}
    try:
        max_stake = strike.bankroll.calculate_max_stake(edge_percent)
        return {
            "max_position_allowed": max_stake,
            "current_balance": strike.bankroll.current_bankroll,
            "edge_percent": edge_percent,
            "percent_of_bankroll": round(
                max_stake / max(strike.bankroll.current_bankroll, 1) * 100, 2
            ),
        }
    except Exception as e:
        return {"error": str(e)}


def record_selection(
    track: str,
    race_number: int,
    horse: str,
    odds: float,
    position_size: float,
    edge_percent: float,
    confidence: str,
    strike=None,
    **kwargs,
) -> Dict:
    """Record a selection through the bankroll governor."""
    if not strike:
        return {"status": "ERROR", "reason": "StrikeTips not initialized"}

    from core_agent.core.strike_brain import brain

    if hasattr(brain, "emergency_stop") and brain.emergency_stop:
        return {
            "status": "REJECTED",
            "reason": "SAFETY REJECTED: System Lock Active (Kill Switch Triggered)",
        }

    try:
        bet = strike.bankroll.record_bet(
            track=track,
            race_number=race_number,
            horse=horse,
            odds=odds,
            stake=position_size,
            edge_percent=edge_percent,
            confidence=confidence,
        )
        if bet:
            return {"status": "RECORDED", "bet_id": bet.bet_id, "stake": bet.stake}
        return {
            "status": "REJECTED",
            "reason": "Governor limits exceeded or insufficient edge",
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}


def update_race_result(
    selection_id: str, result: str, notes: str = "", strike=None, **kwargs
) -> Dict:
    """Settle a selection as WON or LOST."""
    if not strike:
        return {"status": "ERROR", "reason": "StrikeTips not initialized"}
    try:
        won = result.upper() in ("WON", "WIN", "W")
        success = strike.bankroll.settle_bet(selection_id, won=won, notes=notes)
        if success:
            return {
                "status": "SETTLED",
                "selection_id": selection_id,
                "result": "WON" if won else "LOST",
                "new_balance": strike.bankroll.current_bankroll,
            }
        return {
            "status": "ERROR",
            "reason": f"Selection {selection_id} not found or already settled",
        }
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}


def search_past_races(query: str, n_results: int = 5, strike=None, **kwargs) -> Dict:
    """Semantic search over stored race insights."""
    if not strike or not hasattr(strike, "memory"):
        return {"query": query, "results": [], "note": "Memory not available"}
    try:
        results = strike.memory.search_form_insights(query, n_results=n_results)
        return {
            "query": query,
            "results": [r.get("content", "") for r in results],
            "count": len(results),
        }
    except Exception as e:
        return {"query": query, "error": str(e)}


async def search_racing_data(query: str, limit: int = 3, **kwargs) -> Dict:
    """Search for racing information via unified SearchService (Brave → Tavily → DDGS)."""
    from core_agent.skills.search_service import search_racing
    from datetime import datetime

    cache_key = f"maf_search:{query}:{limit}"
    cached = await get_cache(cache_key)
    if cached is not None:
        logger.info(f"[MAF] Cache hit: {query}")
        return cached

    current_year = datetime.now().year
    queries = [
        f"{query} {current_year}",
        f"horse racing {query} {current_year}",
    ]

    try:
        all_results = []
        seen_urls = set()
        for q in queries:
            result = await search_racing(q, limit=limit)
            for item in result.get("results", []):
                url = item.get("url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(item)
            if result.get("provider") != "none":
                break

        final = {
            "query": query,
            "results": all_results[:limit * 2],
            "count": len(all_results),
            "status": "success" if all_results else "no_data_found",
        }
        await set_cache(cache_key, final)
        return final
    except Exception as e:
        return {"query": query, "error": str(e), "results": [], "status": "error"}


async def verify_race_exists(track: str, race_number: int, strike=None, **kwargs) -> Dict:
    """Check if a race is scheduled for today at a given track."""
    if not strike:
        return {"exists": False, "reason": "StrikeTips not initialized"}
    try:
        exists = await strike.verify_race_event(track, race_number)
        return {
            "track": track,
            "race_number": race_number,
            "exists": exists,
            "date": date.today().isoformat(),
        }
    except Exception as e:
        return {"exists": False, "error": str(e)}


async def get_odds_snapshot(track: Optional[str] = None, strike=None, **kwargs) -> Dict:
    """Return the latest odds snapshot for a track or all tracks."""
    if not strike:
        return {"status": "no_snapshot_available"}
    try:
        return await strike.get_odds_snapshot(track=track)
    except Exception as e:
        return {"status": "error", "error": str(e)}


async def evaluate_race(
    track: str, race_number: int = 1, strike=None, **kwargs
) -> Dict:
    """Evaluate a specific race for value opportunities."""
    if not strike:
        return {"status": "ERROR", "reason": "StrikeTips not initialized"}
    try:
        return await strike.evaluate_race(track, race_number)
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}


async def run_daily_analysis(
    tracks: Optional[List[str]] = None, strike=None, **kwargs
) -> Dict:
    """Run the full daily analysis scan across all tracks."""
    if not strike:
        return {"status": "ERROR", "reason": "StrikeTips not initialized"}
    try:
        return await strike.run_daily_scan(tracks=tracks)
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}


# ─── Registry ─────────────────────────────────────────────────────────────────

TOOL_REGISTRY: Dict[str, Callable] = {
    "evaluate_race": evaluate_race,
    "run_daily_analysis": run_daily_analysis,
    "calculate_probability_edge": calculate_probability_edge,
    "calculate_max_position": calculate_max_position,
    "get_account_summary": get_account_summary,
    "record_selection": record_selection,
    "update_race_result": update_race_result,
    "search_past_races": search_past_races,
    "search_racing_data": search_racing_data,
    "verify_race_exists": verify_race_exists,
    "get_odds_snapshot": get_odds_snapshot,
}


def get_tool_names() -> List[str]:
    """Return all registered MAF tool names."""
    return list(TOOL_REGISTRY.keys())


def list_tools_with_descriptions() -> List[Dict]:
    """Return all tools with their full metadata."""
    return [
        {"name": name, **info}
        for name, info in TOOL_INFO.items()
        if name in TOOL_REGISTRY
    ]
