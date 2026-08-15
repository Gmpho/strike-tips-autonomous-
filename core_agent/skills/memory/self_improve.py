"""
Self-Improvement Loop — Agent saves learned insights after complex tool chains.
Inspired by Hermes Agent's skill creation after 5+ tool calls + correction patching.
"""

import logging
from typing import Optional, List, Dict

logger = logging.getLogger("self-improve")


DEFAULT_INSIGHTS: List[Dict] = [
    {
        "pattern_name": "exotic_pool_analysis",
        "description": (
            "Detect exotic pool starts from PDF leg_info fields. JP=4 legs, BI=6, PA=7, P6=6. "
            "Build pool blueprint with O(n) race_map dict. AI generates exotic_plays JSON array "
            "with legs, combinations, estimated_dividend. Cost-capped at R200 per pool via "
            "record_exotic_bet(). Settled as single unit via settle_exotic_bet()."
        ),
        "tool_sequence": [
            "analyze_card", "extract_leg_info", "build_exotics_blueprint",
            "call_ai_exotic_analysis", "record_exotic_bet"
        ],
        "key_insight": (
            "PDF leg_info is the source of truth for pool layout. Clip at total races. "
            "Skip tracks with fewer than 4 remaining legs. AI generates combos from "
            "full-card context, not hardcoded permutations."
        ),
    },
    {
        "pattern_name": "auto_betting_flow",
        "description": (
            "During run_daily_scan, check settings.json for auto_bet_enabled=true. "
            "For each value_bet, extract edge_percent (normalise 0-1 to percentage). "
            "Skip if edge < min_edge (5.5%). Place via place_bet() with confidence=AUTO. "
            "For exotic plays, call record_exotic_bet() with ticket_cost and combinations."
        ),
        "tool_sequence": [
            "run_daily_scan", "load_settings", "edge_threshold_filter",
            "place_bet", "record_exotic_bet"
        ],
        "key_insight": (
            "Auto-bets use same value_bet pipeline as Telegram alerts but skip notification. "
            "Edge normalisation: if 0 < edge < 1, multiply by 100. Exotic cost capped at "
            "MAX_EXOTIC_COST (200.0) in BankrollGovernor."
        ),
    },
    {
        "pattern_name": "bankroll_governor_rules",
        "description": (
            "Half-Kelly staking: max_stake = bankroll * (edge / 100) * 0.25. "
            "Daily loss limit: losses cannot exceed total_bankroll * 0.10. "
            "Exposure cap: open_bets stake <= total_bankroll * 0.30. "
            "Exotic cost cap: MAX_EXOTIC_COST = 200.0 per pool. "
            "Bet settlement: settle_bet(bet_id, won=True/False) updates bankroll P&L."
        ),
        "tool_sequence": [
            "calculate_max_stake", "calculate_max_position",
            "record_selection", "record_exotic_bet", "update_race_result"
        ],
        "key_insight": (
            "Edge in percentage, not decimal. Edge 8.0 = 8%. Kelly fraction is hardcoded "
            "at 0.25 (quarter-Kelly). Bankroll data persisted in data/bankroll.json. "
            "DSI (Dream Stress Index) can reduce stake by up to 50%."
        ),
    },
    {
        "pattern_name": "ai_provider_chain",
        "description": (
            "Primary: Groq llama-3.3-70b-versatile for race analysis and exotic generation. "
            "Fallback: Gemini 2.5 flash if Groq fails. No OpenAI/Kimi K providers. "
            "Multimodal: Gemini handles form image analysis. Provider selection in "
            "ai_providers.py via _call_parallel() (formerly _call_kimi_parallel)."
        ),
        "tool_sequence": [
            "analyze_race_card", "call_ai_analysis",
            "fallback_on_failure", "generate_exotic_plays"
        ],
        "key_insight": (
            "Groq is primary for speed (llama-3.3-70b). Gemini is fallback only. "
            "Never use Kimi K. Provider routing is in ai_providers.py. "
            "Parallel calls use asyncio.gather for concurrent analysis."
        ),
    },
    {
        "pattern_name": "value_bet_detection",
        "description": (
            "AI calculates fair probability from form, weight, jockey, trainer, distance. "
            "Converts to fair odds. Compares with bookmaker odds. Edge = "
            "(bookmaker_odds / fair_odds - 1) * 100. Priority alerts at edge >= 15%. "
            "Standard alerts at edge >= 8%. Marginal at >= 5.5%. "
            "Value bets sent via Telegram and optionally auto-placed."
        ),
        "tool_sequence": [
            "evaluate_race", "calculate_probability_edge",
            "calculate_max_position", "record_selection", "send_value_bet"
        ],
        "key_insight": (
            "Edge is percentage, not decimal. Odds must be decimal format. "
            "Half-Kelly stake = bankroll * (edge/100) * 0.25. "
            "Strong value (>=15%) gets priority Telegram formatting."
        ),
    },
    {
        "pattern_name": "pool_detection_from_pdf",
        "description": (
            "Scan each race's leg_info for pattern: JACKPOT=4legs, BIPOT=6legs, "
            "PLACE=7legs, PICK6=6legs. Pool start = race number where leg 1 appears. "
            "Clip at total_races - legs_needed + 1. Skip tracks with fewer than 4 remaining legs. "
            "build_exotics_blueprint() returns pool_starts dict and readable pool names."
        ),
        "tool_sequence": [
            "parse_pdf", "extract_leg_info", "scan_race_headers",
            "build_exotics_blueprint", "validate_pool_starts"
        ],
        "key_insight": (
            "PDF harvester already extracts leg_info strings like 'JACKPOT LEG 1'. "
            "Pool detection reads these — does NOT regex on raw text. "
            "Pool starts are 1-indexed race numbers."
        ),
    },
]


