from pydantic import BaseModel, Field
from typing import List, Optional

class Runner(BaseModel):
    name: str
    odds: float | str = Field(..., description="Decimal odds or 'SP' if pending")
    form: str = ""
    edge: Optional[float] = None
    win_probability: Optional[float] = Field(None, alias="winProbability")
    implied_probability: Optional[float] = Field(None, alias="impliedProbability")
    jockey_name: str = Field("TBA", alias="jockeyName")
    trainer_name: str = Field("TBA", alias="trainerName")
    age: str = "Unknown"
    weight: str = "0"
    number: str = "0"
    star_rating: int = Field(0, alias="starRating")
    draw: int = 0
    time_form: str = Field("", alias="timeForm")
    outcome_name: str = Field("", alias="outcomeName")
    outcome_id: str = Field("", alias="outcomeId")

    class Config:
        populate_by_name = True

class RaceEvent(BaseModel):
    id: str
    en: str
    course: str
    t: str
    st: str
    is_finished: bool = Field(False, alias="isFinished")
    race_number: str = Field("1", alias="raceNumber")
    runners: List[Runner]
    complexity: str = "EVALUATING"
    prediction_confidence: Optional[float] = Field(None, alias="predictionConfidence")

    class Config:
        populate_by_name = True
