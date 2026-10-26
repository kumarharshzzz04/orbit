"""Smoke test for ORBIT backend - verifies the walking skeleton works end-to-end.

This test exercises the complete backend workflow:
Mission -> Hypothesis -> Experiment -> Execution -> Evaluation -> Promotion -> WebSocket verdict
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db.config import create_engine_with_pragmas
from app.main import create_app


@pytest.fixture
def test_client():
    """Create a test client with a fresh database."""
    # Use a unique database name to avoid Windows file locking issues
    db_path = Path(tempfile.gettempdir()) / f"orbit_test_{os.getpid()}_{time.time()}.db"

    engine = create_engine_with_pragmas(db_path)
    SQLModel.metadata.create_all(engine)
    os.environ["ORBIT_DB_PATH"] = str(db_path)

    app = create_app()
    client = TestClient(app)

    yield client

    engine.dispose()
    # On Windows, give it a moment and try to delete
    time.sleep(0.1)
    try:
        if db_path.exists():
            db_path.unlink()
    except PermissionError:
        pass  # Best effort cleanup


def test_smoke_full_lifecycle(test_client: TestClient):
    """Smoke test: complete backend workflow with stub execution."""

    # 1. Create a mission
    mission_resp = test_client.post(
        "/api/missions",
        json={"question": "Find a better exoplanet vetting model", "budget_rounds": 3},
    )
    assert mission_resp.status_code == 201
    mission = mission_resp.json()
    mission_id = mission["id"]
    # Mission starts as 'pending' then can be updated to 'active'
    assert mission["status"] in ("pending", "active")

    # 2. Create a hypothesis
    hyp_resp = test_client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {
                "statement": "Adding vetting features will improve F1",
                "rationale": "Vetting features from folded light curves are label-independent",
                "expected_config": {
                    "model": "baseline",
                    "feature_set": "catalog_v1_plus_vetting",
                },
            },
        },
    )
    assert hyp_resp.status_code == 201
    hypothesis = hyp_resp.json()
    hypothesis_id = hypothesis["id"]
    assert hypothesis["status"] == "proposed"

    # 3. Create an experiment config (stub mode for fast execution)
    config_content = {
        "name": "smoke_test_challenger",
        "model": "baseline",
        "data": {
            "mode": "stub",
            "stub_targets": 103,
            "root": "data",
            "split_version": "v2",
        },
        "features": {"set": "catalog_v1"},
        "seed": 42,
        "training": {
            "threshold_selection": "val_f1",
        },
    }

    config_dir = Path(__file__).resolve().parents[2] / "runs"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / f"smoke_test_{os.getpid()}.json"
    config_path.write_text(json.dumps(config_content))

    try:
        # 4. Create experiment record (PENDING)
        exp_resp = test_client.post(
            "/api/experiments",
            json={
                "hypothesis_id": hypothesis_id,
                "config_hash": "smoke_test_hash_" + str(os.getpid()),
                "seed": 42,
                "git_commit": "test_commit",
                "git_dirty": False,
                "dataset_fingerprint": "test_fingerprint",
                "split_fingerprint": "test_split",
                "split_version": "v1",
                "metrics": {"f1": 0.85, "roc_auc": 0.95},
                "artifact_path": "artifacts/smoke_test/",
                "replayable": True,
                "model": "baseline",
                "model_family": "baseline",
                "feature_set": "catalog_v1",
                "threshold": 0.5,
                "threshold_source": "val_f1",
                "candidate_inclusive_metrics": {},
                "metrics_detail": {},
                "training": {},
                "split_sizes": {"train": 10, "val": 5, "test": 5},
                "duration_seconds": 1.0,
                "config": config_content,
            },
        )
        assert exp_resp.status_code == 201
        experiment = exp_resp.json()
        experiment_id = experiment["id"]
        assert experiment["verdict"] == "PENDING"

        # 5. Execute the experiment via CLI AND register it
        import asyncio

        from app.services.execution import MLExecutionService

        async def run_execution():
            repo_root = Path(__file__).resolve().parents[2]
            service = MLExecutionService(repo_root=repo_root, max_concurrent=1)
            await service.start()
            try:
                result = await service.execute_and_register(
                    config_path=str(config_path),
                    mission_id=mission_id,
                    hypothesis_id=hypothesis_id,
                )
                return result
            finally:
                await service.stop()

        result = asyncio.run(run_execution())

        # Execution should succeed in stub mode
        assert result.success is True, f"Execution failed: {result.error_message}"
        assert result.experiment_id is not None
        assert result.run_record is not None
        assert "metrics" in result.run_record
        assert "f1" in result.run_record["metrics"]

        # The execution service creates a NEW experiment record from the run_record
        # Let's verify that experiment and its attempts
        actual_experiment_id = result.experiment_id
        exp_get = test_client.get(f"/api/experiments/{actual_experiment_id}")
        assert exp_get.status_code == 200
        exp_data = exp_get.json()
        assert exp_data["verdict"] == "PENDING"  # New experiment starts as PENDING

        # Check the attempt was recorded - query by the actual experiment ID
        attempts_resp = test_client.get(
            f"/api/experiments/{actual_experiment_id}/attempts"
        )
        assert attempts_resp.status_code == 200
        attempts = attempts_resp.json()
        assert attempts["total"] >= 1
        assert attempts["items"][0]["execution_status"] == "COMPLETED"

        # 7. Promote the experiment (should REJECT since no champion exists)
        promote_resp = test_client.post(f"/api/experiments/{experiment_id}/promote")
        assert promote_resp.status_code == 200
        promote_data = promote_resp.json()
        assert promote_data["verdict"] == "REJECT"
        assert "rationale" in promote_data

    finally:
        # Cleanup
        if config_path.exists():
            config_path.unlink()


def test_smoke_mission_crud(test_client: TestClient):
    """Smoke test: basic mission CRUD operations."""
    # Create
    resp = test_client.post(
        "/api/missions", json={"question": "Test mission", "budget_rounds": 2}
    )
    assert resp.status_code == 201
    mission = resp.json()
    mission_id = mission["id"]

    # List
    list_resp = test_client.get("/api/missions")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Get
    get_resp = test_client.get(f"/api/missions/{mission_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == mission_id

    # Update status
    update_resp = test_client.patch(
        f"/api/missions/{mission_id}", json={"status": "completed"}
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "completed"


def test_smoke_websocket_connection(test_client: TestClient):
    """Smoke test: WebSocket connection works."""
    # Create a mission first
    mission_resp = test_client.post(
        "/api/missions", json={"question": "WS test", "budget_rounds": 1}
    )
    mission_id = mission_resp.json()["id"]

    # Connect via WebSocket
    with test_client.websocket_connect(f"/ws/{mission_id}") as ws:
        # Should receive a system event on connect
        data = ws.receive_json()
        assert data["event"] == "system"
        assert data["mission_id"] == mission_id
        assert "Connected to mission" in data["payload"]["text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
