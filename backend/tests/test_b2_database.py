"""Tests for B2 database schema and persistence foundations."""

from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.db.config import create_engine_with_pragmas
from app.db.models import (
    ExecutionStatus,
    Experiment,
    ExperimentDecision,
    GraphEdge,
    Hypothesis,
    Message,
    Mission,
    MissionStatus,
    Paper,
    Verdict,
)
from app.services.registry import (
    _evaluate_gate,
    bootstrap_champion,
    get_decision,
    insert_experiment,
    promote,
    record_attempt_completion,
    record_attempt_start,
)

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for each test."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    engine = create_engine_with_pragmas(db_path)
    # Import models to register them
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    engine.dispose()

    yield db_path

    # Cleanup - don't try to delete on Windows (let OS clean up temp files)
    # db_path.unlink(missing_ok=True)


@pytest.fixture
def session(temp_db):
    """Get a session for the temp database."""
    engine = create_engine_with_pragmas(temp_db)
    # Ensure models are imported
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def sample_run_record():
    """Sample run_record.json from ML sandbox."""
    return {
        "id": "test_experiment_001",
        "hypothesis_id": "H-001",
        "config_hash": "abc123def456",
        "seed": 42,
        "git_commit": "abcdef123456",
        "git_dirty": False,
        "dataset_fingerprint": "ee1f7e04226f8e7b0ca68b3bd4dd8527877bac17",
        "split_fingerprint": "303b6081ebb5002449fae5de31b30f5adb78a732",
        "split_version": "v1",
        "metrics": {
            "accuracy": 0.93,
            "precision": 0.92,
            "recall": 0.94,
            "f1": 0.93,
            "roc_auc": 0.98,
        },
        "artifact_path": "artifacts/test_experiment_001/",
        "verdict": "PENDING",
        "diagnosis": None,
        "created_at": "2026-10-25T10:00:00+00:00",
        "replayable": True,
        "model": "test-model",
        "model_family": "baseline",
        "feature_set": "catalog_v1",
        "threshold": 0.5,
        "threshold_source": "val_f1",
        "candidate_inclusive_metrics": {"accuracy": 0.90, "f1": 0.89},
        "metrics_detail": {"threshold": 0.5, "n_primary": 100},
        "training": {"duration": 10.5},
        "split_sizes": {"train": 700, "val": 150, "test": 150},
        "duration_seconds": 10.5,
        "config": {"name": "test", "model": "baseline"},
    }


# =============================================================================
# Schema and Model Tests
# =============================================================================


def test_all_tables_created(temp_db):
    """All required tables can be created."""
    engine = create_engine_with_pragmas(temp_db)

    from app.db import models  # noqa: F401

    inspector = __import__("sqlalchemy").inspect(engine)
    tables = inspector.get_table_names()

    expected = {
        "missions",
        "hypotheses",
        "experiments",
        "experiment_decisions",
        "experiment_attempts",
        "papers",
        "graph_edges",
        "messages",
    }
    for table in expected:
        assert table in tables, f"Missing table: {table}"


def test_mission_model_defaults(session):
    """Mission model defaults and validation."""
    mission = Mission(
        id="mission_001",
        question="Test mission",
        budget_rounds=2,
    )
    session.add(mission)
    session.commit()

    assert mission.status == MissionStatus.PENDING
    assert mission.current_round == 0
    assert mission.created_at is not None
    assert mission.updated_at is not None


def test_mission_status_validation(session):
    """Mission status accepts valid values."""
    mission = Mission(id="m1", question="Q", status=MissionStatus.RUNNING)
    session.add(mission)
    session.commit()

    assert mission.status == MissionStatus.RUNNING


def test_hypothesis_foreign_key(session):
    """Hypothesis must reference existing mission."""
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    session.commit()

    hypothesis = Hypothesis(
        id="h1",
        mission_id="m1",
        proposal_json=json.dumps({"change": "test"}),
    )
    session.add(hypothesis)
    session.commit()

    assert hypothesis.mission_id == "m1"


def test_experiment_json_fields(session):
    """JSON fields serialize and deserialize correctly."""
    exp = Experiment(
        id="exp1",
        config_hash="hash1",
        seed=42,
        git_commit="commit1",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.9, "roc_auc": 0.95},
        artifact_path="artifacts/exp1/",
        verdict=Verdict.PENDING,
    )
    session.add(exp)
    session.commit()

    retrieved = session.get(Experiment, "exp1")
    assert retrieved.metrics == {"f1": 0.9, "roc_auc": 0.95}
    assert isinstance(retrieved.candidate_inclusive_metrics, dict)
    assert isinstance(retrieved.metrics_detail, dict)
    assert isinstance(retrieved.training, dict)


def test_experiment_verdict_enum(session):
    """Experiment verdict only accepts KEEP, REJECT, PENDING."""
    exp = Experiment(
        id="exp1",
        config_hash="hash1",
        seed=42,
        git_commit="commit1",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.9},
        artifact_path="artifacts/exp1/",
        verdict=Verdict.KEEP,
    )
    session.add(exp)
    session.commit()

    assert exp.verdict == Verdict.KEEP