SELF_IMPROVE_NUDGE = (
    "\n\n=== SELF-IMPROVEMENT NUDGE ===\n"
    "If you just completed a multi-step analysis (5+ tool calls), consider saving "
    "the winning approach as a learned insight using save_learned_insight.\n"
    "Include: the pattern you used, key tools called, and the decision logic.\n"
    "This helps you reason faster on similar future queries."
)


def maybe_add_self_improve_nudge(tool_call_count: int, base_prompt: str) -> str:
    """Add self-improvement nudge if tool call count >= 5."""
    if tool_call_count >= 5:
        return base_prompt + SELF_IMPROVE_NUDGE
    return base_prompt


async def save_learned_insight(
    pattern_name: str,
    description: str,
    tool_sequence: list,
    key_insight: str,
    strike=None,
    **kwargs
) -> dict:
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
        logger.error(f"Save learned insight error: {e}")
        return {"status": "ERROR", "reason": str(e)}


def seed_default_insights() -> List[Dict]:
    """Seed ChromaDB with default learned insights about Strike Tips features.
    Call this once after a fresh ChromaDB setup to bake in feature knowledge.
    Returns list of save results — one per insight.
    """
    from core_agent.core.strike_brain import brain
    if not brain or not brain.memory or not brain.memory._is_ready:
        logger.warning("Memory not ready — cannot seed insights")
        return [{"status": "ERROR", "reason": "Memory not ready"}]

    results = []
    for insight in DEFAULT_INSIGHTS:
        content = (
            f"=== LEARNED INSIGHT: {insight['pattern_name']} ===\n"
            f"Description: {insight['description']}\n"
            f"Tool sequence: {' → '.join(insight['tool_sequence'])}\n"
            f"Key insight: {insight['key_insight']}\n"
        )
        ok = brain.memory.add_form_insight(
            horse=insight["pattern_name"],
            insight=content,
            metadata={"type": "learned_insight", "pattern_name": insight["pattern_name"]},
        )
        status = "SAVED" if ok else "FAILED"
        results.append({"status": status, "pattern": insight["pattern_name"]})
        logger.info(f"[SEED] {status}: {insight['pattern_name']}")
    return results


def get_learned_insights(n_results: int = 6) -> str:
    """Retrieve saved learned insights from ChromaDB and format as context string.
    Returns empty string on failure or if no insights found.
    """
    try:
        from core_agent.core.strike_brain import brain
        if not brain or not brain.memory or not brain.memory._is_ready:
            return ""
        results = brain.memory.search_form_insights(
            query="learned insight analysis feature",
            n_results=n_results,
            where={"type": "learned_insight"},
        )
        if not results:
            return ""
        lines = ["=== LEARNED PATTERNS FROM PAST ANALYSIS ==="]
        for r in results:
            content = r.get("content", "")
            pattern = r.get("metadata", {}).get("pattern_name", "?")
            first_line = content.split("\n")[0] if content else pattern
            lines.append(f"• {first_line}")
        lines.append("")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"Failed to retrieve learned insights: {e}")
        return ""


