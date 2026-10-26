"""Experiment API router for ORBIT backend."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from ..db.config import get_session
from ..db.models import (
    ExecutionStatus,
    Experiment,
    ExperimentAttempt,
    ExperimentDecision,
    Hypothesis,
    Verdict,
)
from ..schemas.experiments import (
    ChampionResponse,
    ExperimentAttemptListResponse,
    ExperimentAttemptSummary,
    ExperimentCreate,
    ExperimentDecisionDetailResponse,
    ExperimentDecisionSummary,
    ExperimentDetailResponse,
    ExperimentListResponse,
    ExperimentSummary,
)
from ..services.registry import get_champion, promote
from ..services.ws_manager import get_ws_manager

LOG = logging.getLogger("orbit.experiments")

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


def _experiment_to_summary(exp: Experiment) -> ExperimentSummary:
    """Convert Experiment model to summary schema."""
    return ExperimentSummary(
        id=exp.id,
        hypothesis_id=exp.hypothesis_id,
        verdict=exp.verdict,
        execution_status=exp.execution_status,
        metrics=exp.metrics,
        created_at=exp.created_at,
        model=exp.model,
        model_family=exp.model_family,
        feature_set=exp.feature_set,
    )


def _experiment_to_detail(exp: Experiment) -> ExperimentDetailResponse:
    """Convert Experiment model to detail schema."""
    return ExperimentDetailResponse(
        id=exp.id,
        hypothesis_id=exp.hypothesis_id,
        verdict=exp.verdict,
        execution_status=exp.execution_status,
        metrics=exp.metrics,
        created_at=exp.created_at,
        model=exp.model,
        model_family=exp.model_family,
        feature_set=exp.feature_set,
        config_hash=exp.config_hash,
        seed=exp.seed,
        git_commit=exp.git_commit,
        git_dirty=exp.git_dirty,
        dataset_fingerprint=exp.dataset_fingerprint,
        split_fingerprint=exp.split_fingerprint,
        split_version=exp.split_version,
        artifact_path=exp.artifact_path,
        replayable=exp.replayable,
        diagnosis=exp.diagnosis,
        threshold=exp.threshold,
        threshold_source=exp.threshold_source,
        candidate_inclusive_metrics=exp.candidate_inclusive_metrics,
        metrics_detail=exp.metrics_detail,
        training=exp.training,
        split_sizes=exp.split_sizes,
        duration_seconds=exp.duration_seconds,
        config=exp.config,
    )


@router.post("", response_model=ExperimentSummary, status_code=status.HTTP_201_CREATED)
def create_experiment(
    experiment_data: ExperimentCreate,
    session: Session = Depends(get_session),
):
    """Create a new experiment record."""
    # Verify hypothesis exists if provided
    if experiment_data.hypothesis_id:
        hypothesis = session.get(Hypothesis, experiment_data.hypothesis_id)
        if not hypothesis:
            raise HTTPException(status_code=404, detail="Hypothesis not found")

    # Check for duplicate config_hash
    existing = session.exec(
        select(Experiment).where(Experiment.config_hash == experiment_data.config_hash)
    ).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Experiment with config_hash {experiment_data.config_hash} already exists",
        )

    experiment = Experiment(
        id=f"exp_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S_%f')}",
        hypothesis_id=experiment_data.hypothesis_id,
        config_hash=experiment_data.config_hash,
        seed=experiment_data.seed,
        git_commit=experiment_data.git_commit,
        git_dirty=experiment_data.git_dirty,
        dataset_fingerprint=experiment_data.dataset_fingerprint,
        split_fingerprint=experiment_data.split_fingerprint,
        split_version=experiment_data.split_version,
        metrics=experiment_data.metrics,
        artifact_path=experiment_data.artifact_path,
        verdict=Verdict.PENDING,
        replayable=experiment_data.replayable,
        model=experiment_data.model,
        model_family=experiment_data.model_family,
        feature_set=experiment_data.feature_set,
        threshold=experiment_data.threshold,
        threshold_source=experiment_data.threshold_source,
        candidate_inclusive_metrics=experiment_data.candidate_inclusive_metrics,
        metrics_detail=experiment_data.metrics_detail,
        training=experiment_data.training,
        split_sizes=experiment_data.split_sizes,
        duration_seconds=experiment_data.duration_seconds,
        config=experiment_data.config,
        execution_status=ExecutionStatus.COMPLETED,
    )
    session.add(experiment)
    session.commit()
    session.refresh(experiment)
    return _experiment_to_summary(experiment)


@router.get("", response_model=ExperimentListResponse)
def list_experiments(
    hypothesis_id: str | None = Query(None, description="Filter by hypothesis ID"),
    verdict: str | None = Query(
        None, description="Filter by verdict (KEEP, REJECT, PENDING)"
    ),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """List experiments with optional filtering."""
    query = select(Experiment).order_by(Experiment.created_at.desc())

    if hypothesis_id:
        query = query.where(Experiment.hypothesis_id == hypothesis_id)

    if verdict:
        try:
            verdict_enum = Verdict(verdict)
            query = query.where(Experiment.verdict == verdict_enum)
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Invalid verdict: {verdict}"
            ) from None

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    experiments = session.exec(query.offset(offset).limit(limit)).all()

    return ExperimentListResponse(
        items=[_experiment_to_summary(e) for e in experiments],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/champion", response_model=ChampionResponse)
def get_champion_experiment(
    session: Session = Depends(get_session),
):
    """Get the current champion experiment."""
    champion = get_champion(session)
    if not champion:
        raise HTTPException(status_code=404, detail="No champion exists")

    return ChampionResponse(
        id=champion.id,
        metrics=champion.metrics,
        artifact_path=champion.artifact_path,
        created_at=champion.created_at,
        diagnosis=champion.diagnosis,
    )


@router.get("/{experiment_id}", response_model=ExperimentDetailResponse)
def get_experiment(
    experiment_id: str,
    session: Session = Depends(get_session),
):
    """Get an experiment by ID with related attempts and decisions."""
    experiment = session.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Get related attempts
    attempts = session.exec(
        select(ExperimentAttempt).where(
            ExperimentAttempt.experiment_id == experiment_id
        )
    ).all()

    # Get related decisions
    decisions = session.exec(
        select(ExperimentDecision).where(
            ExperimentDecision.challenger_id == experiment_id
        )
    ).all()

    detail = _experiment_to_detail(experiment)
    detail.attempts = [
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
    ]
    detail.decisions = [
        ExperimentDecisionSummary(
            id=d.id,
            challenger_id=d.challenger_id,
            verdict_id=d.verdict_id,
            verdict=d.verdict,
            rationale=d.rationale,
            created_at=d.created_at,
        )
        for d in decisions
    ]
    return detail


@router.get("/{experiment_id}/attempts", response_model=ExperimentAttemptListResponse)
def list_experiment_attempts(
    experiment_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
):
    """List attempts for an experiment."""
    experiment = session.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    query = (
        select(ExperimentAttempt)
        .where(ExperimentAttempt.experiment_id == experiment_id)
        .order_by(ExperimentAttempt.created_at.desc())
    )

    total = session.exec(select(func.count()).select_from(query.subquery())).one()
    attempts = session.exec(query.offset(offset).limit(limit)).all()

    return ExperimentAttemptListResponse(
        items=[
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
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/{experiment_id}/decisions", response_model=list[ExperimentDecisionDetailResponse]
)
def get_experiment_decisions(
    experiment_id: str,
    session: Session = Depends(get_session),
):
    """Get all decisions for an experiment (as challenger and as verdict)."""
    experiment = session.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Decisions where this experiment is the challenger
    challenger_decisions = session.exec(
        select(ExperimentDecision).where(
            ExperimentDecision.challenger_id == experiment_id
        )
    ).all()

    # Decisions where this experiment is the verdict
    verdict_decisions = session.exec(
        select(ExperimentDecision).where(ExperimentDecision.verdict_id == experiment_id)
    ).all()

    all_decisions = list(challenger_decisions) + list(verdict_decisions)

    result = []
    for decision in all_decisions:
        challenger = session.get(Experiment, decision.challenger_id)
        verdict_exp = session.get(Experiment, decision.verdict_id)
        result.append(
            ExperimentDecisionDetailResponse(
                id=decision.id,
                challenger_id=decision.challenger_id,
                verdict_id=decision.verdict_id,
                verdict=decision.verdict,
                rationale=decision.rationale,
                created_at=decision.created_at,
                challenger=_experiment_to_summary(challenger) if challenger else None,
                verdict_experiment=(
                    _experiment_to_summary(verdict_exp) if verdict_exp else None
                ),
            )
        )

    return result


@router.post("/{experiment_id}/promote", response_model=dict)
def promote_experiment(
    experiment_id: str,
    margin: float = Query(0.0, ge=0.0, description="Performance margin required"),
    session: Session = Depends(get_session),
):
    """
    Promote an experiment through the evaluation gate.

    This is the single decision point for champion promotion.
    Returns the verdict and rationale.
    """
    experiment = session.get(Experiment, experiment_id)
    if not experiment:
        raise HTTPException(status_code=404, detail="Experiment not found")

    if experiment.verdict != Verdict.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Experiment is not PENDING: {experiment.verdict.value}",
        )

    verdict, rationale = promote(session, experiment_id, margin)
    session.commit()

    # Broadcast verdict event to WebSocket if mission_id is available
    if experiment.hypothesis_id:
        # Get mission_id from hypothesis
        hypothesis = session.get(Hypothesis, experiment.hypothesis_id)
        if hypothesis and hypothesis.mission_id:
            ws_manager = get_ws_manager()
            try:
                import asyncio

                asyncio.run(
                    ws_manager.broadcast_verdict(
                        mission_id=hypothesis.mission_id,
                        run_id=experiment_id,
                        kept=(verdict == Verdict.KEEP),
                        rationale=rationale,
                    )
                )
            except Exception as e:
                LOG.warning("WebSocket verdict broadcast failed: %s", e)

    return {
        "experiment_id": experiment_id,
        "verdict": verdict.value,
        "rationale": rationale,
    }
