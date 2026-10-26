"""Hypothesis API router for ORBIT backend."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from ..db.config import get_session
from ..db.models import Experiment, Hypothesis, HypothesisStatus, Mission
from ..schemas.experiments import ExperimentSummary
from ..schemas.hypotheses import (
    HypothesisCreate,
    HypothesisDetailResponse,
    HypothesisListResponse,
    HypothesisSummary,
    HypothesisUpdate,
)

router = APIRouter(prefix="/api/hypotheses", tags=["hypotheses"])


def _hypothesis_to_summary(hypothesis: Hypothesis) -> HypothesisSummary:
    """Convert Hypothesis model to summary schema."""
    return HypothesisSummary(
        id=hypothesis.id,
        mission_id=hypothesis.mission_id,
        status=hypothesis.status.value,
        created_at=hypothesis.created_at,
    )


@router.post("", response_model=HypothesisSummary, status_code=status.HTTP_201_CREATED)
def create_hypothesis(
    hypothesis_data: HypothesisCreate,
    session: Session = Depends(get_session),
):
    """Create a new hypothesis associated with a mission."""
    # Verify mission exists
    mission = session.get(Mission, hypothesis_data.mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    hypothesis = Hypothesis(
        id=f"hypothesis_{hypothesis_data.mission_id}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}",
        mission_id=hypothesis_data.mission_id,
        proposal_json=json.dumps(hypothesis_data.proposal_json),
        status=HypothesisStatus.PROPOSED,
    )
    session.add(hypothesis)
    session.commit()
    session.refresh(hypothesis)
    return _hypothesis_to_summary(hypothesis)


@router.get("", response_model=HypothesisListResponse)
def list_hypotheses(
    mission_id: str | None = Query(None, description="Filter by mission ID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """List hypotheses with optional filtering."""
    query = select(Hypothesis).order_by(Hypothesis.created_at.desc())

    if mission_id:
        query = query.where(Hypothesis.mission_id == mission_id)

    if status:
        try:
            hypothesis_status = HypothesisStatus(status)
            query = query.where(Hypothesis.status == hypothesis_status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {status}"
            ) from None

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    hypotheses = session.exec(query.offset(offset).limit(limit)).all()

    return HypothesisListResponse(
        items=[_hypothesis_to_summary(h) for h in hypotheses],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{hypothesis_id}", response_model=HypothesisDetailResponse)
def get_hypothesis(
    hypothesis_id: str,
    session: Session = Depends(get_session),
):
    """Get a hypothesis by ID with related experiments."""
    hypothesis = session.get(Hypothesis, hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    # Get related experiments
    experiments = session.exec(
        select(Experiment).where(Experiment.hypothesis_id == hypothesis_id)
    ).all()

    summary = _hypothesis_to_summary(hypothesis)
    proposal = json.loads(hypothesis.proposal_json)

    return HypothesisDetailResponse(
        **summary.model_dump(),
        proposal_json=proposal,
        experiments=[
            ExperimentSummary(
                id=e.id,
                hypothesis_id=e.hypothesis_id,
                verdict=e.verdict,
                execution_status=e.execution_status,
                metrics=e.metrics,
                created_at=e.created_at,
                model=e.model,
                model_family=e.model_family,
                feature_set=e.feature_set,
            )
            for e in experiments
        ],
    )


@router.patch("/{hypothesis_id}", response_model=HypothesisSummary)
def update_hypothesis(
    hypothesis_id: str,
    update_data: HypothesisUpdate,
    session: Session = Depends(get_session),
):
    """Update a hypothesis's metadata."""
    hypothesis = session.get(Hypothesis, hypothesis_id)
    if not hypothesis:
        raise HTTPException(status_code=404, detail="Hypothesis not found")

    if update_data.proposal_json is not None:
        hypothesis.proposal_json = json.dumps(update_data.proposal_json)
    if update_data.status is not None:
        try:
            hypothesis.status = HypothesisStatus(update_data.status)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid status: {update_data.status}"
            ) from None

    session.add(hypothesis)
    session.commit()
    session.refresh(hypothesis)
    return _hypothesis_to_summary(hypothesis)
