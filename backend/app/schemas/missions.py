"""Mission schemas for ORBIT API."""

from pydantic import BaseModel, Field

from .experiments import ExperimentAttemptSummary
from .hypotheses import HypothesisSummary


class MissionCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    budget_rounds: int = Field(default=2, ge=1, le=10)


class MissionUpdate(BaseModel):
    question: str | None = Field(default=None, min_length=1, max_length=1000)
    budget_rounds: int | None = Field(default=None, ge=1, le=10)
    status: str | None = Field(default=None)


class MissionResponse(BaseModel):
    id: str
    question: str
    budget_rounds: int
    current_round: int
    status: str
    created_at: str
    updated_at: str


class MissionDetailResponse(MissionResponse):
    hypotheses: list[HypothesisSummary] = []
    attempts: list[ExperimentAttemptSummary] = []


class MissionListResponse(BaseModel):
    items: list[MissionResponse]
    total: int
    limit: int
    offset: int
