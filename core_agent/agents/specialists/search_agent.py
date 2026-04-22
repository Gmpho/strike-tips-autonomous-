from agent_framework import Agent, SkillsProvider
from core_agent.config.model_factory import get_client


def build_search_agent(strike, skills_provider: SkillsProvider) -> Agent:
    from core_agent.agents.tools import build_tools
    analyst_tools, _, _ = build_tools(strike)
    # analyst_tools = [calculate_probability_edge, search_past_races, search_racing_data, evaluate_race]
    # indices 1 and 2 are the search tools
    search_tools = analyst_tools[1:3]
    client = get_client("SCRAPER")
    return client.as_agent(
        name="search",
        instructions=(
            "You are the Strike Tips Search Specialist. "
            "Perform multi-step research to gather high-fidelity SA racing intelligence. "
            "If a query yields low-confidence data, rephrase and search again. "
            "Summarise findings into concise, actionable insights."
        ),
        tools=search_tools,
        context_providers=[skills_provider],
    )
