from unittest.mock import AsyncMock

import pytest

from core_agent.agents.ai_pydantic import (
    UNSUPPORTED_GEOGRAPHY_SCOPE_MESSAGE,
    ModelPipeline,
    UnifiedOrchestrator,
)
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


@pytest.mark.asyncio
async def test_unified_orchestrator_returns_deterministic_scope_message_for_uk_query():
    orchestrator = UnifiedOrchestrator(strike_tips=None)
    orchestrator.pipeline.chat = AsyncMock()  # type: ignore[method-assign]

    response = await orchestrator.chat("Can you analyze Cheltenham and Southwell in the UK?")

    orchestrator.pipeline.chat.assert_not_called()
    assert response.summary == UNSUPPORTED_GEOGRAPHY_SCOPE_MESSAGE
    assert response.model_used == "intent_handler"
    assert response.confidence == 1.0


@pytest.mark.asyncio
async def test_unified_orchestrator_sa_query_routes_to_pipeline():
    orchestrator = UnifiedOrchestrator(strike_tips=None)
    orchestrator.pipeline.chat = AsyncMock(  # type: ignore[method-assign]
        return_value=AgentReply(summary="SA scan complete", model_used="scanner")
    )

    response = await orchestrator.chat("Please scan Vaal races today")

    orchestrator.pipeline.chat.assert_awaited_once_with(
        "Please scan Vaal races today", model_override=None
    )
    assert response.summary == "SA scan complete"
    assert response.model_used == "scanner"
