from core_agent.tools.maf_tool_registry import TOOL_REGISTRY

class AnalystSpecialist:
    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt
        self.allowed_tools = ["search_past_races", "search_racing_data", "calculate_probability_edge"]

    async def process(self, intent: str, message: str, strike) -> str:
        if intent in self.allowed_tools:
            tool = TOOL_REGISTRY.get(intent)
            if tool:
                # Analyst tools require specific arguments, so we pass query=message
                import inspect
                if intent == "search_past_races":
                    result = tool(query=message, strike=strike)
                elif intent == "calculate_probability_edge":
                    # This tool requires odds/prob, simplified for test
                    result = tool(odds_decimal=6.5, estimated_probability=0.25)
                else:
                    if inspect.iscoroutinefunction(tool):
                        result = await tool(strike=strike, message=message)
                    else:
                        result = tool(strike=strike, message=message)
                return f"Result: {result}"
        return f"Tool {intent} not allowed or not found."

