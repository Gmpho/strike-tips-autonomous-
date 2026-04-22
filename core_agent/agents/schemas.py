from __future__ import annotations
from typing import Literal, Optional, Union
from pydantic import BaseModel, Field


class RunnerEdge(BaseModel):
    name: str
    odds: float
    edge: float
    confidence: Literal["STRONG_VALUE", "VALUE", "MARGINAL", "NO_VALUE"]


class RaceAnalysis(BaseModel):
    track: str
    race_number: int
    runners: list[RunnerEdge] = Field(default_factory=list)
    recommended: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    analysis_depth: Literal["shallow", "deep"] = "shallow"
    include_past_history: bool = False


class BetDecision(BaseModel):
    action: Literal["RECORD", "REJECT"]
    track: str
    race_number: int
    horse: str
    stake: float = 0.0
    reason: str


class AccountSummary(BaseModel):
    balance: float
    pnl: float
    open_bets: int


class IntentResponse(BaseModel):
    intent: str
    confidence: float = 1.0


class AgentReply(BaseModel):
    summary: str
    model_used: str = "unknown"
    data: Optional[Union[RaceAnalysis, BetDecision, AccountSummary]] = None
    token_usage: Optional[dict] = None  # {input, output, total}
