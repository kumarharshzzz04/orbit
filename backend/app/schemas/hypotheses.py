"""Hypothesis schemas for ORBIT API."""

from typing import Any

from pydantic import BaseModel, Field

from .experiments import ExperimentSummary


class HypothesisCreate(BaseModel):
    mission_id: str
    proposal_json: dict[str, Any]


class HypothesisUpdate(BaseModel):
    proposal_json: dict[str, Any] | None = None
    status: str | None = Field(default=None)


class HypothesisSummary(BaseModel):
    id: str
    mission_id: str
    status: str
    created_at: str


class HypothesisDetailResponse(HypothesisSummary):
    proposal_json: dict[str, Any]
    experiments: list[ExperimentSummary] = []


class HypothesisListResponse(BaseModel):
    items: list[HypothesisSummary]
    total: int
    limit: int
    offset: int
