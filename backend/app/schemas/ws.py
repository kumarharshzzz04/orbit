"""WebSocket event schemas for ORBIT API."""

from typing import Any, Literal

from pydantic import BaseModel


class AgentMessagePayload(BaseModel):
    agent: str
    round: int
    type: str
    body: str
    refs: list[str] = []


class RunProgressPayload(BaseModel):
    run_id: str
    stage: str
    percent: float


class RunMetricsPayload(BaseModel):
    run_id: str
    metrics: dict[str, float]


class VerdictPayload(BaseModel):
    run_id: str
    kept: bool
    rationale: str


class SystemPayload(BaseModel):
    level: str
    text: str


class WSEvent(BaseModel):
    event: Literal["agent_message", "run_progress", "run_metrics", "verdict", "system"]
    mission_id: str
    payload: dict[str, Any]


# Union type for validated payloads
WSMessagePayload = (
    AgentMessagePayload
    | RunProgressPayload
    | RunMetricsPayload
    | VerdictPayload
    | SystemPayload
)
