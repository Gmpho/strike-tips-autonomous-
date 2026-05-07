from agent_framework import Agent, SkillsProvider
from core_agent.config.model_factory import get_client


def build_bankroll_agent(strike, skills_provider: SkillsProvider) -> Agent:
    from core_agent.agents.tools import build_tools

    _, bankroll_tools, _ = build_tools(strike)
    client = get_client("FUNC_CALL")
    return client.as_agent(
        name="bankroll",
        instructions=(
            "You are the Strike Tips Bankroll Governor. "
            "Enforce Half-Kelly staking, 5% max stake, 20% daily loss limit. "
            "Always call get_account_summary before approving any selection. "
            "Return structured JSON matching the BetDecision schema."
        ),
        tools=bankroll_tools,
        context_providers=[skills_provider],
    )
