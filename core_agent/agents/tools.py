"""
MAF @tool wrappers for the 11 Strike Tips tool registry functions.
strike_instance is injected via closure — call build_tools(strike) to get grouped lists.
"""
from typing import Annotated, Optional
from pydantic import Field
from agent_framework import tool
from core_agent.tools.maf_tool_registry import TOOL_REGISTRY


def build_tools(strike):
    """Return (ANALYST_TOOLS, BANKROLL_TOOLS, SCANNER_TOOLS) with strike injected."""

    # ── Read-ops ──────────────────────────────────────────────────────────────

    @tool(approval_mode="never_require")
    def calculate_probability_edge(
        odds_decimal: Annotated[float, Field(description="Decimal odds e.g. 6.5")],
        estimated_probability: Annotated[float, Field(description="Your estimated win probability 0-1")],
    ) -> dict:
        """Calculate betting edge = (estimated_prob - implied_prob) × 100."""
        return TOOL_REGISTRY["calculate_probability_edge"](
            odds_decimal=odds_decimal, estimated_probability=estimated_probability
        )

    @tool(approval_mode="never_require")
    def calculate_max_position(
        edge_percent: Annotated[float, Field(description="Edge percentage e.g. 12.5")],
    ) -> dict:
        """Calculate max allowed stake using Half-Kelly, capped at 5% of bankroll."""
        return TOOL_REGISTRY["calculate_max_position"](edge_percent=edge_percent, strike=strike)

    @tool(approval_mode="never_require")
    def get_account_summary() -> dict:
        """Return current bankroll balance, P&L, open bets, and performance stats."""
        return TOOL_REGISTRY["get_account_summary"](strike=strike)

    @tool(approval_mode="never_require")
    def search_past_races(
        query: Annotated[str, Field(description="Search query e.g. 'Turffontein 1600m form'")],
        n_results: Annotated[int, Field(description="Number of results", default=5)] = 5,
    ) -> dict:
        """Semantic search over historical race data in ChromaDB memory."""
        return TOOL_REGISTRY["search_past_races"](query=query, n_results=n_results, strike=strike)

    @tool(approval_mode="never_require")
    def search_racing_data(
        query: Annotated[str, Field(description="Search query for live racing data")],
    ) -> dict:
        """Search for racing information via DuckDuckGo web search."""
        return TOOL_REGISTRY["search_racing_data"](query=query)

    @tool(approval_mode="never_require")
    def verify_race_exists(
        track: Annotated[str, Field(description="Track name e.g. turffontein")],
        race_number: Annotated[int, Field(description="Race number")],
    ) -> dict:
        """Verify if a race is scheduled today at the given track."""
        return TOOL_REGISTRY["verify_race_exists"](track=track, race_number=race_number, strike=strike)

    @tool(approval_mode="never_require")
    def get_odds_snapshot(
        track: Annotated[Optional[str], Field(description="Track name or None for all tracks")] = None,
    ) -> dict:
        """Return latest odds snapshot for one or all tracks."""
        return TOOL_REGISTRY["get_odds_snapshot"](track=track, strike=strike)

    @tool(approval_mode="never_require")
    async def evaluate_race(
        track: Annotated[str, Field(description="Track name")],
        race_number: Annotated[int, Field(description="Race number")] = 1,
    ) -> dict:
        """Evaluate a specific race for value opportunities."""
        return await TOOL_REGISTRY["evaluate_race"](track=track, race_number=race_number, strike=strike)

    @tool(approval_mode="never_require")
    async def run_daily_analysis(
        tracks: Annotated[Optional[list[str]], Field(description="List of tracks or None for all")] = None,
    ) -> dict:
        """Run full daily analysis scan across all SA tracks."""
        return await TOOL_REGISTRY["run_daily_analysis"](tracks=tracks, strike=strike)

    # ── Write-ops (require approval) ──────────────────────────────────────────

    @tool(approval_mode="always_require")
    def record_selection(
        track: Annotated[str, Field(description="Track name")],
        race_number: Annotated[int, Field(description="Race number")],
        horse: Annotated[str, Field(description="Horse name")],
        odds: Annotated[float, Field(description="Decimal odds")],
        position_size: Annotated[float, Field(description="Stake in ZAR")],
        edge_percent: Annotated[float, Field(description="Edge percentage")],
        confidence: Annotated[str, Field(description="VALUE | STRONG_VALUE | MARGINAL")],
    ) -> dict:
        """Record a new selection through the bankroll governor."""
        return TOOL_REGISTRY["record_selection"](
            track=track, race_number=race_number, horse=horse, odds=odds,
            position_size=position_size, edge_percent=edge_percent,
            confidence=confidence, strike=strike,
        )

    @tool(approval_mode="always_require")
    def update_race_result(
        selection_id: Annotated[str, Field(description="Bet ID to settle")],
        result: Annotated[str, Field(description="WON or LOST")],
        notes: Annotated[str, Field(description="Optional notes")] = "",
    ) -> dict:
        """Settle an open selection with WON or LOST result."""
        return TOOL_REGISTRY["update_race_result"](
            selection_id=selection_id, result=result, notes=notes, strike=strike
        )

    ANALYST_TOOLS = [
        calculate_probability_edge, search_past_races,
        search_racing_data, evaluate_race,
    ]
    BANKROLL_TOOLS = [
        get_account_summary, calculate_max_position,
        record_selection, update_race_result,
    ]
    SCANNER_TOOLS = [
        run_daily_analysis, verify_race_exists,
        evaluate_race, get_odds_snapshot, search_racing_data,
    ]

    return ANALYST_TOOLS, BANKROLL_TOOLS, SCANNER_TOOLS
