from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

class ScannerSpecialist:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.allowed_tools = ["run_daily_analysis", "verify_race_exists", "evaluate_race", "get_odds_snapshot"]

    async def process(self, intent: str, message: str, strike) -> str:
        if intent in self.allowed_tools:
            tool = TOOL_REGISTRY.get(intent)
            if tool:
                import inspect
                if inspect.iscoroutinefunction(tool):
                    result = await tool(strike=strike, message=message)
                else:
                    result = tool(strike=strike, message=message)
                return f"Result: {result}"
        return f"Tool {intent} not allowed or not found."