def analyze_performance_and_learn(bankroll) -> List[Dict]:
    """Analyze settled bet performance and auto-generate learned insights.
    
    Detects:
      - Tracks with poor ROI (< -10%) → negative pattern insight
      - Tracks with strong win rate (> 40%) → positive pattern insight
      - Odds brackets with poor ROI (< -15%) → negative bracket insight
    
    Skips patterns that already exist in ChromaDB to avoid duplicates.
    Returns list of save results — one per new insight generated.
    """
    if not bankroll:
        return [{"status": "ERROR", "reason": "No bankroll provided"}]

    from core_agent.core.strike_brain import brain
    if not brain or not brain.memory or not brain.memory._is_ready:
        logger.warning("Memory not ready — cannot auto-learn")
        return [{"status": "ERROR", "reason": "Memory not ready"}]

    # Fetch existing pattern names from ChromaDB to avoid duplicates
    existing_patterns = set()
    try:
        existing = brain.memory.search_form_insights(
            query="learned insight",
            n_results=50,
            where={"type": "learned_insight"},
        )
        for r in existing:
            name = r.get("metadata", {}).get("pattern_name", "")
            if name:
                existing_patterns.add(name)
    except Exception:
        pass

    results = []

    # 1. Track-level analysis
    track_stats = bankroll.get_settled_bets_by_track(min_bets=5)
    for stat in track_stats:
        track = stat["track"]
        roi = stat["roi"]
        wins = stat["wins"]
        total = stat["total_bets"]

        if roi < -10.0:
            pattern_name = f"low_roi_{track}"
            if pattern_name in existing_patterns:
                continue
            content = (
                f"=== LEARNED INSIGHT: {pattern_name} ===\n"
                f"Description: Track {track} has persistently low ROI over {total} settled bets. "
                f"Win rate: {stat['win_rate']:.0f}%, ROI: {roi:.1f}%. "
                f"Recommend scaling down Kelly stake by 0.5x when betting at {track}.\n"
                f"Key insight: {track} shows negative expected value. "
                f"Reduce position sizing or skip this track entirely.\n"
            )
            ok = brain.memory.add_form_insight(
                horse=pattern_name,
                insight=content,
                metadata={"type": "learned_insight", "pattern_name": pattern_name, "track": track, "roi": roi},
            )
            status = "SAVED" if ok else "FAILED"
            results.append({"status": status, "pattern": pattern_name, "type": "track_warning"})
            logger.info(f"[AUTO-LEARN] {status}: {track} ROI={roi}% ({wins}/{total})")

        elif stat["win_rate"] > 40.0 and roi > 5.0:
            pattern_name = f"strong_track_{track}"
            if pattern_name in existing_patterns:
                continue
            content = (
                f"=== LEARNED INSIGHT: {pattern_name} ===\n"
                f"Description: Track {track} shows strong performance over {total} settled bets. "
                f"Win rate: {stat['win_rate']:.0f}%, ROI: {roi:.1f}%. "
                f"This track has favourable conditions — maintain standard Kelly sizing.\n"
                f"Key insight: {track} is a high-confidence track. " 
                f"Continue applying standard bankroll rules here.\n"
            )
            ok = brain.memory.add_form_insight(
                horse=pattern_name,
                insight=content,
                metadata={"type": "learned_insight", "pattern_name": pattern_name, "track": track, "roi": roi},
            )
            status = "SAVED" if ok else "FAILED"
            results.append({"status": status, "pattern": pattern_name, "type": "track_positive"})
            logger.info(f"[AUTO-LEARN] {status}: {track} ROI={roi}% ({wins}/{total})")

    # 2. Odds-bracket analysis
    bracket_stats = bankroll.get_settled_bets_by_odds_range(min_bets=5)
    for stat in bracket_stats.values():
        bracket = stat["bracket"]
        roi = stat["roi"]
        total = stat["total_bets"]

        if total < 5:
            continue

        if roi < -15.0:
            pattern_name = f"poor_odds_{bracket}"
            if pattern_name in existing_patterns:
                continue
            content = (
                f"=== LEARNED INSIGHT: {pattern_name} ===\n"
                f"Description: Odds bracket {bracket} has poor ROI over {total} settled bets. "
                f"Win rate: {stat['win_rate']:.0f}%, ROI: {roi:.1f}%. "
                f"Horses in this odds range are underperforming expectations. "
                f"Recommend increasing edge threshold by 2% for this bracket.\n"
                f"Key insight: {bracket} shows negative expected value. "
                f"Require higher edge to compensate for the bracket bias.\n"
            )
            ok = brain.memory.add_form_insight(
                horse=pattern_name,
                insight=content,
                metadata={"type": "learned_insight", "pattern_name": pattern_name, "roi": roi},
            )
            status = "SAVED" if ok else "FAILED"
            results.append({"status": status, "pattern": pattern_name, "type": "odds_warning"})
            logger.info(f"[AUTO-LEARN] {status}: {bracket} ROI={roi}% ({stat['wins']}/{total})")

    if not results:
        logger.info("[AUTO-LEARN] No new patterns detected from settled bets")
    return results


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        from core_agent.core.strike_brain import brain
        brain.initialize()
        results = seed_default_insights()
        saved = sum(1 for r in results if r.get("status") == "SAVED")
        print(f"[SEED] {saved}/{len(results)} insights seeded")
        sys.exit(0)