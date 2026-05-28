from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.agents.ai_pydantic import (
    ModelPipeline,
    UnifiedOrchestrator,
    build_unsupported_track_response,
)
from core_agent.agents.schemas import AgentReply


@pytest.mark.asyncio
async def test_chat_cold_start_delegates_to_pipeline():
    pipeline = ModelPipeline(strike_tips=object())

    with patch("core_agent.agents.pipeline.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AgentReply(summary="ok", model_used="groq:llama-3.1-8b-instant")
        response = await pipeline.chat("please analyze this race")

    mock_run.assert_awaited_once()
    assert response.summary == "ok"
    assert response.model_used == "groq:llama-3.1-8b-instant"


@pytest.mark.asyncio
async def test_orchestrator_returns_greeting_for_hello():
    orchestrator = UnifiedOrchestrator(strike_tips=None)
    response = await orchestrator.chat("hello")
    assert "Strike Tips" in response.summary
    assert response.model_used == "intent_handler"
    assert response.confidence == 1.0


@pytest.mark.asyncio
async def test_orchestrator_returns_bankroll_for_account_query():
    mock_strike = MagicMock()
    mock_strike.get_bankroll_status.return_value = {
        "current_bankroll": 1000.0, "total_profit_loss": 0.0, "open_bets": 0,
    }
    orchestrator = UnifiedOrchestrator(strike_tips=mock_strike)
    response = await orchestrator.chat("Show me my balance")
    assert response.model_used == "intent_handler"
    assert response.confidence == 1.0
    assert "1000" in response.summary


@pytest.mark.asyncio
async def test_orchestrator_sa_query_routes_to_pipeline():
    orchestrator = UnifiedOrchestrator(strike_tips=None)

    with patch("core_agent.agents.pipeline.run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = AgentReply(summary="SA scan complete", model_used="groq:llama-3.1-8b-instant")
        response = await orchestrator.chat("Please scan Vaal races today")

    mock_run.assert_awaited_once()
    assert response.summary == "SA scan complete"


def test_build_unsupported_track_response_from_alias_is_deterministic():
    response = build_unsupported_track_response("Please scan SOUTHWELL race 2")
    assert response is not None
    assert "can't scan Southwell" in response
    assert "Vaal, Turffontein, Kenilworth" in response


def test_build_unsupported_track_response_supported_track_returns_none():
    response = build_unsupported_track_response("Please scan vaal race 1")
    assert response is None
