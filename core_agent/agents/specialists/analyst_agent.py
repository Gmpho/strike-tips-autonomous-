from pathlib import Path
from agent_framework import Agent, SkillsProvider
from core_agent.config.model_factory import get_client

_SKILLS_DIR = Path(__file__).parent.parent.parent / "skills"


def build_analyst_agent(strike, skills_provider: SkillsProvider, chroma_provider) -> Agent:
    from core_agent.agents.tools import build_tools
    analyst_tools, _, _ = build_tools(strike)
    client = get_client("SCRAPER")  # racing_qwen — tool-capable
    return client.as_agent(
        name="analyst",
        instructions=(
            "You are the Strike Tips Race Analyst. "
            "Use your tools to research form and calculate edge. "
            "Always return structured JSON matching the RaceAnalysis schema."
        ),
        tools=analyst_tools,
        context_providers=[skills_provider, chroma_provider],
    )
