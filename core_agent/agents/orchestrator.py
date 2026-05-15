"""
Orchestrator — the single public API for all agent interactions.
Handles instant responses, bankroll shortcuts, and delegates to pipeline.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core_agent.agents import pipeline
from core_agent.agents.schemas import AgentReply

logger = logging.getLogger("orchestrator")


@dataclass
class AgentResponse:
    """Public response contract — unchanged for backward compatibility."""
    summary: str
    model_used: str = "unknown"
    confidence: float = 0.8
    tool_calls: List[Dict] = field(default_factory=list)
    raw_output: Optional[str] = None
    suggested_action: Optional[str] = None
    token_usage: Optional[Dict] = None

    @property
    def success(self) -> bool:
        return self.confidence > 0.0


def _reply_to_response(reply: AgentReply) -> AgentResponse:
    return AgentResponse(
        summary=reply.summary,
        model_used=reply.model_used,
        confidence=0.85 if reply.model_used != "unavailable" else 0.0,
        token_usage=reply.token_usage,
    )


class UnifiedOrchestrator:
    """
    Public API for the agent system.
    Signature unchanged — all existing callers work without modification.
    """

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self._history: List[Dict] = []

    async def chat(
        self, message: str, model_override: Optional[str] = None
    ) -> AgentResponse:
        msg_lower = message.lower().strip()

        # Instant handlers — no LLM needed
        if msg_lower in ("hi", "hello", "hey"):
            return AgentResponse(
                summary="🏇 Strike Tips AI ready. Ask me about race cards, value bets, or your bankroll.",
                model_used="intent_handler",
                confidence=1.0,
            )

        if self.strike and any(
            kw in msg_lower
            for kw in ("status", "balance", "bankroll", "how much", "my account", "my balance")
        ):
            try:
                s = self.strike.get_bankroll_status()
                return AgentResponse(
                    summary=f"💰 Bankroll: R{s['current_bankroll']:.2f} | P&L: R{s['total_profit_loss']:.2f} | Open: {s['open_bets']}",
                    model_used="intent_handler",
                    confidence=1.0,
                )
            except Exception:
                pass

        # Delegate to pipeline
        reply = await pipeline.run(message, model_override=model_override)

        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": reply.summary})
        self._history = self._history[-20:]

        return _reply_to_response(reply)

    def clear_history(self) -> None:
        self._history = []
