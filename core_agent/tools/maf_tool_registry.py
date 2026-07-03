"""
MAF Tool Registry - 11 Gambling-Free Tools for Strike Bot
Each tool is a plain Python function callable by the agent pipeline.
Tool names follow the func_gemma-compatible naming convention.
"""

import asyncio
import json
import logging
import re
from dataclasses import asdict
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from core_agent.core.redis_cache import get_cache, set_cache
from core_agent.skills.exotics.parser import (
    extract_form_string,
    detect_jockey_trainer,
    compute_win_probability,
)
from core_agent.skills.exotics.builder import build_exotics_blueprint

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
        "description": "Return the latest odds snapshot for one or all tracks (Betway as primary source).",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "What are the current odds at Kenilworth?",
    },
    "get_atr_market_movers": {
        "description": "Return ATR market movers - horses with significant odds movement.",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "Show me today's ATR market movers",
    },
    "get_atr_predictor": {
        "description": "Return ATR AI predictions for upcoming races.",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "What are the ATR predictor tips for today?",
    },
    "get_atr_results": {
        "description": "Return ATR race results from yesterday.",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "Show me yesterday's ATR race results",
    },
    "get_dream_context": {
        "description": "Return recent AI dreams/insights generated from live race data (background reasoning).",
        "specialist": "racing_qwen",
        "category": "data",
        "speed": "~1-2s",
        "use_case": "What has the agent been dreaming about lately?",
    },
    "search_racing_keywords": {
        "description": "Keyword search over indexed race data using BM25 full-text search. Supports exact phrases, OR, and prefix matching. Better for exact horse/track names than semantic search.",
        "specialist": "racing_qwen",
        "category": "search",
        "speed": "~1s",
        "use_case": "Find all indexed data mentioning 'Winter Mountain' or 'Turffontein 1600m'",
    },
    "search_hybrid": {
        "description": "Hybrid search combining BM25 keyword search + semantic vector search. Best for finding relevant racing info when you're not sure of exact terms. Weights: 60% keyword, 40% semantic.",
        "specialist": "racing_qwen",
        "category": "search",
        "speed": "~2s",
        "use_case": "Find anything about Turffontein 1600m form — exact or similar",
    },
    "save_learned_insight": {
        "description": "Save a learned analysis pattern after a multi-step tool chain (5+ calls). Captures the winning approach for future reuse.",
        "specialist": "racing_qwen",
        "category": "learning",
        "speed": "~1s",
        "use_case": "Save the Turffontein rail bias analysis pattern after 5 tool calls",
    },
    "simulate_race_scenarios": {
        "description": "Force on-demand scenario simulation (e.g. wind, going, scratch), recalculate runner probability shifts, and record to memory.",
        "specialist": "ds_racing",
        "category": "analysis",
        "speed": "~3-5s",
        "use_case": "Simulate heavy rain scenario for Vaal Race 4",
    },
    "query_racing_dreams": {
        "description": "Query ChromaDB vector database for background scenario simulations matching specific tracks and conditions.",
        "specialist": "racing_qwen",
        "category": "search",
        "speed": "~2s",
        "use_case": "Find all soft going dreams simulated for Vaal",
    },
    "analyze_full_race_card": {
        "description": "Parse a raw daily South African racecard (Greyville, Kenilworth, etc.), compute runner win probabilities (weighted form & jockey/trainer combinations), and map out optimal exotic combinations (Pick 3/6, Bipot, PA, Jackpots) with dynamic leg detection.",
        "specialist": "lfm_racing",
        "category": "analysis",
        "speed": "~5-10s",
        "use_case": "Parse and analyze today's card to suggest exotics and find value",
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
    distance: Optional[int] = None,
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
            distance=distance,
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
        # Use strike.settle_bet() which wires to LearningEngine
        settle_result = strike.settle_bet(selection_id, won=won, notes=notes)
        if settle_result and settle_result.get("settled"):
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
    """Return the latest odds snapshot for a track or all tracks (Betway as primary source)."""
    if strike:
        try:
            return await strike.get_odds_snapshot(track=track)
        except Exception as e:
            return {"status": "error", "error": str(e)}
    from core_agent.core.snapshot_cache import get_snapshot
    snap = get_snapshot()
    events = snap.get("events", {})
    if track:
        track_lower = track.lower()
        filtered = {k: v for k, v in events.items() if track_lower in v.get("course", "").lower() or track_lower in v.get("en", "").lower()}
        return {"events": filtered, "count": len(filtered), "track": track}
    return snap


async def get_atr_market_movers(strike=None, **kwargs) -> Dict:
    """Return ATR market movers from disk snapshot."""
    from core_agent.config.paths import ATR_MOVERS_PATH
    import json
    if ATR_MOVERS_PATH.exists():
        data = json.loads(ATR_MOVERS_PATH.read_text())
        movers = data.get("movers", [])
        return {"movers": movers, "count": len(movers), "source": "ATR", "last_update": data.get("last_update")}
    return {"movers": [], "count": 0, "source": "ATR", "error": "No snapshot available"}


async def get_atr_predictor(strike=None, **kwargs) -> Dict:
    """Return ATR AI predictions from disk snapshot."""
    from core_agent.config.paths import ATR_PREDICTOR_PATH
    import json
    if ATR_PREDICTOR_PATH.exists():
        data = json.loads(ATR_PREDICTOR_PATH.read_text())
        predictions = data.get("predictions", [])
        return {"predictions": predictions, "count": len(predictions), "source": "ATR", "last_update": data.get("last_update")}
    return {"predictions": [], "count": 0, "source": "ATR", "error": "No snapshot available"}


async def get_atr_results(strike=None, **kwargs) -> Dict:
    """Return ATR race results from disk snapshot."""
    from core_agent.config.paths import ATR_RESULTS_PATH
    import json
    if ATR_RESULTS_PATH.exists():
        data = json.loads(ATR_RESULTS_PATH.read_text())
        results = data.get("results", [])
        return {"results": results, "count": len(results), "source": "ATR", "last_update": data.get("last_update")}
    return {"results": [], "count": 0, "source": "ATR", "error": "No snapshot available"}


async def get_dream_context(strike=None, **kwargs) -> Dict:
    """Return recent AI dreams/insights from background reasoning engine."""
    try:
        from core_agent.skills.memory.honcho_memory import dream_honcho
        dream_context = dream_honcho.get_dream_context()
        if dream_context:
            return {"dream_context": dream_context, "source": "honcho_dream_memory"}
    except Exception as e:
        pass
    # Fallback to local dream memory
    try:
        from core_agent.core.dream_memory import read_memories
        dreams = read_memories("dreams", limit=5)
        if dreams:
            return {
                "dream_context": " | ".join(d.get("body", "") for d in dreams if d.get("body")),
                "source": "local_dream_memory"
            }
    except Exception:
        pass
    return {"dream_context": "", "source": "none", "error": "No dreams available"}


async def evaluate_race(
    track: str, race_number: int = 1, strike=None, **kwargs
) -> Dict:
    """Evaluate a specific race for value opportunities — with Redis racecard cache."""
    from core_agent.core.redis_cache import get_cache, set_cache
    from datetime import date

    if not strike:
        return {"status": "ERROR", "reason": "StrikeTips not initialized"}

    cache_key = f"racecard:{track.lower()}:{date.today().isoformat()}"
    cached = await get_cache(cache_key)
    if cached:
        logger.info(f"[MAF] Racecard cache HIT: {cache_key}")
        return cached

    try:
        result = await strike.evaluate_race(track, race_number)
        await set_cache(cache_key, result, ttl=900)
        logger.info(f"[MAF] Racecard cache SET: {cache_key}")
        return result
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


async def search_racing_keywords(query: str, n: int = 10, source_type: Optional[str] = None, **kwargs) -> Dict:
    """BM25 full-text keyword search over indexed race data (FTS5)."""
    try:
        from core_agent.skills.search.fts5_search import FTS5Search
        searcher = FTS5Search()
        results = searcher.search(query, n=n, source_type=source_type)
        return {
            "query": query,
            "results": [
                {
                    "content": r["content"],
                    "source_type": r["source_type"],
                    "score": r["score"],
                    "method": r["method"],
                }
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        return {"query": query, "error": str(e), "results": [], "count": 0}


async def search_hybrid(
    query: str, n: int = 10, source_type: Optional[str] = None,
    keyword_weight: float = 0.6, semantic_weight: float = 0.4, **kwargs
) -> Dict:
    """Hybrid search: BM25 keyword + ChromaDB semantic (60/40 weighting)."""
    try:
        from core_agent.skills.search.fts5_search import FTS5Search
        searcher = FTS5Search()
        results = searcher.hybrid_search(
            query, n=n, source_type=source_type,
            keyword_weight=keyword_weight, semantic_weight=semantic_weight
        )
        return {
            "query": query,
            "results": [
                {
                    "content": r["content"],
                    "source_type": r["source_type"],
                    "hybrid_score": r["hybrid_score"],
                    "keyword_score": r["keyword_score"],
                    "semantic_score": r["semantic_score"],
                    "method": r["method"],
                }
                for r in results
            ],
            "count": len(results),
        }
    except Exception as e:
        return {"query": query, "error": str(e), "results": [], "count": 0}


async def save_learned_insight(
    pattern_name: str,
    description: str,
    tool_sequence: list,
    key_insight: str,
    strike=None,
    **kwargs
) -> Dict:
    """Save a learned analysis pattern as a ChromaDB insight (type=learned_insight)."""
    if not strike or not hasattr(strike, "memory") or not strike.memory._is_ready:
        return {"status": "ERROR", "reason": "Memory not available"}

    try:
        content = (
            f"=== LEARNED INSIGHT: {pattern_name} ===\n"
            f"Description: {description}\n"
            f"Tool sequence: {' → '.join(tool_sequence)}\n"
            f"Key insight: {key_insight}\n"
        )

        from core_agent.core.strike_brain import brain
        if brain and brain.memory and brain.memory._is_ready:
            success = brain.memory.add_form_insight(
                horse=pattern_name,
                insight=content,
                metadata={"type": "learned_insight", "pattern_name": pattern_name}
            )
            if success:
                return {"status": "SAVED", "pattern": pattern_name}
        return {"status": "ERROR", "reason": "Failed to save"}
    except Exception as e:
        return {"status": "ERROR", "reason": str(e)}


async def simulate_race_scenarios(track: str, race_number: int, scenario_override: str, **kwargs) -> Dict[str, Any]:
    """Force on-demand scenario simulation, recalculate runner probability shift and record to memory."""
    try:
        from core_agent.skills.dreamer import dream_engine
        d = await dream_engine.generate_custom_dream(
            track=track,
            race_num=race_number,
            scenario_override=scenario_override
        )
        return {
            "status": "success",
            "dream_id": d.id,
            "track": d.track,
            "race": d.race,
            "scenario": d.scenario,
            "probability_shift": d.probability_shift,
            "vividness": d.vividness,
            "insight": d.insight
        }
    except Exception as e:
        logger.error(f"simulate_race_scenarios failed: {e}")
        return {"status": "error", "reason": str(e)}


async def query_racing_dreams(track: Optional[str] = None, keywords: Optional[str] = None, limit: int = 3, **kwargs) -> Dict[str, Any]:
    """Query ChromaDB vector database for past simulations matching specific tracks and conditions."""
    try:
        from core_agent.core.strike_brain import brain
        if not brain or not brain.memory or not brain.memory._is_ready:
            return {"status": "error", "reason": "Memory not ready"}
            
        where = {"type": "dream"}
        if track:
            where["track"] = track.lower()
            
        results = brain.memory.search_form_insights(
            query=keywords or "simulation",
            n_results=limit,
            where=where
        )
        
        dreams = []
        for r in results:
            meta = r.get("metadata", {})
            dreams.append({
                "track": meta.get("track"),
                "race": meta.get("race"),
                "scenario": meta.get("scenario"),
                "probability_shift": meta.get("probability_shift"),
                "vividness": meta.get("vividness"),
                "timestamp": meta.get("timestamp"),
                "content": r.get("content")
            })
            
        return {
            "status": "success",
            "track": track,
            "keywords": keywords,
            "count": len(dreams),
            "dreams": dreams
        }
    except Exception as e:
        logger.error(f"query_racing_dreams failed: {e}")
        return {"status": "error", "reason": str(e)}


# ─── Exotics & Full Card Analysis Tool (helpers in core_agent/skills/exotics/) ──


# ─── Full Card Analysis Tool ──────────────────────────────────────────────────

async def analyze_full_race_card(card_text: str, strike=None, **kwargs) -> Dict[str, Any]:
    """Parses daily racecard text, calculates runner win probabilities, and suggests exotics paths."""
    try:
        card_text = card_text.replace("‑", "-").replace("–", "-").replace("—", "-")
        
        # 1. Parse text into races
        races_raw = []
        blocks = re.split(r'(?i)\bRace\s+(\d+)\b', card_text)
        
        if len(blocks) < 3:
            # Fallback split
            blocks = re.split(r'(?m)^(\d+)\s+–\s+\d{2}:\d{2}', card_text)
            
        if len(blocks) < 3:
            return {"status": "error", "reason": "Could not identify races. Ensure races start with 'Race X' or 'X - HH:MM'."}
            
        for i in range(1, len(blocks), 2):
            race_num = int(blocks[i])
            content = blocks[i+1]
            
            header = " ".join(content.split("\n")[:3])
            
            runners = []
            for line in content.split("\n"):
                line = line.strip()
                if not line.startswith("#"):
                    continue
                
                num_match = re.match(r'^#(\d+)\s+([A-Za-z\s\'\-]+?)\s*\((\d+(?:\.\d+)?)kg\)', line)
                if num_match:
                    h_num = int(num_match.group(1))
                    h_name = num_match.group(2).strip()
                    h_weight = float(num_match.group(3))
                    
                    jockey, trainer = detect_jockey_trainer(line)
                    form_str = extract_form_string(line)
                    
                    runners.append({
                        "number": h_num,
                        "name": h_name,
                        "weight": h_weight,
                        "jockey": jockey,
                        "trainer": trainer,
                        "form": form_str,
                        "raw_line": line
                    })
                    
            pools_started = []
            for pool in ["JP1", "JP2", "JP3", "BI1", "BI2", "PA", "P6", "BIPOT", "JACKPOT"]:
                if re.search(rf'\b{pool}\b', header, re.IGNORECASE):
                    pools_started.append(pool.upper())
                    
            if runners:
                races_raw.append({
                    "number": race_num,
                    "runners": runners,
                    "pools": pools_started,
                    "header": header
                })
                
        if not races_raw:
            return {"status": "error", "reason": "No runners parsed from the racecard."}
            
        # 2. Run probability scoring for all runners
        for race in races_raw:
            field_size = len(race["runners"])
            for r in race["runners"]:
                r["prob"] = compute_win_probability(r["form"], r["weight"], r["jockey"], r["trainer"], field_size)
                
        # 3. Dynamic Exotics Mapping
        blueprints, starts = build_exotics_blueprint(races_raw)
        
        # 4. Generate the Markdown Report
        lines = []
        lines.append("🏇 **STRIKE TIPS L7 RACE ANALYSIS & EXOTICS BLUEPRINT**")
        lines.append(f"📊 *Parsed {len(races_raw)} races | Dynamic Pool Detection Active*\n")
        
        pool_starts_str = ", ".join(f"{k}: Race {v}" for k, v in sorted(starts.items()))
        lines.append(f"🔍 **Detected Pool Starts:** {pool_starts_str}\n")
        
        for race in races_raw:
            lines.append("---")
            lines.append(f"### Race {race['number']}")
            if race["pools"]:
                lines.append(f"🏆 *Pools declared: {', '.join(race['pools'])}*")
                
            sorted_runners = sorted(race["runners"], key=lambda r: r["prob"], reverse=True)
            top_3 = sorted_runners[:3]
            
            field_size = len(race["runners"])
            implied_avg = 1.15 / field_size
            
            for r in race["runners"]:
                r["edge"] = r["prob"] - implied_avg
                
            value_shots = [r for r in race["runners"] if r["edge"] >= 0.05 and r["name"] not in [t["name"] for t in top_3]]
            big_shots = value_shots[:2] if value_shots else sorted_runners[3:5]
            
            lines.append("**🎯 Top 3 Contenders:**")
            for idx, r in enumerate(top_3, 1):
                j_t = f" (J:{r['jockey']}, T:{r['trainer']})" if r["jockey"] or r["trainer"] else ""
                lines.append(f"  {idx}. #{r['number']} **{r['name']}** ({r['weight']}kg) - Win Prob: {r['prob']:.1%}{j_t}")
                
            lines.append("\n**💣 Big 2 Shots (Value / Exotics Savers):**")
            for r in big_shots:
                j_t = f" (J:{r['jockey']}, T:{r['trainer']})" if r["jockey"] or r["trainer"] else ""
                lines.append(f"  • #{r['number']} **{r['name']}** (Form: {r['form'] or 'Unknown'}){j_t}")
                
            if sorted_runners:
                banker = sorted_runners[0]
                lines.append(f"\n🥇 **Win Bet Suggestion**: #{banker['number']} **{banker['name']}**")
                
            lines.append("")
            
        lines.append("---")
        lines.append("📋 **EXOTICS COMBINATION SHEET**")
        
        for pool_name, legs in blueprints.items():
            lines.append(f"\n🏆 **{pool_name} Layout:**")
            banker_tokens = []
            saver_tokens = []
            for leg in legs:
                b = leg["banker"]
                banker_tokens.append(f"R{leg['race']}: #{b['number']}")
                
                s_list = [f"#{s['number']}" for s in leg["savers"]]
                saver_tokens.append(f"R{leg['race']}: {'/'.join(s_list)}")
                
            lines.append(f"  • **Banker Path:** {' | '.join(banker_tokens)}")
            lines.append(f"  • **Savers Path:** {' | '.join(saver_tokens)}")
            
        lines.append("\n---")
        lines.append("⚖️ *Governance: Staking sizes are subject to drawdown and Kelly limits. Bet responsibly.*")
        
        report_text = "\n".join(lines)
        return {
            "status": "success",
            "races_parsed": len(races_raw),
            "pool_starts": starts,
            "report": report_text
        }
        
    except Exception as e:
        logger.error(f"analyze_full_race_card failed: {e}")
        return {"status": "error", "reason": str(e)}


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
    "get_atr_market_movers": get_atr_market_movers,
    "get_atr_predictor": get_atr_predictor,
    "get_atr_results": get_atr_results,
    "get_dream_context": get_dream_context,
    "search_racing_keywords": search_racing_keywords,
    "search_hybrid": search_hybrid,
    "save_learned_insight": save_learned_insight,
    "simulate_race_scenarios": simulate_race_scenarios,
    "query_racing_dreams": query_racing_dreams,
    "analyze_full_race_card": analyze_full_race_card,
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
