"""
MAF Tool Registry
Standardized tool registration for Strike Bot.
"""
from typing import Dict, Callable, Any
from pydantic_ai import RunContext
# Absolute imports to Strike Bot
from core.brain import StrikeDeps

class MAFToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, func: Callable):
        self._tools[name] = func

    def get_tool_definitions(self) -> list:
        # Returns list of tools for LLM tool-calling schema
        return [
            {"name": name, "description": func.__doc__}
            for name, func in self._tools.items()
        ]

    async def execute_tool(self, name: str, args: Dict[str, Any], deps: StrikeDeps) -> Any:
        if name in self._tools:
            return await self._tools[name](deps, **args)
        raise ValueError(f"Tool {name} not found.")

# Global Registry
registry = MAFToolRegistry()
