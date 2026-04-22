from agent_framework import Agent, SkillsProvider
from core_agent.config.model_factory import get_client


def build_scanner_agent(strike, skills_provider: SkillsProvider, chroma_provider) -> Agent:
    from core_agent.agents.tools import build_tools
    _, _, scanner_tools = build_tools(strike)
    client = get_client("SCRAPER")
    return client.as_agent(
        name="scanner",
        instructions=(
            "You are the Strike Tips Race Scanner. "
            "Scan SA tracks for today's races and flag value opportunities. "
            "Use verify_race_exists before evaluate_race. "
            "Flag STRONG_VALUE (edge ≥ 15%) races immediately."
        ),
        tools=scanner_tools,
        context_providers=[skills_provider, chroma_provider],
    )
