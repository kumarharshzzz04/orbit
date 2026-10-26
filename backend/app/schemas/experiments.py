"""Experiment schemas for ORBIT API."""

from typing import Any

from pydantic import BaseModel, Field

from .common import ExecutionStatus, Verdict


class ExperimentAttemptSummary(BaseModel):
    id: str
    mission_id: str | None = None
    hypothesis_id: str | None = None
    experiment_id: str | None = None
    config_path: str
    config_hash: str | None = None
    execution_status: ExecutionStatus
    error_type: str | None = None
    error_message: str | None = None
    artifact_path: str | None = None
    duration_seconds: float
    created_at: str


class ExperimentDecisionSummary(BaseModel):
    id: str
    challenger_id: str
    verdict_id: str
    verdict: Verdict
    rationale: str
    created_at: str


class ExperimentCreate(BaseModel):
    hypothesis_id: str | None = None
    config_hash: str
    seed: int = Field(ge=0)
    git_commit: str
    git_dirty: bool = False
    dataset_fingerprint: str
    split_fingerprint: str | None = None
    split_version: str = "v1"
    metrics: dict[str, float]
    artifact_path: str
    replayable: bool = False
    model: str | None = None
    model_family: str | None = None
    feature_set: str | None = None
    threshold: float | None = None
    threshold_source: str | None = None
    candidate_inclusive_metrics: dict[str, float] = {}
    metrics_detail: dict[str, Any] = {}
    training: dict[str, Any] = {}
    split_sizes: dict[str, int] = {}
    duration_seconds: float = 0.0
    config: dict[str, Any] = {}


class ExperimentSummary(BaseModel):
    id: str
    hypothesis_id: str | None = None
    verdict: Verdict
    execution_status: ExecutionStatus
    metrics: dict[str, float]
    created_at: str
    model: str | None = None
    model_family: str | None = None
    feature_set: str | None = None


class ExperimentDetailResponse(ExperimentSummary):
    config_hash: str
    seed: int
    git_commit: str
    git_dirty: bool
    dataset_fingerprint: str
    split_fingerprint: str | None = None
    split_version: str
    artifact_path: str
    replayable: bool
    diagnosis: str | None = None
    threshold: float | None = None
    threshold_source: str | None = None
    candidate_inclusive_metrics: dict[str, float] = {}
    metrics_detail: dict[str, Any] = {}
    training: dict[str, Any] = {}
    split_sizes: dict[str, int] = {}
    duration_seconds: float
    config: dict[str, Any] = {}
    attempts: list[ExperimentAttemptSummary] = []
    decisions: list[ExperimentDecisionSummary] = []


class ExperimentListResponse(BaseModel):
    items: list[ExperimentSummary]
    total: int
    limit: int
    offset: int


class ExperimentAttemptSummary(BaseModel):
    id: str
    mission_id: str | None = None
    hypothesis_id: str | None = None
    experiment_id: str | None = None
    config_path: str
    config_hash: str | None = None
    execution_status: ExecutionStatus
    error_type: str | None = None
    error_message: str | None = None
    artifact_path: str | None = None
    duration_seconds: float
    created_at: str


class ExperimentAttemptDetailResponse(ExperimentAttemptSummary):
    stdout_tail: str | None = None
    stderr_tail: str | None = None


class ExperimentAttemptListResponse(BaseModel):
    items: list[ExperimentAttemptSummary]
    total: int
    limit: int
    offset: int


class ExperimentDecisionSummary(BaseModel):
    id: str
    challenger_id: str
    verdict_id: str
    verdict: Verdict
    rationale: str
    created_at: str


class ExperimentDecisionDetailResponse(ExperimentDecisionSummary):
    challenger: ExperimentSummary | None = None
    verdict_experiment: ExperimentSummary | None = None


class ChampionResponse(BaseModel):
    id: str
    metrics: dict[str, float]
    artifact_path: str
    created_at: str
    diagnosis: str | None = None