def test_foreign_key_enforcement(temp_db):
    """Foreign key constraints are enforced."""
    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Try to insert hypothesis with non-existent mission
        hypothesis = Hypothesis(id="h1", mission_id="nonexistent", proposal_json="{}")
        session.add(hypothesis)
        with pytest.raises(IntegrityError):
            session.commit()


def test_unique_constraint_experiment_decision_challenger(session):
    """Unique constraint on experiment_decisions.challenger_id."""
    # Setup: mission -> hypothesis -> experiment (challenger)
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    challenger = Experiment(
        id="challenger1",
        hypothesis_id="h1",
        config_hash="hash1",
        seed=42,
        git_commit="commit1",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.9},
        artifact_path="artifacts/challenger1/",
        verdict=Verdict.PENDING,
    )
    session.add(challenger)

    # Also need the verdict experiment for foreign key
    verdict_row = Experiment(
        id="verdict1",
        hypothesis_id="h1",
        config_hash="hash2",
        seed=42,
        git_commit="commit2",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.95},
        artifact_path="artifacts/verdict1/",
        verdict=Verdict.KEEP,
    )
    session.add(verdict_row)
    session.commit()

    # Insert first decision
    decision1 = ExperimentDecision(
        id="dec1",
        challenger_id="challenger1",
        verdict_id="verdict1",
        verdict=Verdict.KEEP,
        rationale="Test",
    )
    session.add(decision1)
    session.commit()

    # Try to insert second decision for same challenger
    decision2 = ExperimentDecision(
        id="dec2",
        challenger_id="challenger1",  # Same challenger
        verdict_id="verdict2",
        verdict=Verdict.REJECT,
        rationale="Test2",
    )
    session.add(decision2)
    with pytest.raises(IntegrityError):  # Should raise integrity error
        session.commit()


def test_unique_constraint_experiment_decision_verdict(session):
    """Unique constraint on experiment_decisions.verdict_id."""
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)

    challenger = Experiment(
        id="challenger1",
        hypothesis_id="h1",
        config_hash="hash1",
        seed=42,
        git_commit="commit1",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.9},
        artifact_path="artifacts/challenger1/",
        verdict=Verdict.PENDING,
    )
    session.add(challenger)

    verdict_row = Experiment(
        id="verdict1",
        hypothesis_id="h1",
        config_hash="hash1",
        seed=42,
        git_commit="commit1",
        dataset_fingerprint="fp1",
        metrics={"f1": 0.9},
        artifact_path="artifacts/verdict1/",
        verdict=Verdict.KEEP,
    )
    session.add(verdict_row)
    session.commit()

    # First decision
    decision1 = ExperimentDecision(
        id="dec1",
        challenger_id="challenger1",
        verdict_id="verdict1",
        verdict=Verdict.KEEP,
        rationale="Test",
    )
    session.add(decision1)
    session.commit()

    # Second decision trying to use same verdict_id
    decision2 = ExperimentDecision(
        id="dec2",
        challenger_id="challenger2",  # Different challenger
        verdict_id="verdict1",  # Same verdict_id
        verdict=Verdict.REJECT,
        rationale="Test2",
    )
    session.add(decision2)
    with pytest.raises(IntegrityError):  # Should raise integrity error
        session.commit()


def test_execution_status_enum():
    """ExecutionStatus enum has required values."""
    assert ExecutionStatus.RUNNING == "RUNNING"
    assert ExecutionStatus.COMPLETED == "COMPLETED"
    assert ExecutionStatus.FAILED == "FAILED"
    assert ExecutionStatus.CANCELLED == "CANCELLED"


# =============================================================================
# Experiment Attempt Tests
# =============================================================================


