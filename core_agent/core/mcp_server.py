"""
Strike Tips - MCP Server
Implements Model Context Protocol (MCP) using FastMCP
"""

import asyncio
import logging
from typing import Optional
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from core_agent.core.strike_brain import brain

logger = logging.getLogger("mcp-server")

mcp = FastMCP("StrikeTips")


@mcp.tool(name="chat", description="General chat with the Strike Tips AI assistant.")
async def chat_tool(query: str) -> str:
    if not query:
        return "Please provide a query."
    try:
        from core_agent.agent.providers.task_router import TaskRouter
        router = TaskRouter()
        messages = [
            {"role": "system", "content": "You are Strike Tips AI, expert in horse racing analysis."},
            {"role": "user", "content": query},
        ]
        chunks = []
        async for chunk in router.stream(messages, None, None):
            chunks.append(chunk)
        return "".join(chunks) or "No response."
    except Exception as e:
        logger.error("MCP chat error: %s", e)
        return f"Error: {e}"


@mcp.tool(name="get_account_summary", description="Return current bankroll balance, P&L, and performance stats.")
async def mcp_get_account_summary() -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_account_summary as tool_fn
        result = tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="get_odds_snapshot", description="Return the latest odds snapshot for a track or all tracks.")
async def mcp_get_odds_snapshot(track: Optional[str] = None) -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_odds_snapshot as tool_fn
        result = await tool_fn(track=track, strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="get_atr_market_movers", description="Return ATR market movers - horses with significant odds movement.")
async def mcp_get_atr_market_movers() -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_atr_market_movers as tool_fn
        result = await tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="get_atr_predictor", description="Return ATR AI predictions for upcoming races.")
async def mcp_get_atr_predictor() -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_atr_predictor as tool_fn
        result = await tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="get_atr_results", description="Return ATR race results from yesterday.")
async def mcp_get_atr_results() -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_atr_results as tool_fn
        result = await tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="get_dream_context", description="Return recent AI dreams/insights from background reasoning.")
async def mcp_get_dream_context() -> str:
    try:
        from core_agent.tools.maf_tool_registry import get_dream_context as tool_fn
        result = await tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="search_racing_data", description="Search for racing information via web search.")
async def mcp_search_racing_data(query: str, limit: int = 3) -> str:
    try:
        from core_agent.tools.maf_tool_registry import search_racing_data as tool_fn
        result = await tool_fn(query=query, limit=limit)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="evaluate_race", description="Evaluate a specific race for value opportunities.")
async def mcp_evaluate_race(track: str, race_number: int = 1) -> str:
    try:
        from core_agent.tools.maf_tool_registry import evaluate_race as tool_fn
        result = await tool_fn(track=track, race_number=race_number, strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="run_daily_analysis", description="Run a full daily scan across all tracks and return value selections.")
async def mcp_run_daily_analysis() -> str:
    try:
        from core_agent.tools.maf_tool_registry import run_daily_analysis as tool_fn
        result = await tool_fn(strike=brain.strike)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="simulate_race_scenarios", description="Force on-demand scenario simulation (e.g. wind, going, scratch), recalculate runner probability shifts, and record to memory.")
async def mcp_simulate_race_scenarios(track: str, race_number: int, scenario_override: str) -> str:
    try:
        from core_agent.tools.maf_tool_registry import simulate_race_scenarios as tool_fn
        result = await tool_fn(track=track, race_number=race_number, scenario_override=scenario_override)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="query_racing_dreams", description="Query ChromaDB vector database for background scenario simulations matching specific tracks and conditions.")
async def mcp_query_racing_dreams(track: Optional[str] = None, keywords: Optional[str] = None, limit: int = 3) -> str:
    try:
        from core_agent.tools.maf_tool_registry import query_racing_dreams as tool_fn
        result = await tool_fn(track=track, keywords=keywords, limit=limit)
        return str(result)
    except Exception as e:
        return f'{{"error": "{e}"}}'


@mcp.tool(name="analyze_full_race_card", description="Parse daily SA racecard text, compute runner win probabilities, and suggest dynamic exotics combinations (BI, PA, P6, JPs).")
async def mcp_analyze_full_race_card(card_text: str) -> str:
    try:
        from core_agent.tools.maf_tool_registry import analyze_full_race_card as tool_fn
        result = await tool_fn(card_text=card_text, strike=brain.strike)
        if result.get("status") == "success":
            return result["report"]
        else:
            return f"Error: {result.get('reason', 'Unknown error')}"
    except Exception as e:
        return f"Error wrapper: {e}"


@mcp.resource("racing://current-config")
def get_config_resource() -> str:
    try:
        from core_agent.config.settings import BANKROLL, TRACKS
        config = {
            "bankroll": {
                "max_bet_percent": BANKROLL.max_bet_percent,
                "daily_loss_limit": BANKROLL.daily_loss_limit,
                "min_edge_threshold": BANKROLL.min_edge_threshold,
            },
            "supported_tracks": list(TRACKS.keys()),
        }
        return str(config)
    except Exception as e:
        return f'{{"error": "Config not available: {e}"}}'


@mcp.custom_route("/mcp", methods=["GET"])
async def mcp_root(request):
    return JSONResponse({
        "status": "ready",
        "protocol": "Model Context Protocol (MCP)",
        "transport": "SSE",
        "endpoints": {"handshake": "/mcp/sse", "messages": "/mcp/messages"},
        "server": "Strike Tips AI Hub",
    })
