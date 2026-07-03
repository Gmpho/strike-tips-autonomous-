"""
Strike Tips - MCP Server
Implements Model Context Protocol (MCP) using FastMCP
"""

import asyncio
import logging
from functools import wraps
from typing import Optional
from fastmcp import FastMCP
from starlette.responses import JSONResponse
from core_agent.core.strike_brain import brain

logger = logging.getLogger("mcp-server")

mcp = FastMCP("StrikeTips")


def mcp_tool(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        try:
            result = await fn(*args, **kwargs)
            return str(result)
        except Exception as e:
            logger.error("MCP tool %s error: %s", fn.__name__, e)
            return f'{{"error": "{e}"}}'
    return wrapper


def import_tool(name: str):
    mod = __import__("core_agent.tools.maf_tool_registry", fromlist=[name])
    return getattr(mod, name)


@mcp.tool(name="chat", description="General chat with the Strike Tips AI assistant.")
@mcp_tool
async def chat_tool(query: str) -> str:
    if not query:
        return "Please provide a query."
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


@mcp.tool(name="get_account_summary", description="Return current bankroll balance, P&L, and performance stats.")
@mcp_tool
async def mcp_get_account_summary() -> str:
    fn = import_tool("get_account_summary")
    return fn(strike=brain.strike)


@mcp.tool(name="get_odds_snapshot", description="Return the latest odds snapshot for a track or all tracks.")
@mcp_tool
async def mcp_get_odds_snapshot(track: Optional[str] = None) -> str:
    fn = import_tool("get_odds_snapshot")
    return await fn(track=track, strike=brain.strike)


@mcp.tool(name="get_atr_market_movers", description="Return ATR market movers - horses with significant odds movement.")
@mcp_tool
async def mcp_get_atr_market_movers() -> str:
    fn = import_tool("get_atr_market_movers")
    return await fn(strike=brain.strike)


@mcp.tool(name="get_atr_predictor", description="Return ATR AI predictions for upcoming races.")
@mcp_tool
async def mcp_get_atr_predictor() -> str:
    fn = import_tool("get_atr_predictor")
    return await fn(strike=brain.strike)


@mcp.tool(name="get_atr_results", description="Return ATR race results from yesterday.")
@mcp_tool
async def mcp_get_atr_results() -> str:
    fn = import_tool("get_atr_results")
    return await fn(strike=brain.strike)


@mcp.tool(name="get_dream_context", description="Return recent AI dreams/insights from background reasoning.")
@mcp_tool
async def mcp_get_dream_context() -> str:
    fn = import_tool("get_dream_context")
    return await fn(strike=brain.strike)


@mcp.tool(name="search_racing_data", description="Search for racing information via web search.")
@mcp_tool
async def mcp_search_racing_data(query: str, limit: int = 3) -> str:
    fn = import_tool("search_racing_data")
    return await fn(query=query, limit=limit)


@mcp.tool(name="evaluate_race", description="Evaluate a specific race for value opportunities.")
@mcp_tool
async def mcp_evaluate_race(track: str, race_number: int = 1) -> str:
    fn = import_tool("evaluate_race")
    return await fn(track=track, race_number=race_number, strike=brain.strike)


@mcp.tool(name="run_daily_analysis", description="Run a full daily scan across all tracks and return value selections.")
@mcp_tool
async def mcp_run_daily_analysis() -> str:
    fn = import_tool("run_daily_analysis")
    return await fn(strike=brain.strike)


@mcp.tool(name="simulate_race_scenarios", description="Force on-demand scenario simulation (e.g. wind, going, scratch), recalculate runner probability shifts, and record to memory.")
@mcp_tool
async def mcp_simulate_race_scenarios(track: str, race_number: int, scenario_override: str) -> str:
    fn = import_tool("simulate_race_scenarios")
    return await fn(track=track, race_number=race_number, scenario_override=scenario_override)


@mcp.tool(name="query_racing_dreams", description="Query ChromaDB vector database for background scenario simulations matching specific tracks and conditions.")
@mcp_tool
async def mcp_query_racing_dreams(track: Optional[str] = None, keywords: Optional[str] = None, limit: int = 3) -> str:
    fn = import_tool("query_racing_dreams")
    return await fn(track=track, keywords=keywords, limit=limit)


@mcp.tool(name="analyze_full_race_card", description="Parse daily SA racecard text, compute runner win probabilities, and suggest dynamic exotics combinations (BI, PA, P6, JPs).")
@mcp_tool
async def mcp_analyze_full_race_card(card_text: str) -> str:
    fn = import_tool("analyze_full_race_card")
    result = await fn(card_text=card_text, strike=brain.strike)
    if result.get("status") == "success":
        return result["report"]
    return f"Error: {result.get('reason', 'Unknown error')}"


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
