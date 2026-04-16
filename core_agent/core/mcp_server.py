"""
Strike Tips - MCP Server
Implements Model Context Protocol (MCP) using FastMCP
Target: Senior L7 AI DevOps standard (High Reliability)
"""
from fastmcp import FastMCP
from typing import List, Optional, Dict
from core_agent.core.strike_brain import brain
from starlette.responses import JSONResponse

# Create the MCP Server instance
mcp = FastMCP("StrikeTips")

@mcp.custom_route("/mcp", methods=["GET"])
async def mcp_root(request):
    """Provides protocol information for browser-based discovery"""
    return JSONResponse({
        "status": "ready",
        "protocol": "Model Context Protocol (MCP)",
        "transport": "SSE",
        "endpoints": {
            "handshake": "/mcp/sse",
            "messages": "/mcp/messages"
        },
        "server": "Strike Tips AI Hub"
    })

from core_agent.tools.maf_tool_registry import TOOL_REGISTRY, TOOL_INFO

# Dynamically register all tools from the registry
for tool_name, tool_fn in TOOL_REGISTRY.items():
    tool_meta = TOOL_INFO.get(tool_name, {})
    
    # Use a unique function name for each tool registration
    def create_wrapper(name, fn, meta):
        @mcp.tool(name=name, description=meta.get("description", "No description"))
        def dynamic_tool(query: str = "") -> str:
            """Dynamic bridge to MAF tools"""
            return str(fn(query=query, strike=brain.strike))
        return dynamic_tool

    create_wrapper(tool_name, tool_fn, tool_meta)


@mcp.resource("racing://current-config")
def get_config_resource() -> str:
    """
    Provides the current betting configuration and L7 Governor settings.
    """
    from config.settings import BANKROLL, TRACKS
    config = {
        "bankroll": {
            "max_bet_percent": BANKROLL.max_bet_percent,
            "daily_loss_limit": BANKROLL.daily_loss_limit,
            "min_edge_threshold": BANKROLL.min_edge_threshold
        },
        "supported_tracks": TRACKS
    }
    return str(config) 