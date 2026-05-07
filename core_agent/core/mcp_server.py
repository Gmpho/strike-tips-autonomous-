"""
Strike Tips - MCP Server
Implements Model Context Protocol (MCP) using FastMCP
Target: Senior L7 AI DevOps standard (High Reliability)
"""

from fastmcp import FastMCP
from typing import List, Optional, Dict
from core_agent.core.strike_brain import brain
from starlette.responses import JSONResponse

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Create the MCP Server instance
mcp = FastMCP("StrikeTips")


@mcp.tool(
    name="bridge_to_redis", description="Execute Redis MCP operations via bridge."
)
async def bridge_to_redis(tool_name: str, arguments: dict) -> dict:
    server_params = StdioServerParameters(
        command="uvx",
        args=["redis-mcp-server@latest", "--url", "redis://localhost:6379/0"],
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            return {"result": result.content}


@mcp.custom_route("/mcp", methods=["GET"])
async def mcp_root(request):
    """Provides protocol information for browser-based discovery"""
    return JSONResponse(
        {
            "status": "ready",
            "protocol": "Model Context Protocol (MCP)",
            "transport": "SSE",
            "endpoints": {"handshake": "/mcp/sse", "messages": "/mcp/messages"},
            "server": "Strike Tips AI Hub",
        }
    )


from core_agent.tools.maf_tool_registry import TOOL_REGISTRY, TOOL_INFO

# Dynamically register all tools from the registry
for tool_name, tool_fn in TOOL_REGISTRY.items():
    tool_meta = TOOL_INFO.get(tool_name, {})

    def create_wrapper(name, fn, meta):
        @mcp.tool(name=name, description=meta.get("description", "No description"))
        def dynamic_tool(query: str = "") -> str:
            """Dynamic bridge to MAF tools"""
            return str(fn(query=query, strike=brain.strike))

        return dynamic_tool

    create_wrapper(tool_name, tool_fn, tool_meta)


# ── MAF Agent chat tools ──────────────────────────────────────────────────────


def _get_agent(name: str):
    pipeline = getattr(brain, "pipeline", None)
    if not pipeline:
        return None
    return (
        pipeline._get_agent(name)
        if hasattr(pipeline, "_get_agent")
        else (getattr(pipeline, "_agents", None) or {}).get(name)
    )


@mcp.tool(
    name="analyst_chat",
    description="Ask the Race Analyst agent to evaluate a race or calculate edge.",
)
async def analyst_chat(query: str) -> str:
    agent = _get_agent("analyst")
    if not agent:
        return '{"error": "Analyst agent not initialized"}'
    result = await agent.run(query, session=agent.create_session())
    return result.text if hasattr(result, "text") else str(result)


@mcp.tool(
    name="bankroll_chat",
    description="Ask the Bankroll Governor to check balance, size a stake, or record a selection.",
)
async def bankroll_chat(query: str) -> str:
    agent = _get_agent("bankroll")
    if not agent:
        return '{"error": "Bankroll agent not initialized"}'
    result = await agent.run(query, session=agent.create_session())
    return result.text if hasattr(result, "text") else str(result)


@mcp.tool(
    name="scanner_chat",
    description="Ask the Race Scanner to scan today's SA tracks for value opportunities.",
)
async def scanner_chat(query: str) -> str:
    agent = _get_agent("scanner")
    if not agent:
        return '{"error": "Scanner agent not initialized"}'
    result = await agent.run(query, session=agent.create_session())
    return result.text if hasattr(result, "text") else str(result)


@mcp.resource("racing://current-config")
def get_config_resource() -> str:
    """Provides the current betting configuration and L7 Governor settings."""
    from config.settings import BANKROLL, TRACKS

    config = {
        "bankroll": {
            "max_bet_percent": BANKROLL.max_bet_percent,
            "daily_loss_limit": BANKROLL.daily_loss_limit,
            "min_edge_threshold": BANKROLL.min_edge_threshold,
        },
        "supported_tracks": TRACKS,
    }
    return str(config)
