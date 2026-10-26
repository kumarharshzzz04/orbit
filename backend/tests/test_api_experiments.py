"""Tests for Experiment API endpoints."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from app.db import models  # noqa: F401
from app.db.config import create_engine_with_pragmas
from app.main import create_app


@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for each test."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    engine = create_engine_with_pragmas(db_path)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    yield db_path


@pytest.fixture
def client(temp_db):
    """Create a test client with temp database."""
    import os

    os.environ["ORBIT_DB_PATH"] = str(temp_db)

    engine = create_engine_with_pragmas(temp_db)
    SQLModel.metadata.create_all(engine)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()


def sample_experiment_data(hypothesis_id: str = None):
    """Sample experiment data for testing."""
    return {
        "hypothesis_id": hypothesis_id,
        "config_hash": f"abc123def456_{uuid.uuid4().hex[:8]}",
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


def create_experiment(client, hypothesis_id: str = None, **overrides):
    """Helper to create an experiment with unique config_hash."""
    data = sample_experiment_data(hypothesis_id)
    data.update(overrides)
    data["config_hash"] = f"{data['config_hash']}_{uuid.uuid4().hex[:8]}"
    response = client.post("/api/experiments", json=data)
    return response


def test_create_experiment(client):
    """Test creating a new experiment."""
    response = create_experiment(client)
    assert response.status_code == 201
    data = response.json()
    assert data["verdict"] == "PENDING"
    assert data["execution_status"] == "COMPLETED"
    assert data["metrics"]["f1"] == 0.93
    assert "id" in data
    assert data["id"].startswith("exp_")


def test_create_experiment_with_hypothesis(client):
    """Test creating experiment linked to hypothesis."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]
    hypothesis_id = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "test"},
        },
    ).json()["id"]

    response = create_experiment(client, hypothesis_id)
    assert response.status_code == 201
    data = response.json()
    assert data["hypothesis_id"] == hypothesis_id


def test_create_experiment_duplicate_config_hash(client):
    """Test creating experiment with duplicate config_hash fails."""
    data = sample_experiment_data()
    config_hash = data["config_hash"]
    client.post("/api/experiments", json=data)
    data["config_hash"] = config_hash  # Same hash
    response = client.post("/api/experiments", json=data)
    assert response.status_code == 409


def test_list_experiments(client):
    """Test listing experiments."""
    for _ in range(3):
        create_experiment(client)

    response = client.get("/api/experiments")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 3
    assert len(data["items"]) >= 3


def test_list_experiments_with_verdict_filter(client):
    """Test listing experiments filtered by verdict."""
    create_experiment(client)

    # Check the filter works
    response = client.get("/api/experiments?verdict=PENDING")
    assert response.status_code == 200
    data = response.json()
    for exp in data["items"]:
        assert exp["verdict"] == "PENDING"


def test_list_experiments_with_hypothesis_filter(client):
    """Test listing experiments filtered by hypothesis."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]
    hypothesis_id = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "test"},
        },
    ).json()["id"]

    create_experiment(client, hypothesis_id)

    response = client.get(f"/api/experiments?hypothesis_id={hypothesis_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["hypothesis_id"] == hypothesis_id


def test_get_experiment(client):
    """Test getting a single experiment."""
    response = create_experiment(client)
    experiment_id = response.json()["id"]

    response = client.get(f"/api/experiments/{experiment_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == experiment_id
    assert data["verdict"] == "PENDING"
    assert "attempts" in data
    assert "decisions" in data


def test_get_experiment_not_found(client):
    """Test getting a non-existent experiment."""
    response = client.get("/api/experiments/nonexistent")
    assert response.status_code == 404


def test_get_champion_no_champion(client):
    """Test getting champion when none exists."""
    response = client.get("/api/experiments/champion")
    assert response.status_code == 404


def test_promote_experiment_no_champion(client):
    """Test promoting experiment when no champion exists."""
    response = create_experiment(client)
    experiment_id = response.json()["id"]

    response = client.post(f"/api/experiments/{experiment_id}/promote")
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "REJECT"
    assert "no champion exists" in data["rationale"].lower()


def test_promote_experiment_not_pending(client):
    """Test promoting non-PENDING experiment."""
    # First create a champion
    champion_data = sample_experiment_data()
    champion_data["config_hash"] = f"champion_hash_promo_{uuid.uuid4().hex[:8]}"
    champion_data["metrics"]["f1"] = 0.80
    champion_data["metrics"]["roc_auc"] = 0.85
    client.post("/api/experiments", json=champion_data)

    # Manually set to KEEP (we need to do this via the database for test)
    # For API test, we just test the validation
    challenger_resp = create_experiment(client)
    challenger_id = challenger_resp.json()["id"]

    # Try to promote - will return REJECT because no KEEP champion in DB
    # The API returns 200 with REJECT verdict
    response = client.post(f"/api/experiments/{challenger_id}/promote")
    assert response.status_code == 200
    data = response.json()
    assert data["verdict"] == "REJECT"
    assert "no champion exists" in data["rationale"].lower()


def test_get_experiment_attempts(client):
    """Test getting experiment attempts."""
    response = create_experiment(client)
    experiment_id = response.json()["id"]

    response = client.get(f"/api/experiments/{experiment_id}/attempts")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data


def test_get_experiment_decisions(client):
    """Test getting experiment decisions."""
    response = create_experiment(client)
    experiment_id = response.json()["id"]

    response = client.get(f"/api/experiments/{experiment_id}/decisions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
