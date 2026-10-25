"""SQLModel database models for ORBIT backend."""

import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional, List

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, Index, Relationship, SQLModel, UniqueConstraint


# =============================================================================
# Enums
# =============================================================================

class Verdict(str, Enum):
    """Experiment verdict values."""
    KEEP = "KEEP"
    REJECT = "REJECT"
    PENDING = "PENDING"


class ExecutionStatus(str, Enum):
    """Experiment attempt execution status."""
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionStatus(str, Enum):
    """Mission status values."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HypothesisStatus(str, Enum):
    """Hypothesis status values."""
    PROPOSED = "proposed"
    APPROVED = "approved"
    VETOED = "vetoed"


# =============================================================================
# JSON Field Helpers
# =============================================================================

class JSONField:
    """Helper for JSON columns with proper serialization."""

    @staticmethod
    def default_factory() -> dict:
        return {}

    @staticmethod
    def sa_column():
        return Column(JSON, default={}, nullable=False)


# =============================================================================
# Models
# =============================================================================

class Mission(SQLModel, table=True):
    """Mission - top-level research mission."""

    __tablename__ = "missions"

    id: str = Field(primary_key=True)
    question: str = Field(index=True)
    budget_rounds: int = Field(default=2, ge=1, le=10)
    current_round: int = Field(default=0, ge=0)
    status: MissionStatus = Field(default=MissionStatus.PENDING, index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # Relationships - use strings for forward references
    hypotheses: list["Hypothesis"] = Relationship(back_populates="mission", sa_relationship_kwargs={"lazy": "selectin"})
    attempts: list["ExperimentAttempt"] = Relationship(back_populates="mission", sa_relationship_kwargs={"lazy": "selectin"})
    messages: list["Message"] = Relationship(back_populates="mission", sa_relationship_kwargs={"lazy": "selectin"})

    __table_args__ = (
        Index("ix_missions_status_created", "status", "created_at"),
    )


class Hypothesis(SQLModel, table=True):
    """Hypothesis - proposed change to the current champion."""

    __tablename__ = "hypotheses"

    id: str = Field(primary_key=True)
    mission_id: str = Field(foreign_key="missions.id", index=True)
    proposal_json: str = Field(sa_column=Column(JSON, nullable=False))
    status: HypothesisStatus = Field(default=HypothesisStatus.PROPOSED, index=True)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # Relationships
    mission: "Mission" = Relationship(back_populates="hypotheses")
    experiments: list["Experiment"] = Relationship(back_populates="hypothesis")
    attempts: list["ExperimentAttempt"] = Relationship(back_populates="hypothesis")

    __table_args__ = (
        Index("ix_hypotheses_mission_status", "mission_id", "status"),
    )


class Experiment(SQLModel, table=True):
    """
    Scientific Experiment Registry - append-only record of completed experiments.

    Only scientifically valid, completed runs with genuine provenance are stored here.
    Failed subprocess executions do NOT create experiment records.
    """

    __tablename__ = "experiments"

    # Primary identification
    id: str = Field(primary_key=True)
    hypothesis_id: Optional[str] = Field(default=None, foreign_key="hypotheses.id", index=True)

    # Configuration and provenance
    config_hash: str = Field(index=True)
    seed: int = Field(ge=0)
    git_commit: str
    git_dirty: bool = Field(default=False)
    dataset_fingerprint: str = Field(index=True)
    split_fingerprint: Optional[str] = Field(default=None)
    split_version: str = Field(default="v1")

    # Metrics (primary: CONFIRMED vs FALSE POSITIVE)
    metrics: dict = Field(sa_column=Column(JSON, nullable=False))

    # Artifact and result
    artifact_path: str
    verdict: Verdict = Field(default=Verdict.PENDING, index=True)
    diagnosis: Optional[str] = Field(default=None)

    # Metadata
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    replayable: bool = Field(default=False)

    # Model information
    model: Optional[str] = Field(default=None)
    model_family: Optional[str] = Field(default=None)
    feature_set: Optional[str] = Field(default=None)

    # Training details
    threshold: Optional[float] = Field(default=None)
    threshold_source: Optional[str] = Field(default=None)
    candidate_inclusive_metrics: dict = Field(sa_column=Column(JSON, nullable=False), default_factory=dict)
    metrics_detail: dict = Field(sa_column=Column(JSON, nullable=False), default_factory=dict)
    training: dict = Field(sa_column=Column(JSON, nullable=False), default_factory=dict)
    split_sizes: dict = Field(sa_column=Column(JSON, nullable=False), default_factory=dict)
    duration_seconds: float = Field(default=0.0)
    config: dict = Field(sa_column=Column(JSON, nullable=False), default_factory=dict)

    # Execution status (for completed experiments)
    execution_status: ExecutionStatus = Field(default=ExecutionStatus.COMPLETED, index=True)

    # Relationships
    hypothesis: Optional["Hypothesis"] = Relationship(back_populates="experiments")
    decisions: list["ExperimentDecision"] = Relationship(
        back_populates="challenger",
        sa_relationship_kwargs={"foreign_keys": "ExperimentDecision.challenger_id", "lazy": "selectin"}
    )
    verdict_decisions: list["ExperimentDecision"] = Relationship(
        back_populates="verdict_experiment",
        sa_relationship_kwargs={"foreign_keys": "ExperimentDecision.verdict_id", "lazy": "selectin"}
    )
    attempts: list["ExperimentAttempt"] = Relationship(back_populates="experiment", sa_relationship_kwargs={"lazy": "selectin"})

    __table_args__ = (
        Index("ix_experiments_verdict_created", "verdict", "created_at"),
        Index("ix_experiments_hypothesis", "hypothesis_id"),
        Index("ix_experiments_champion", "verdict", "execution_status"),
    )


class ExperimentDecision(SQLModel, table=True):
    """
    Append-only decision log.

    Each challenger receives at most one final decision.
    Links challenger experiment -> verdict experiment.
    """

    __tablename__ = "experiment_decisions"

    id: str = Field(primary_key=True)
    challenger_id: str = Field(
        foreign_key="experiments.id",
        unique=True,  # ONE decision per challenger
        index=True
    )
    verdict_id: str = Field(
        foreign_key="experiments.id",
        unique=True,  # Each verdict row is the result of one decision
        index=True
    )
    verdict: Verdict = Field(index=True)
    rationale: str
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # Relationships
    challenger: "Experiment" = Relationship(
        back_populates="decisions",
        sa_relationship_kwargs={"foreign_keys": "ExperimentDecision.challenger_id"}
    )
    verdict_experiment: "Experiment" = Relationship(
        back_populates="verdict_decisions",
        sa_relationship_kwargs={"foreign_keys": "ExperimentDecision.verdict_id"}
    )

    __table_args__ = (
        UniqueConstraint("challenger_id", name="uq_decision_per_challenger"),
        UniqueConstraint("verdict_id", name="uq_verdict_per_decision"),
        Index("ix_decisions_verdict_created", "verdict", "created_at"),
    )


class ExperimentAttempt(SQLModel, table=True):
    """
    Execution attempt log.

    One row per subprocess invocation. Includes failed runs.
    Does NOT mix with scientific experiment registry.
    """

    __tablename__ = "experiment_attempts"

    id: str = Field(primary_key=True)
    mission_id: Optional[str] = Field(default=None, foreign_key="missions.id", index=True)
    hypothesis_id: Optional[str] = Field(default=None, foreign_key="hypotheses.id", index=True)
    config_path: str
    config_hash: Optional[str] = Field(default=None)
    execution_status: ExecutionStatus = Field(default=ExecutionStatus.RUNNING, index=True)
    error_type: Optional[str] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    artifact_path: Optional[str] = Field(default=None)
    stdout_tail: Optional[str] = Field(default=None)
    stderr_tail: Optional[str] = Field(default=None)
    duration_seconds: float = Field(default=0.0)
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))
    experiment_id: Optional[str] = Field(default=None, foreign_key="experiments.id", index=True)

    # Relationships
    mission: Optional["Mission"] = Relationship(back_populates="attempts")
    hypothesis: Optional["Hypothesis"] = Relationship(back_populates="attempts")
    experiment: Optional["Experiment"] = Relationship(back_populates="attempts")

    __table_args__ = (
        Index("ix_attempts_mission_created", "mission_id", "created_at"),
        Index("ix_attempts_experiment", "experiment_id"),
        Index("ix_attempts_status", "execution_status"),
    )


class Paper(SQLModel, table=True):
    """Research paper/evidence record."""

    __tablename__ = "papers"

    id: str = Field(primary_key=True)
    title: str = Field(index=True)
    authors: Optional[str] = Field(default=None)
    year: Optional[int] = Field(default=None)
    doi: Optional[str] = Field(default=None)
    abstract: Optional[str] = Field(default=None)
    source: Optional[str] = Field(default=None)
    fetched_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    __table_args__ = (
        Index("ix_papers_fetched", "fetched_at"),
    )


class GraphEdge(SQLModel, table=True):
    """Knowledge graph edge - lightweight relationships."""

    __tablename__ = "graph_edges"

    id: Optional[int] = Field(default=None, primary_key=True)
    src_type: str = Field(index=True)
    src_id: str = Field(index=True)
    rel: str
    dst_type: str = Field(index=True)
    dst_id: str = Field(index=True)

    __table_args__ = (
        Index("ix_graph_src", "src_type", "src_id"),
        Index("ix_graph_dst", "dst_type", "dst_id"),
    )


class Message(SQLModel, table=True):
    """Agent message / transcript record."""

    __tablename__ = "messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    mission_id: str = Field(foreign_key="missions.id", index=True)
    agent: str
    round: int
    type: str
    body: str
    refs_json: Optional[str] = Field(default=None)  # JSON array
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    # Relationships
    mission: "Mission" = Relationship(back_populates="messages")

    __table_args__ = (
        Index("ix_messages_mission_round", "mission_id", "round"),
    )