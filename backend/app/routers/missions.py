"""Mission API router for ORBIT backend."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from ..db.config import get_session
from ..db.models import ExperimentAttempt, Hypothesis, Mission, MissionStatus
from ..schemas.experiments import ExperimentAttemptSummary
from ..schemas.hypotheses import HypothesisSummary
from ..schemas.missions import (
    MissionCreate,
    MissionDetailResponse,
    MissionListResponse,
    MissionResponse,
    MissionUpdate,
)

router = APIRouter(prefix="/api/missions", tags=["missions"])


def _mission_to_response(mission: Mission) -> MissionResponse:
    """Convert Mission model to response schema."""
    return MissionResponse(
        id=mission.id,
        question=mission.question,
        budget_rounds=mission.budget_rounds,
        current_round=mission.current_round,
        status=mission.status.value,
        created_at=mission.created_at,
        updated_at=mission.updated_at,
    )


@router.post("", response_model=MissionResponse, status_code=status.HTTP_201_CREATED)
def create_mission(
    mission_data: MissionCreate,
    session: Session = Depends(get_session),
):
    """Create a new mission."""
    mission = Mission(
        id=f"mission_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}",
        question=mission_data.question,
        budget_rounds=mission_data.budget_rounds,
        status=MissionStatus.PENDING,
    )
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return _mission_to_response(mission)


@router.get("", response_model=MissionListResponse)
def list_missions(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """List missions with optional filtering."""
    query = select(Mission).order_by(Mission.created_at.desc())
    if status:
        try:
            mission_status = MissionStatus(status)
            query = query.where(Mission.status == mission_status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status}"
            ) from None

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    missions = session.exec(query.offset(offset).limit(limit)).all()

    return MissionListResponse(
        items=[_mission_to_response(m) for m in missions],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{mission_id}", response_model=MissionDetailResponse)
def get_mission(
    mission_id: str,
    session: Session = Depends(get_session),
):
    """Get a mission by ID with related hypotheses and attempts."""
    mission = session.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    # Get related hypotheses
    hypotheses = session.exec(
        select(Hypothesis).where(Hypothesis.mission_id == mission_id)
    ).all()

    # Get related attempts
    attempts = session.exec(
        select(ExperimentAttempt).where(ExperimentAttempt.mission_id == mission_id)
    ).all()

    response = _mission_to_response(mission)
    detail = MissionDetailResponse(
        **response.model_dump(),
        hypotheses=[
            HypothesisSummary(
                id=h.id,
                mission_id=h.mission_id,
                status=h.status.value,
                created_at=h.created_at,
            )
            for h in hypotheses
        ],
        attempts=[
            ExperimentAttemptSummary(
                id=a.id,
                mission_id=a.mission_id,
                hypothesis_id=a.hypothesis_id,
                experiment_id=a.experiment_id,
                config_path=a.config_path,
                config_hash=a.config_hash,
                execution_status=a.execution_status,
                error_type=a.error_type,
                error_message=a.error_message,
                artifact_path=a.artifact_path,
                duration_seconds=a.duration_seconds,
                created_at=a.created_at,
            )
            for a in attempts
        ],
    )
    return detail


@router.patch("/{mission_id}", response_model=MissionResponse)
def update_mission(
    mission_id: str,
    update_data: MissionUpdate,
    session: Session = Depends(get_session),
):
    """Update a mission's metadata."""
    mission = session.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    if update_data.question is not None:
        mission.question = update_data.question
    if update_data.budget_rounds is not None:
        mission.budget_rounds = update_data.budget_rounds
    if update_data.status is not None:
        try:
            mission.status = MissionStatus(update_data.status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {update_data.status}"
            ) from None

    mission.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
    session.add(mission)
    session.commit()
    session.refresh(mission)
    return _mission_to_response(mission)
