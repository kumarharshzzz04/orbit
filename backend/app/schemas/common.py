"""Common Pydantic schemas for ORBIT API."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    KEEP = "KEEP"
    REJECT = "REJECT"
    PENDING = "PENDING"


class ExecutionStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class MissionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    VETOED = "vetoed"


class WSMessageType(str, Enum):
    AGENT_MESSAGE = "agent_message"
    RUN_PROGRESS = "run_progress"
    RUN_METRICS = "run_metrics"
    VERDICT = "verdict"
    SYSTEM = "system"


class AgentType(str, Enum):
    RESEARCHER = "researcher"
    HYPOTHESIZER = "hypothesizer"
    SKEPTIC = "skeptic"
    EXPERIMENTER = "experimenter"
    EVALUATOR = "evaluator"
    ORCHESTRATOR = "orchestrator"


class AgentMessageType(str, Enum):
    EVIDENCE_CARD = "evidence_card"
    PROPOSAL = "proposal"
    CRITIQUE = "critique"
    RUN_RECORD = "run_record"
    VERDICT = "verdict"
    STATUS = "status"


class SystemLevel(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel):
    items: list[Any]
    total: int
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    detail: str
    code: str | None = None


class HealthResponse(BaseModel):
    status: str
    database: str
    ml_sandbox: str
    timestamp: str
