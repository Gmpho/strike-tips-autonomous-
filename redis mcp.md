import asyncio
from fastmcp import Client

# 1. Define your multi-server config
config = {
    "mcpServers": {
        "redis": {
            "command": "uvx",
            "args": ["mcp-redis"]
        },
        "devtools": {
            "command": "npx",
            "args": ["-y", "chrome-devtools-mcp@latest"]
        }
    }
}


Why this works for your bot:
Automatic Lifecycle: FastMCP launches the servers as subprocesses when your bot starts and cleans them up when it exits.
Namespacing: Tools are automatically prefixed (e.g., redis_ or devtools_), so you don't have conflicting tool names if both servers have a "get" command.
Async Ready: Since racing bots often need to handle real-time data, FastMCP’s native asyncio support ensures your bot doesn't freeze while waiting for a browser to load or a database to respond. 
FastMCP
FastMCP
 +1
Configuring Chrome for DevTools MCP 
For the Chrome MCP to work with a live browser your bot can "see," you must start Chrome with remote debugging enabled first:
Command: google-chrome --remote-debugging-port=9222
The Chrome DevTools MCP will then connect to this port automatically or via the --autoConnect flag
