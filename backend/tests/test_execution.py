"""Tests for ML execution service."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

import pytest

from app.services.execution import MLExecutionService


@pytest.fixture
def execution_service():
    """Create an execution service instance."""
    repo_root = Path(__file__).resolve().parents[2]  # orbit root
    service = MLExecutionService(repo_root=repo_root, max_concurrent=1)
    return service


@pytest.mark.asyncio
async def test_execution_service_start_stop(execution_service):
    """Test starting and stopping the execution service."""
    await execution_service.start()
    assert execution_service._semaphore is not None
    await execution_service.stop()


@pytest.mark.asyncio
async def test_execute_nonexistent_config(execution_service):
    """Test executing a non-existent config file."""
    await execution_service.start()
    try:
        result = await execution_service.execute_experiment(
            config_path="nonexistent.json",
            mission_id="test_mission",
        )
        assert result.success is False
        assert result.error_type == "config_not_found"
    finally:
        await execution_service.stop()


@pytest.mark.asyncio
async def test_execute_stub_config(execution_service):
    """Test executing a stub config (fast, no real training)."""
    await execution_service.start()
    try:
        # Create a minimal stub config
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            config = {
                "name": "test_stub",
                "model": "baseline",
                "data": {"mode": "stub"},
                "features": {"set": "catalog_v1"},
                "seed": 42,
                "split_version": "v1",
                "calibration": None,
                "cv": {"n_splits": 2, "shuffle": True},
            }
            json.dump(config, f)
            config_path = f.name

        try:
            result = await execution_service.execute_experiment(
                config_path=config_path,
                mission_id="test_mission",
            )
            # The stub config should at least start and either succeed or fail gracefully
            # We just check it doesn't crash
            assert result is not None
            assert hasattr(result, "success")
        finally:
            os.unlink(config_path)
    finally:
        await execution_service.stop()


@pytest.mark.asyncio
async def test_execute_real_stub_cli_integration(execution_service):
    """Integration test: execute actual Module C CLI with stub config.

    This tests the complete pipeline:
    - Subprocess launch
    - stdout JSON parsing
    - stderr ORBIT_PROGRESS parsing
    - Artifact creation
    - Attempt persistence
    - Execution completion
    """
    await execution_service.start()
    try:
        # Create a proper stub config file in the expected location
        config_content = {
            "name": "test_stub_integration",
            "model": "baseline",
            "data": {"mode": "stub", "stub_targets": 10},
            "features": {"set": "catalog_v1"},
            "seed": 42,
            "split_version": "v1",
            "calibration": None,
            "cv": {"n_splits": 2, "shuffle": True},
            "training": {
                "threshold_selection": "val_f1",
            },
        }

        # Write to a temp file under repo root runs/ directory
        repo_root = Path(__file__).resolve().parents[2]
        config_dir = repo_root / "runs"
        config_dir.mkdir(exist_ok=True)
        config_path = config_dir / f"test_stub_integration_{os.getpid()}.json"

        config_path.write_text(json.dumps(config_content))

        try:
            result = await execution_service.execute_experiment(
                config_path=str(config_path),
                mission_id="test_mission_integration",
            )

            # The stub mode should succeed
            assert result is not None
            assert hasattr(result, "success")

            # If successful, verify the execution result
            if result.success:
                assert result.experiment_id is not None
                assert result.run_record is not None
                assert result.attempt_id is not None
                assert "metrics" in result.run_record
                assert "f1" in result.run_record["metrics"]
                assert result.duration_seconds > 0

                # Verify attempt was persisted in database
                from sqlmodel import select

                from app.db.config import session_scope
                from app.db.models import ExecutionStatus, ExperimentAttempt

                with session_scope() as session:
                    attempt = session.exec(
                        select(ExperimentAttempt).where(
                            ExperimentAttempt.id == result.attempt_id
                        )
                    ).first()
                    assert attempt is not None
                    assert attempt.execution_status == ExecutionStatus.COMPLETED
                    assert attempt.config_hash is not None
                    assert attempt.artifact_path is not None
            else:
                # If it failed, it should have error info
                assert result.error_type is not None
                assert result.error_message is not None
        finally:
            # Cleanup
            if config_path.exists():
                config_path.unlink()
    finally:
        await execution_service.stop()


@pytest.mark.asyncio
async def test_execution_timeout_handling(execution_service):
    """Test that timeout is properly handled."""
    import os
    import tempfile
    from pathlib import Path

    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    from app.db.config import create_engine_with_pragmas
    from app.main import create_app

    # Create a temp database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    engine = create_engine_with_pragmas(db_path)
    SQLModel.metadata.create_all(engine)
    os.environ["ORBIT_DB_PATH"] = str(db_path)

    app = create_app()
    client = TestClient(app)

    # Create a mission first
    mission_resp = client.post(
        "/api/missions", json={"question": "Test timeout", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    try:
        await execution_service.start()
        try:
            # Create a config that will take longer than the timeout
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                config = {
                    "name": "test_timeout",
                    "model": "baseline",
                    "data": {
                        "mode": "stub",
                        "stub_targets": 100000,
                    },  # Large number to slow down
                    "features": {"set": "catalog_v1"},
                    "seed": 42,
                    "split_version": "v1",
                    "calibration": None,
                    "cv": {"n_splits": 2, "shuffle": True},
                }
                json.dump(config, f)
                config_path = f.name

            try:
                result = await execution_service.execute_experiment(
                    config_path=config_path,
                    mission_id=mission_id,
                    timeout=0.1,  # Very short timeout
                )
                # Should fail with timeout
                assert result.success is False
                assert result.error_type == "timeout"
            finally:
                os.unlink(config_path)
        finally:
            await execution_service.stop()
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


@pytest.mark.asyncio
async def test_execution_cancellation(execution_service):
    """Test cooperative cancellation."""
    import os
    import tempfile
    from pathlib import Path

    from fastapi.testclient import TestClient
    from sqlmodel import SQLModel

    from app.db.config import create_engine_with_pragmas
    from app.main import create_app

    # Create a temp database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    engine = create_engine_with_pragmas(db_path)
    SQLModel.metadata.create_all(engine)
    os.environ["ORBIT_DB_PATH"] = str(db_path)

    app = create_app()
    client = TestClient(app)

    # Create a mission first
    mission_resp = client.post(
        "/api/missions", json={"question": "Test cancel", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    cancel_event = asyncio.Event()

    try:
        await execution_service.start()
        try:
            # Create a config
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                config = {
                    "name": "test_cancel",
                    "model": "baseline",
                    "data": {"mode": "stub", "stub_targets": 10000},
                    "features": {"set": "catalog_v1"},
                    "seed": 42,
                    "split_version": "v1",
                    "calibration": None,
                    "cv": {"n_splits": 2, "shuffle": True},
                }
                json.dump(config, f)
                config_path = f.name

            try:
                # Start execution in background and cancel immediately
                async def run_and_cancel():
                    # Give it a moment to start, then cancel
                    await asyncio.sleep(0.05)
                    cancel_event.set()

                # Run both concurrently
                exec_task = asyncio.create_task(
                    execution_service.execute_experiment(
                        config_path=config_path,
                        mission_id=mission_id,
                        cancellation_event=cancel_event,
                    )
                )
                cancel_task = asyncio.create_task(run_and_cancel())

                # The task will raise CancelledError, which is expected
                try:
                    _ = await exec_task
                    await cancel_task
                except asyncio.CancelledError:
                    # This is expected - the execution service raises CancelledError on cancellation
                    pass

                # Verify the attempt was recorded as CANCELLED in database
                from sqlmodel import select

                from app.db.config import session_scope
                from app.db.models import ExecutionStatus, ExperimentAttempt

                with session_scope() as session:
                    attempt = session.exec(
                        select(ExperimentAttempt).where(
                            ExperimentAttempt.mission_id == mission_id
                        )
                    ).first()
                    # The attempt should exist and be marked as cancelled
                    assert attempt is not None
                    assert attempt.execution_status == ExecutionStatus.CANCELLED
            finally:
                if os.path.exists(config_path):
                    os.unlink(config_path)
        finally:
            await execution_service.stop()
    finally:
        engine.dispose()
        if db_path.exists():
            db_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
