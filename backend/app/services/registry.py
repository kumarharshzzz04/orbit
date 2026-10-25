"""Experiment registry service - persistence and promotion logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session, select

from ..db.models import (
    Experiment,
    ExperimentDecision,
    ExperimentAttempt,
    Verdict,
    ExecutionStatus,
)
from ..db.session import immediate_transaction, get_current_champion


# =============================================================================
# Gate Evaluation
# =============================================================================

@dataclass(frozen=True)
class GateResult:
    """Result of gate evaluation."""
    verdict: Verdict
    rationale: str


# Null champion floor metrics (worst acceptable baseline)
NULL_CHAMPION_F1 = 0.0
NULL_CHAMPION_AUC = 0.5


def _evaluate_gate(
    champion: Optional[Experiment],
    challenger: Experiment,
    margin: float = 0.0,
) -> GateResult:
    """
    Single authoritative gate logic.

    Used by both promote() and bootstrap_champion().
    """
    # Null champion = floor metrics
    if champion is None:
        ch_f1 = NULL_CHAMPION_F1
        ch_auc = NULL_CHAMPION_AUC
        ch_id = "null"
    else:
        ch_f1 = champion.metrics.get("f1", 0.0)
        ch_auc = champion.metrics.get("roc_auc", 0.5)
        ch_id = champion.id

    c_f1 = challenger.metrics.get("f1", 0.0)
    c_auc = challenger.metrics.get("roc_auc", 0.5)

    # Replayability gate (applies to all)
    if not challenger.replayable:
        return GateResult(Verdict.REJECT, "run not replayable")

    # Scientific gate
    better_f1 = c_f1 > ch_f1 + margin
    safe_auc = c_auc >= ch_auc - 1e-9

    if better_f1 and safe_auc:
        return GateResult(
            Verdict.KEEP,
            f"beats champion {ch_id} on F1 ({c_f1:.4f} > {ch_f1:.4f}), AUC not degraded ({c_auc:.4f} >= {ch_auc:.4f})"
        )

    # Diagnosis for rejection
    if not better_f1:
        return GateResult(Verdict.REJECT, f"F1 {c_f1:.4f} does not beat champion {ch_f1:.4f} (margin={margin})")
    return GateResult(Verdict.REJECT, f"AUC {c_auc:.4f} degrades below champion {ch_auc:.4f}")


# =============================================================================
# Registry Operations
# =============================================================================

def insert_experiment(session: Session, run_record: dict) -> Experiment:
    """
    Insert a PENDING experiment from ML sandbox run_record.json.

    This creates the scientific registry record.
    """
    experiment = Experiment(
        id=run_record["id"],
        hypothesis_id=run_record.get("hypothesis_id"),
        config_hash=run_record["config_hash"],
        seed=run_record["seed"],
        git_commit=run_record["git_commit"],
        git_dirty=run_record.get("git_dirty", False),
        dataset_fingerprint=run_record["dataset_fingerprint"],
        split_fingerprint=run_record.get("split_fingerprint"),
        split_version=run_record.get("split_version", "v1"),
        metrics=run_record["metrics"],
        artifact_path=run_record["artifact_path"],
        verdict=Verdict.PENDING,
        diagnosis=run_record.get("diagnosis"),
        created_at=run_record.get("created_at", datetime.now(UTC).isoformat(timespec="seconds")),
        replayable=run_record.get("replayable", False),
        model=run_record.get("model"),
        model_family=run_record.get("model_family"),
        feature_set=run_record.get("feature_set"),
        threshold=run_record.get("threshold"),
        threshold_source=run_record.get("threshold_source"),
        candidate_inclusive_metrics=run_record.get("candidate_inclusive_metrics", {}),
        metrics_detail=run_record.get("metrics_detail", {}),
        training=run_record.get("training", {}),
        split_sizes=run_record.get("split_sizes", {}),
        duration_seconds=run_record.get("duration_seconds", 0.0),
        config=run_record.get("config", {}),
        execution_status=ExecutionStatus.COMPLETED,
    )
    session.add(experiment)
    session.flush()
    return experiment


def _insert_verdict_row(
    session: Session,
    challenger: Experiment,
    result: GateResult,
) -> Experiment:
    """Insert a new KEEP/REJECT verdict row (append-only)."""
    verdict_row = Experiment(
        id=f"{challenger.id}-{result.verdict.value.lower()}",
        hypothesis_id=challenger.hypothesis_id,
        config_hash=challenger.config_hash,
        seed=challenger.seed,
        git_commit=challenger.git_commit,
        git_dirty=challenger.git_dirty,
        dataset_fingerprint=challenger.dataset_fingerprint,
        split_fingerprint=challenger.split_fingerprint,
        split_version=challenger.split_version,
        metrics=challenger.metrics,
        artifact_path=challenger.artifact_path,
        verdict=result.verdict,
        diagnosis=result.rationale if result.verdict == Verdict.REJECT else None,
        created_at=datetime.now(UTC).isoformat(timespec="seconds"),
        replayable=challenger.replayable,
        model=challenger.model,
        model_family=challenger.model_family,
        feature_set=challenger.feature_set,
        threshold=challenger.threshold,
        threshold_source=challenger.threshold_source,
        candidate_inclusive_metrics=challenger.candidate_inclusive_metrics,
        metrics_detail=challenger.metrics_detail,
        training=challenger.training,
        split_sizes=challenger.split_sizes,
        duration_seconds=challenger.duration_seconds,
        config=challenger.config,
        execution_status=ExecutionStatus.COMPLETED,
    )
    session.add(verdict_row)
    session.flush()
    return verdict_row


def _record_decision(
    session: Session,
    challenger: Experiment,
    verdict_row: Experiment,
    result: GateResult,
) -> ExperimentDecision:
    """Record the decision in the append-only decision table."""
    decision = ExperimentDecision(
        id=f"{challenger.id}-{result.verdict.value.lower()}",
        challenger_id=challenger.id,
        verdict_id=verdict_row.id,
        verdict=result.verdict,
        rationale=result.rationale,
    )
    session.add(decision)
    session.flush()
    return decision


def promote(session: Session, challenger_id: str, margin: float = 0.0) -> tuple[Verdict, str]:
    """
    Atomic promotion using BEGIN IMMEDIATE transaction.

    1. Acquire write lock
    2. Re-read champion AND challenger inside transaction
    3. Re-validate challenger is still PENDING
    4. Check if decision already exists
    5. Evaluate gate
    6. Insert verdict row (append-only)
    7. Insert decision record (UNIQUE constraint enforces single decision)
    8. Commit or rollback
    """
    with immediate_transaction(session):
        # 1. Read current champion (highest-F1 KEEP with COMPLETED status)
        champion = get_current_champion(session)

        if champion is None:
            return Verdict.REJECT, "no champion exists; bootstrap required"

        # 2. Read challenger (must be PENDING)
        challenger = session.get(Experiment, challenger_id)
        if challenger is None:
            return Verdict.REJECT, f"challenger {challenger_id} not found"

        if challenger.verdict != Verdict.PENDING:
            return Verdict.REJECT, f"challenger not PENDING: {challenger.verdict.value}"

        # 3. CRITICAL: Check if decision already exists (inside transaction!)
        existing_decision = session.exec(
            select(ExperimentDecision).where(ExperimentDecision.challenger_id == challenger_id)
        ).first()
        if existing_decision:
            return Verdict.REJECT, f"already decided: {existing_decision.verdict.value} ({existing_decision.rationale})"

        # 4. Evaluate gate
        result = _evaluate_gate(champion, challenger, margin)

        # 5. Insert verdict row (append-only)
        verdict_row = _insert_verdict_row(session, challenger, result)

        # 6. Insert decision record (UNIQUE constraint enforces single decision)
        _record_decision(session, challenger, verdict_row, result)

        # Commit happens in context manager
        return result.verdict, result.rationale


def bootstrap_champion(session: Session, run_record: dict) -> Experiment:
    """
    Atomic one-time bootstrap using the SAME gate as promote().

    Evaluates against null champion (F1=0.0, AUC=0.5).
    Fails if any KEEP experiment already exists.
    """
    # Use manual transaction to allow committing REJECT before raising
    session.exec(text("BEGIN IMMEDIATE TRANSACTION"))
    try:
        # Verify no champion exists
        existing = session.exec(
            select(Experiment).where(Experiment.verdict == Verdict.KEEP)
        ).first()
        if existing:
            raise RuntimeError(f"Champion already exists: {existing.id}; use promote()")

        # Verify run_record validity
        if run_record.get("verdict") != Verdict.PENDING.value:
            raise ValueError("Bootstrap requires PENDING run_record")
        if not run_record.get("replayable"):
            raise ValueError("Bootstrap requires replayable run")

        # Insert PENDING row first
        pending = insert_experiment(session, run_record)

        # Evaluate against null champion using SAME gate
        result = _evaluate_gate(None, pending, margin=0.0)

        if result.verdict != Verdict.KEEP:
            # Insert REJECT row and decision (durably record rejection)
            verdict_row = _insert_verdict_row(session, pending, result)
            _record_decision(session, pending, verdict_row, result)
            # Commit the rejection decision before raising
            session.commit()
            raise RuntimeError(f"Bootstrap failed gate: {result.rationale}")

        # Insert KEEP row and decision
        verdict_row = _insert_verdict_row(session, pending, result)
        _record_decision(session, pending, verdict_row, result)

        session.commit()
        return verdict_row
    except Exception:
        session.rollback()
        raise


def get_experiment(session: Session, experiment_id: str) -> Experiment | None:
    """Get experiment by ID."""
    return session.get(Experiment, experiment_id)


def list_experiments(
    session: Session,
    verdict: Verdict | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Experiment]:
    """List experiments with optional filtering."""
    query = select(Experiment).order_by(Experiment.created_at.desc())
    if verdict is not None:
        query = query.where(Experiment.verdict == verdict)
    return list(session.exec(query.offset(offset).limit(limit)).all())


def get_champion(session: Session) -> Experiment | None:
    """Get current champion (highest-F1 KEEP with COMPLETED status)."""
    return get_current_champion(session)


def record_attempt_start(
    session: Session,
    attempt_id: str,
    mission_id: str | None,
    hypothesis_id: str | None,
    config_path: str,
) -> ExperimentAttempt:
    """Record the start of an experiment attempt."""
    attempt = ExperimentAttempt(
        id=attempt_id,
        mission_id=mission_id,
        hypothesis_id=hypothesis_id,
        config_path=config_path,
        execution_status=ExecutionStatus.RUNNING,
    )
    session.add(attempt)
    session.flush()
    return attempt


def record_attempt_completion(
    session: Session,
    attempt_id: str,
    execution_status: ExecutionStatus,
    config_hash: str | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    artifact_path: str | None = None,
    stdout_tail: str | None = None,
    stderr_tail: str | None = None,
    duration_seconds: float = 0.0,
    experiment_id: str | None = None,
) -> ExperimentAttempt:
    """Record the completion of an experiment attempt."""
    attempt = session.get(ExperimentAttempt, attempt_id)
    if not attempt:
        raise ValueError(f"Attempt {attempt_id} not found")

    attempt.execution_status = execution_status
    attempt.config_hash = config_hash
    attempt.error_type = error_type
    attempt.error_message = error_message[:1000] if error_message else None
    attempt.artifact_path = artifact_path
    attempt.stdout_tail = stdout_tail[:500] if stdout_tail else None
    attempt.stderr_tail = stderr_tail[:500] if stderr_tail else None
    attempt.duration_seconds = duration_seconds
    attempt.experiment_id = experiment_id

    session.add(attempt)
    session.flush()
    return attempt


def get_decision(session: Session, challenger_id: str) -> ExperimentDecision | None:
    """Get the decision for a challenger."""
    return session.exec(
        select(ExperimentDecision).where(ExperimentDecision.challenger_id == challenger_id)
    ).first()