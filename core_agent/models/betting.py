from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BetRecord(BaseModel):
    id: str
    track: str
    race_number: int = Field(alias="raceNumber")
    horse: str
    odds: float
    edge_percent: float = Field(alias="edgePercent")
    stake: float
    confidence: str
    placed_at: datetime = Field(alias="placedAt")
    settled: bool = False
    won: Optional[bool] = None
    payout: Optional[float] = None
    notes: Optional[str] = None

    class Config:
        populate_by_name = True


class DailyStats(BaseModel):
    date: str
    total_bets: int = Field(alias="totalBets")
    wins: int
    losses: int
    stake_total: float = Field(alias="stakeTotal")
    payout_total: float = Field(alias="payoutTotal")
    roi_percent: float = Field(alias="roiPercent")


class BankrollState(BaseModel):
    balance: float
    daily_limit: float = Field(alias="dailyLimit")
    daily_loss: float = Field(alias="dailyLoss")
    max_stake: float = Field(alias="maxStake")
    total_exposure: float = Field(alias="totalExposure")


class LearningState(BaseModel):
    total_roi: float = Field(alias="totalRoi")
    samples: int
    top_track: str = Field(alias="topTrack")
    accuracy: float