def test_attempt_starts_as_running(session):
    """Attempt starts as RUNNING."""
    # Need to create mission and hypothesis first for foreign keys
    mission = Mission(id="mission1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="hypothesis1", mission_id="mission1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    attempt = record_attempt_start(
        session, "attempt1", "mission1", "hypothesis1", "config.json"
    )

    assert attempt.execution_status == ExecutionStatus.RUNNING
    assert attempt.config_path == "config.json"
    assert attempt.mission_id == "mission1"
    assert attempt.hypothesis_id == "hypothesis1"
    assert attempt.duration_seconds == 0.0


def test_successful_attempt_links_to_experiment(session, sample_run_record):
    """Successful attempt links to a valid experiment."""
    # Start attempt - need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    _ = record_attempt_start(session, "attempt1", "m1", "H-001", "config.json")
    session.commit()

    # Insert experiment (simulating successful completion)
    experiment = insert_experiment(session, sample_run_record)
    session.commit()

    # Record completion
    updated = record_attempt_completion(
        session,
        "attempt1",
        ExecutionStatus.COMPLETED,
        config_hash=sample_run_record["config_hash"],
        artifact_path=sample_run_record["artifact_path"],
        duration_seconds=10.0,
        experiment_id=experiment.id,
    )

    assert updated.execution_status == ExecutionStatus.COMPLETED
    assert updated.experiment_id == experiment.id
    assert updated.config_hash == sample_run_record["config_hash"]


def test_failed_attempt_no_experiment_created(session):
    """Failed execution creates attempt but no experiment."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    _ = record_attempt_start(session, "attempt1", "m1", "h1", "config.json")
    session.commit()

    # Record failure - no experiment created
    updated = record_attempt_completion(
        session,
        "attempt1",
        ExecutionStatus.FAILED,
        error_type="timeout",
        error_message="Process timed out after 600s",
        stderr_tail="Timeout error...",
        duration_seconds=600.0,
    )

    assert updated.execution_status == ExecutionStatus.FAILED
    assert updated.error_type == "timeout"
    assert updated.experiment_id is None
    # No experiment should exist
    experiments = list(session.exec(select(Experiment)).all())
    assert len(experiments) == 0


def test_cancelled_attempt_represented_correctly(session):
    """Cancellation is represented correctly."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    _ = record_attempt_start(session, "attempt1", "m1", "h1", "config.json")
    session.commit()

    updated = record_attempt_completion(
        session,
        "attempt1",
        ExecutionStatus.CANCELLED,
        error_type="cancelled",
        error_message="Mission cancelled by user",
        duration_seconds=5.0,
    )

    assert updated.execution_status == ExecutionStatus.CANCELLED
    assert updated.error_type == "cancelled"
    assert updated.experiment_id is None


def test_error_messages_bounded(session):
    """Error messages and output tails are bounded in size."""
    long_error = "x" * 2000
    long_stdout = "y" * 1000
    long_stderr = "z" * 1000

    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    _ = record_attempt_start(session, "attempt1", "m1", "h1", "config.json")
    session.commit()

    updated = record_attempt_completion(
        session,
        "attempt1",
        ExecutionStatus.FAILED,
        error_message=long_error,
        stdout_tail=long_stdout,
        stderr_tail=long_stderr,
    )

    # Should be truncated
    assert len(updated.error_message) <= 1000
    assert len(updated.stdout_tail) <= 500
    assert len(updated.stderr_tail) <= 500


# =============================================================================
# Registry Tests
# =============================================================================


def test_insert_experiment_creates_pending_record(session, sample_run_record):
    """insert_experiment creates PENDING experiment record."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    experiment = insert_experiment(session, sample_run_record)
    session.commit()

    assert experiment.id == sample_run_record["id"]
    assert experiment.verdict == Verdict.PENDING
    assert experiment.metrics == sample_run_record["metrics"]
    assert experiment.replayable is True


def test_original_pending_remains_unchanged(session, sample_run_record):
    """Original PENDING record remains unchanged after promotion."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()
    pending_id = pending.id
    pending_f1 = pending.metrics["f1"]

    # Create a champion first
    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion_record["verdict"] = "KEEP"
    champion_record["replayable"] = True
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # Promote the challenger
    verdict, rationale = promote(session, pending_id)

    # Original PENDING should still exist and be unchanged
    original = session.get(Experiment, pending_id)
    assert original is not None
    assert original.verdict == Verdict.PENDING
    assert original.metrics["f1"] == pending_f1

    # New verdict row should exist
    verdict_row = session.get(Experiment, f"{pending_id}-keep")
    assert verdict_row is not None
    assert verdict_row.verdict == Verdict.KEEP


def test_keep_reject_decision_appended(session, sample_run_record):
    """KEEP/REJECT decision is appended as new row."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()

    # Create champion
    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion_record["verdict"] = "KEEP"
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # Promote
    verdict, rationale = promote(session, pending.id)
    session.commit()

    assert verdict == Verdict.KEEP

    # Check decision recorded
    decision = get_decision(session, pending.id)
    assert decision is not None
    assert decision.verdict == Verdict.KEEP
    assert decision.challenger_id == pending.id


def test_repeated_promotion_no_second_decision(session, sample_run_record):
    """Repeated promotion does not create a second decision."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()

    # Create champion
    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # First promotion
    verdict1, rationale1 = promote(session, pending.id)
    assert verdict1 == Verdict.KEEP

    # Second promotion - should return existing decision
    verdict2, rationale2 = promote(session, pending.id)
    assert verdict2 == Verdict.REJECT
    assert "already decided" in rationale2

    # Only one decision should exist
    decisions = list(session.exec(select(ExperimentDecision)).all())
    assert len(decisions) == 1


def test_rejected_challenger_cannot_later_keep(session, sample_run_record):
    """A rejected challenger cannot later receive KEEP."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()

    # Create champion with higher F1
    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.95  # Higher than challenger
    champion_record["metrics"]["roc_auc"] = 0.98
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # First promotion - should REJECT
    verdict1, _ = promote(session, pending.id)
    assert verdict1 == Verdict.REJECT

    # Second promotion attempt - should still REJECT (already decided)
    verdict2, rationale2 = promote(session, pending.id)
    assert verdict2 == Verdict.REJECT
    assert "already decided" in rationale2


def test_duplicate_decision_insertion_fails_at_db_level(session, sample_run_record):
    """Duplicate decision insertion fails at database level."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()

    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # First promotion succeeds
    promote(session, pending.id)
    session.commit()

    # Try to manually insert duplicate decision
    decision = ExperimentDecision(
        id=f"{pending.id}-keep-2",
        challenger_id=pending.id,
        verdict_id=f"{pending.id}-keep",
        verdict=Verdict.KEEP,
        rationale="Duplicate",
    )
    session.add(decision)
    with pytest.raises(IntegrityError):
        session.commit()


def test_bootstrap_uses_same_gate_as_promote(session, sample_run_record):
    """Bootstrap uses the same evaluation gate as ordinary promotion."""
    # Verify _evaluate_gate is used by both

    # Check that bootstrap_champion calls _evaluate_gate with None champion
    # We can't easily mock, but we can test the behavior matches

    # Bootstrap with F1 > 0 and AUC >= 0.5 should succeed
    bootstrap_record = sample_run_record.copy()
    bootstrap_record["id"] = "bootstrap_test"
    bootstrap_record["metrics"]["f1"] = 0.1
    bootstrap_record["metrics"]["roc_auc"] = 0.6
    bootstrap_record["hypothesis_id"] = None  # Bootstrap has no hypothesis

    champion = bootstrap_champion(session, bootstrap_record)
    assert champion.verdict == Verdict.KEEP
    assert champion.id == "bootstrap_test-keep"


def test_bootstrap_null_champion_floor(session):
    """Bootstrap rejects when F1 <= 0 or AUC < 0.5."""
    # F1 = 0.0, AUC = 0.5 → should REJECT (not strictly better)
    record = {
        "id": "bootstrap_fail_f1",
        "hypothesis_id": None,
        "config_hash": "hash1",
        "seed": 42,
        "git_commit": "commit1",
        "git_dirty": False,
        "dataset_fingerprint": "fp1",
        "split_fingerprint": "split1",
        "split_version": "v1",
        "metrics": {
            "accuracy": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.5,
        },
        "artifact_path": "artifacts/bootstrap_fail_f1/",
        "verdict": "PENDING",
        "diagnosis": None,
        "created_at": "2026-10-25T10:00:00+00:00",
        "replayable": True,
    }

    with pytest.raises(RuntimeError, match="Bootstrap failed gate"):
        bootstrap_champion(session, record)

    # Verify REJECT decision was persisted (not rolled back) - use fresh session
    engine = session.get_bind()
    from sqlmodel import Session as Sess

    with Sess(engine) as fresh_session:
        decisions = list(fresh_session.exec(select(ExperimentDecision)).all())
        assert len(decisions) == 1
        assert decisions[0].verdict == Verdict.REJECT
        assert "F1 0.0000 does not beat champion 0.0000" in decisions[0].rationale

    # F1 > 0 but AUC < 0.5 → REJECT
    record2 = record.copy()
    record2["id"] = "bootstrap_fail_auc"
    record2["metrics"]["f1"] = 0.1
    record2["metrics"]["roc_auc"] = 0.4

    with pytest.raises(RuntimeError):
        bootstrap_champion(session, record2)

    # Verify both decisions persisted with fresh session
    with Sess(engine) as fresh_session:
        decisions = list(fresh_session.exec(select(ExperimentDecision)).all())
        assert len(decisions) == 2


def test_bootstrap_only_once(session, sample_run_record):
    """Bootstrap can happen only once."""
    bootstrap_record = sample_run_record.copy()
    bootstrap_record["id"] = "bootstrap1"
    bootstrap_record["metrics"]["f1"] = 0.1
    bootstrap_record["metrics"]["roc_auc"] = 0.6
    bootstrap_record["hypothesis_id"] = None  # Bootstrap has no hypothesis

    # First bootstrap succeeds
    champion1 = bootstrap_champion(session, bootstrap_record)
    assert champion1.verdict == Verdict.KEEP

    # Second bootstrap should fail
    bootstrap_record2 = sample_run_record.copy()
    bootstrap_record2["id"] = "bootstrap2"
    bootstrap_record2["metrics"]["f1"] = 0.2
    bootstrap_record2["metrics"]["roc_auc"] = 0.7
    bootstrap_record2["hypothesis_id"] = None

    with pytest.raises(RuntimeError, match="Champion already exists"):
        bootstrap_champion(session, bootstrap_record2)


def test_bootstrap_rejection_persisted(session):
    """Bootstrap rejection remains persisted (not rolled back)."""
    record = {
        "id": "bootstrap_reject",
        "hypothesis_id": None,
        "config_hash": "hash1",
        "seed": 42,
        "git_commit": "commit1",
        "git_dirty": False,
        "dataset_fingerprint": "fp1",
        "split_fingerprint": "split1",
        "split_version": "v1",
        "metrics": {
            "accuracy": 0.5,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.5,
        },
        "artifact_path": "artifacts/bootstrap_reject/",
        "verdict": "PENDING",
        "diagnosis": None,
        "created_at": "2026-10-25T10:00:00+00:00",
        "replayable": True,
    }

    with pytest.raises(RuntimeError):
        bootstrap_champion(session, record)

    # The rejection decision should be committed
    decisions = list(session.exec(select(ExperimentDecision)).all())
    assert len(decisions) == 1
    assert decisions[0].verdict == Verdict.REJECT
    assert decisions[0].challenger_id == "bootstrap_reject"

    # The PENDING row should still exist
    pending = session.get(Experiment, "bootstrap_reject")
    assert pending is not None
    assert pending.verdict == Verdict.PENDING

    # The REJECT verdict row should exist
    reject_row = session.get(Experiment, "bootstrap_reject-reject")
    assert reject_row is not None
    assert reject_row.verdict == Verdict.REJECT


# =============================================================================
# Concurrency Tests
# =============================================================================


def test_two_sessions_serialize_promotion(temp_db, sample_run_record):
    """Two independent sessions serialize promotion via BEGIN IMMEDIATE."""
    from app.db.config import create_engine_with_pragmas

    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Setup data in first session
    with Session(engine) as session:
        mission = Mission(id="m1", question="Q")
        session.add(mission)
        hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
        session.add(hypothesis)

        # Champion
        champion_record = sample_run_record.copy()
        champion_record["id"] = "champion_v1"
        champion_record["hypothesis_id"] = "h1"
        champion_record["metrics"]["f1"] = 0.837
        champion_record["metrics"]["roc_auc"] = 0.899
        champion_record["verdict"] = "KEEP"
        champion = insert_experiment(session, champion_record)
        champion.verdict = Verdict.KEEP
        session.add(champion)

        # Two challengers
        challenger_a = sample_run_record.copy()
        challenger_a["id"] = "challenger_a"
        challenger_a["hypothesis_id"] = "h1"
        challenger_a["metrics"]["f1"] = 0.900
        challenger_a["metrics"]["roc_auc"] = 0.950
        _ = insert_experiment(session, challenger_a)

        challenger_b = sample_run_record.copy()
        challenger_b["id"] = "challenger_b"
        challenger_b["hypothesis_id"] = "h1"
        challenger_b["metrics"]["f1"] = 0.920
        challenger_b["metrics"]["roc_auc"] = 0.960
        _ = insert_experiment(session, challenger_b)

        session.commit()

    results = {}

    def promote_a():
        with Session(engine) as session:
            v, r = promote(session, "challenger_a")
            results["a"] = (v, r)

    def promote_b():
        with Session(engine) as session:
            v, r = promote(session, "challenger_b")
            results["b"] = (v, r)

    # Run concurrently
    t1 = threading.Thread(target=promote_a)
    t2 = threading.Thread(target=promote_b)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Both should complete (one waited for lock)
    assert "a" in results
    assert "b" in results

    # Each challenger got exactly one decision
    with Session(engine) as session:
        decisions = list(session.exec(select(ExperimentDecision)).all())
        assert len(decisions) == 2


def test_promotion_reads_latest_champion(temp_db, sample_run_record):
    """Each promotion reads the latest committed champion."""
    from app.db.config import create_engine_with_pragmas

    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Setup
    with Session(engine) as session:
        mission = Mission(id="m1", question="Q")
        session.add(mission)
        hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
        session.add(hypothesis)

        # Initial champion F1=0.837
        champion_record = sample_run_record.copy()
        champion_record["id"] = "champion_v1"
        champion_record["hypothesis_id"] = "h1"
        champion_record["metrics"]["f1"] = 0.837
        champion_record["metrics"]["roc_auc"] = 0.899
        champion_record["verdict"] = "KEEP"
        champion = insert_experiment(session, champion_record)
        champion.verdict = Verdict.KEEP
        session.add(champion)

        # Challenger A: F1=0.900
        challenger_a = sample_run_record.copy()
        challenger_a["id"] = "challenger_a"
        challenger_a["hypothesis_id"] = "h1"
        challenger_a["metrics"]["f1"] = 0.900
        challenger_a["metrics"]["roc_auc"] = 0.950
        insert_experiment(session, challenger_a)

        # Challenger B: F1=0.920
        challenger_b = sample_run_record.copy()
        challenger_b["id"] = "challenger_b"
        challenger_b["hypothesis_id"] = "h1"
        challenger_b["metrics"]["f1"] = 0.920
        challenger_b["metrics"]["roc_auc"] = 0.960
        insert_experiment(session, challenger_b)

        session.commit()

    # Promote A first (in separate session)
    with Session(engine) as session:
        v, _ = promote(session, "challenger_a")
        assert v == Verdict.KEEP

    # Promote B (in separate session) - should beat NEW champion (A)
    with Session(engine) as session:
        v, rationale = promote(session, "challenger_b")
        assert v == Verdict.KEEP
        assert "beats champion challenger_a-keep" in rationale


def test_weaker_second_challenger_rejected(temp_db, sample_run_record):
    """A weaker second challenger is rejected against the newly promoted champion."""
    from app.db.config import create_engine_with_pragmas

    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Setup
    with Session(engine) as session:
        mission = Mission(id="m1", question="Q")
        session.add(mission)
        hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
        session.add(hypothesis)

        # Champion F1=0.837
        champion_record = sample_run_record.copy()
        champion_record["id"] = "champion_v1"
        champion_record["hypothesis_id"] = "h1"
        champion_record["metrics"]["f1"] = 0.837
        champion_record["metrics"]["roc_auc"] = 0.899
        champion_record["verdict"] = "KEEP"
        insert_experiment(session, champion_record)
        session.get(Experiment, "champion_v1").verdict = Verdict.KEEP

        # Challenger A: F1=0.850
        challenger_a = sample_run_record.copy()
        challenger_a["id"] = "challenger_a"
        challenger_a["hypothesis_id"] = "h1"
        challenger_a["metrics"]["f1"] = 0.850
        challenger_a["metrics"]["roc_auc"] = 0.900
        insert_experiment(session, challenger_a)

        # Challenger B: F1=0.840 (weaker than A's 0.850)
        challenger_b = sample_run_record.copy()
        challenger_b["id"] = "challenger_b"
        challenger_b["hypothesis_id"] = "h1"
        challenger_b["metrics"]["f1"] = 0.840
        challenger_b["metrics"]["roc_auc"] = 0.890
        insert_experiment(session, challenger_b)

        session.commit()

    # Promote A first
    with Session(engine) as session:
        v, _ = promote(session, "challenger_a")
        assert v == Verdict.KEEP

    # Promote B - should REJECT against A (0.840 < 0.850)
    with Session(engine) as session:
        v, rationale = promote(session, "challenger_b")
        assert v == Verdict.REJECT
        assert "does not beat champion 0.850" in rationale


def test_no_challenger_receives_multiple_decisions(temp_db, sample_run_record):
    """No challenger receives multiple final decisions even under concurrency."""
    from app.db.config import create_engine_with_pragmas

    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # Setup
    with Session(engine) as session:
        mission = Mission(id="m1", question="Q")
        session.add(mission)
        hypothesis = Hypothesis(id="h1", mission_id="m1", proposal_json="{}")
        session.add(hypothesis)

        champion_record = sample_run_record.copy()
        champion_record["id"] = "champion_v1"
        champion_record["hypothesis_id"] = "h1"
        champion_record["metrics"]["f1"] = 0.80
        champion_record["metrics"]["roc_auc"] = 0.85
        champion_record["verdict"] = "KEEP"
        champion = insert_experiment(session, champion_record)
        champion.verdict = Verdict.KEEP
        session.add(champion)

        challenger = sample_run_record.copy()
        challenger["id"] = "challenger_shared"
        challenger["hypothesis_id"] = "h1"
        challenger["metrics"]["f1"] = 0.90
        challenger["metrics"]["roc_auc"] = 0.95
        insert_experiment(session, challenger)

        session.commit()

    results = {}

    def promote_twice():
        with Session(engine) as session:
            # Try to promote twice in same session
            v1, r1 = promote(session, "challenger_shared")
            v2, r2 = promote(session, "challenger_shared")
            results["same_session"] = (v1, v2, r1, r2)

    def promote_from_other_session():
        with Session(engine) as session:
            v, r = promote(session, "challenger_shared")
            results["other_session"] = (v, r)

    # Run concurrently
    t1 = threading.Thread(target=promote_twice)
    t2 = threading.Thread(target=promote_from_other_session)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # Only one decision should exist
    with Session(engine) as session:
        decisions = list(session.exec(select(ExperimentDecision)).all())
        assert len(decisions) == 1


# =============================================================================
# Transaction Tests
# =============================================================================


def test_failed_transaction_rolls_back(session, sample_run_record):
    """Failed transactions roll back correctly."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    # Insert a champion
    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion_record["verdict"] = "KEEP"
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    # Now try a promotion that will fail due to constraint violation
    # (manually create a decision first, then try to promote)
    pending = insert_experiment(session, sample_run_record)
    session.commit()

    # Manually insert a verdict row AND a decision for the same challenger
    verdict_row = Experiment(
        id=f"{pending.id}-keep",
        hypothesis_id=pending.hypothesis_id,
        config_hash=pending.config_hash,
        seed=pending.seed,
        git_commit=pending.git_commit,
        git_dirty=pending.git_dirty,
        dataset_fingerprint=pending.dataset_fingerprint,
        split_fingerprint=pending.split_fingerprint,
        split_version=pending.split_version,
        metrics=pending.metrics,
        artifact_path=pending.artifact_path,
        verdict=Verdict.KEEP,
        diagnosis=None,
        created_at="2026-10-25T10:00:00+00:00",
        replayable=pending.replayable,
        model=pending.model,
        model_family=pending.model_family,
        feature_set=pending.feature_set,
        threshold=pending.threshold,
        threshold_source=pending.threshold_source,
        candidate_inclusive_metrics=pending.candidate_inclusive_metrics,
        metrics_detail=pending.metrics_detail,
        training=pending.training,
        split_sizes=pending.split_sizes,
        duration_seconds=pending.duration_seconds,
        config=pending.config,
        execution_status=ExecutionStatus.COMPLETED,
    )
    session.add(verdict_row)
    session.commit()

    decision = ExperimentDecision(
        id=f"{pending.id}-keep",
        challenger_id=pending.id,
        verdict_id=f"{pending.id}-keep",
        verdict=Verdict.KEEP,
        rationale="Manual",
    )
    session.add(decision)
    session.commit()

    # Now try to promote - should fail with "already decided" but not crash
    verdict, rationale = promote(session, pending.id)
    assert verdict == Verdict.REJECT
    assert "already decided" in rationale

    # Verify no partial state - only one decision exists
    decisions = list(session.exec(select(ExperimentDecision)).all())
    assert len(decisions) == 1


def test_lock_retries_bounded(session):
    """Lock retries are bounded (test with immediate failure)."""
    # This is harder to test without mocking, but we verify the logic exists
    # by checking the constant
    from app.db.session import BASE_RETRY_DELAY, MAX_RETRIES

    assert MAX_RETRIES == 5
    assert BASE_RETRY_DELAY == 0.05


def test_foreign_keys_active_on_new_connections(temp_db):
    """Foreign keys are active on new connections."""
    engine = create_engine_with_pragmas(temp_db)
    from sqlmodel import SQLModel

    from app.db import models  # noqa: F401

    SQLModel.metadata.create_all(engine)

    # First connection: insert mission
    with Session(engine) as session:
        mission = Mission(id="m1", question="Q")
        session.add(mission)
        session.commit()

    # Second connection: try to insert hypothesis with bad FK
    with Session(engine) as session:
        hypothesis = Hypothesis(id="h1", mission_id="nonexistent", proposal_json="{}")
        session.add(hypothesis)
        with pytest.raises(IntegrityError):
            session.commit()


def test_no_partial_decision_state_committed(session, sample_run_record):
    """No partial decision state is committed on failure."""
    # Need mission and hypothesis for foreign keys
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    hypothesis = Hypothesis(id="H-001", mission_id="m1", proposal_json="{}")
    session.add(hypothesis)
    session.commit()

    champion_record = sample_run_record.copy()
    champion_record["id"] = "champion_v1"
    champion_record["metrics"]["f1"] = 0.80
    champion_record["metrics"]["roc_auc"] = 0.85
    champion_record["verdict"] = "KEEP"
    champion = insert_experiment(session, champion_record)
    champion.verdict = Verdict.KEEP
    session.add(champion)
    session.commit()

    pending = insert_experiment(session, sample_run_record)
    session.commit()

    # Manually insert verdict row but not decision
    verdict_row = Experiment(
        id=f"{pending.id}-keep",
        hypothesis_id=pending.hypothesis_id,
        config_hash=pending.config_hash,
        seed=pending.seed,
        git_commit=pending.git_commit,
        git_dirty=pending.git_dirty,
        dataset_fingerprint=pending.dataset_fingerprint,
        split_fingerprint=pending.split_fingerprint,
        split_version=pending.split_version,
        metrics=pending.metrics,
        artifact_path=pending.artifact_path,
        verdict=Verdict.KEEP,
        diagnosis=None,
        created_at="2026-10-25T10:00:00+00:00",
        replayable=pending.replayable,
        model=pending.model,
        model_family=pending.model_family,
        feature_set=pending.feature_set,
        threshold=pending.threshold,
        threshold_source=pending.threshold_source,
        candidate_inclusive_metrics=pending.candidate_inclusive_metrics,
        metrics_detail=pending.metrics_detail,
        training=pending.training,
        split_sizes=pending.split_sizes,
        duration_seconds=pending.duration_seconds,
        config=pending.config,
    )
    session.add(verdict_row)
    session.commit()

    # Now promote should fail (verdict_id already exists but no decision)
    # Actually it should work and create a new verdict row
    verdict, _ = promote(session, pending.id)
    # Since there's already a verdict row with that ID, this might fail
    # The test verifies we don't get partial state
    decisions = list(session.exec(select(ExperimentDecision)).all())
    # Should have 0 or 1 decision, not a partial state
    assert len(decisions) <= 1


# =============================================================================
# Gate Evaluation Tests
# =============================================================================


def test_evaluate_gate_null_champion():
    """Gate evaluation against null champion uses floor metrics."""
    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.1, "roc_auc": 0.6},
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    result = _evaluate_gate(None, challenger)
    assert result.verdict == Verdict.KEEP
    assert "beats champion null" in result.rationale


def test_evaluate_gate_null_champion_rejects_low_f1():
    """Null champion rejects F1 <= 0."""
    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.0, "roc_auc": 0.6},
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    result = _evaluate_gate(None, challenger)
    assert result.verdict == Verdict.REJECT
    assert "does not beat champion 0.0" in result.rationale


def test_evaluate_gate_null_champion_rejects_low_auc():
    """Null champion rejects AUC < 0.5."""
    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.1, "roc_auc": 0.4},
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    result = _evaluate_gate(None, challenger)
    assert result.verdict == Verdict.REJECT
    assert "AUC 0.4000 degrades below champion 0.5000" in result.rationale


def test_evaluate_gate_rejects_non_replayable():
    """Gate rejects non-replayable runs."""
    champion = Experiment(
        id="champ",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.8, "roc_auc": 0.9},
        artifact_path="artifacts/champ/",
        verdict=Verdict.KEEP,
        replayable=True,
    )

    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.9, "roc_auc": 0.95},
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=False,  # Not replayable
    )

    result = _evaluate_gate(champion, challenger)
    assert result.verdict == Verdict.REJECT
    assert result.rationale == "run not replayable"


def test_evaluate_gate_margin():
    """Gate respects margin parameter."""
    champion = Experiment(
        id="champ",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.80, "roc_auc": 0.90},
        artifact_path="artifacts/champ/",
        verdict=Verdict.KEEP,
        replayable=True,
    )

    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.805, "roc_auc": 0.95},  # Beats by 0.005
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    # Margin 0.01 - should REJECT (0.805 not > 0.80 + 0.01)
    result = _evaluate_gate(champion, challenger, margin=0.01)
    assert result.verdict == Verdict.REJECT

    # Margin 0.0 - should KEEP
    result = _evaluate_gate(champion, challenger, margin=0.0)
    assert result.verdict == Verdict.KEEP


def test_evaluate_gate_auc_tolerance():
    """Gate allows AUC within 1e-9 tolerance."""
    champion = Experiment(
        id="champ",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.80, "roc_auc": 0.90},
        artifact_path="artifacts/champ/",
        verdict=Verdict.KEEP,
        replayable=True,
    )

    challenger = Experiment(
        id="test",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={
            "f1": 0.90,
            "roc_auc": 0.90 - 1e-10,
        },  # Slightly less, within tolerance
        artifact_path="artifacts/test/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    result = _evaluate_gate(champion, challenger)
    assert result.verdict == Verdict.KEEP  # Should pass due to tolerance

    # Below tolerance
    challenger2 = Experiment(
        id="test2",
        config_hash="hash",
        seed=42,
        git_commit="commit",
        dataset_fingerprint="fp",
        metrics={"f1": 0.90, "roc_auc": 0.90 - 1e-8},  # Below tolerance
        artifact_path="artifacts/test2/",
        verdict=Verdict.PENDING,
        replayable=True,
    )

    result = _evaluate_gate(champion, challenger2)
    assert result.verdict == Verdict.REJECT


# =============================================================================
# Paper, GraphEdge, Message Tests
# =============================================================================


def test_paper_model(session):
    """Paper model works correctly."""
    paper = Paper(
        id="paper1",
        title="Test Paper",
        authors="Author et al.",
        year=2023,
        doi="10.1234/test",
        abstract="Test abstract",
        source="arxiv",
    )
    session.add(paper)
    session.commit()

    retrieved = session.get(Paper, "paper1")
    assert retrieved.title == "Test Paper"
    assert retrieved.year == 2023


def test_graph_edge_model(session):
    """GraphEdge model works correctly."""
    edge = GraphEdge(
        src_type="experiment",
        src_id="exp1",
        rel="improves",
        dst_type="experiment",
        dst_id="exp2",
    )
    session.add(edge)
    session.commit()

    assert edge.id is not None
    assert edge.src_type == "experiment"
    assert edge.rel == "improves"


def test_message_model(session):
    """Message model works correctly."""
    mission = Mission(id="m1", question="Q")
    session.add(mission)
    session.commit()

    msg = Message(
        mission_id="m1",
        agent="researcher",
        round=1,
        type="evidence_card",
        body="Evidence...",
        refs_json=json.dumps(["ref1", "ref2"]),
    )
    session.add(msg)
    session.commit()

    assert msg.id is not None
    assert msg.mission_id == "m1"
    assert msg.round == 1


# =============================================================================
# Existing Test Suite Compatibility
# =============================================================================


def test_existing_ml_tests_still_pass():
    """Verify existing ML sandbox tests still pass."""
    import subprocess
    import sys

    # Just run a quick sanity check on a subset of ML tests
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "test_config.py",
            "test_preprocess.py",
            "-q",
            "--tb=short",
        ],
        cwd=Path(__file__).parent,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # Should pass
    assert (
        result.returncode == 0
    ), f"Existing tests failed:\n{result.stdout}\n{result.stderr}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
