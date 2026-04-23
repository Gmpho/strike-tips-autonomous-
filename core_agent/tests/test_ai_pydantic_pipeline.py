from unittest.mock import AsyncMock

import pytest

from core_agent.agents.ai_pydantic import ModelPipeline
from core_agent.agents.schemas import AgentReply


@pytest.mark.asyncio
async def test_chat_cold_start_attempts_lazy_agent_creation():
    pipeline = ModelPipeline(strike_tips=object())
    assert pipeline._agents == {}

    pipeline._run_with_fallback = AsyncMock(  # type: ignore[method-assign]
        return_value=AgentReply(summary="ok", model_used="analyst")
    )

    response = await pipeline.chat("please analyze this race")

    pipeline._run_with_fallback.assert_awaited_once()
    assert response.summary == "ok"
    assert response.model_used == "analyst"
    assert response.summary != "Strike Brain not initialized."
