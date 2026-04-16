from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

class BankrollSpecialist:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.allowed_tools = ["get_account_summary", "calculate_max_position", "record_selection"]

    async def process(self, intent: str, message: str, strike) -> str:
        if intent in self.allowed_tools:
            tool = TOOL_REGISTRY.get(intent)
            if tool:
                # Some tools might be async, handle appropriately
                import inspect
                if inspect.iscoroutinefunction(tool):
                    result = await tool(strike=strike, message=message)
                else:
                    result = tool(strike=strike, message=message)
                return f"Result: {result}"
        return f"Tool {intent} not allowed or not found."
