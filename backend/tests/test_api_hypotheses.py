"""Tests for Hypothesis API endpoints."""

from __future__ import annotations

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


def test_create_hypothesis(client):
    """Test creating a new hypothesis."""
    # First create a mission
    mission_response = client.post(
        "/api/missions",
        json={
            "question": "Test Mission",
            "budget_rounds": 2,
        },
    )
    mission_id = mission_response.json()["id"]

    # Create hypothesis
    response = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "add vetting features", "expected_gain": 0.05},
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["mission_id"] == mission_id
    assert data["status"] == "proposed"
    assert "id" in data
    assert data["id"].startswith("hypothesis_")


def test_create_hypothesis_mission_not_found(client):
    """Test creating hypothesis with non-existent mission."""
    response = client.post(
        "/api/hypotheses",
        json={
            "mission_id": "nonexistent",
            "proposal_json": {"change": "test"},
        },
    )
    assert response.status_code == 404


def test_list_hypotheses(client):
    """Test listing hypotheses."""
    mission_response = client.post(
        "/api/missions",
        json={
            "question": "Test Mission",
            "budget_rounds": 2,
        },
    )
    mission_id = mission_response.json()["id"]

    client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "hypothesis 1"},
        },
    )
    client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "hypothesis 2"},
        },
    )

    response = client.get("/api/hypotheses")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_list_hypotheses_with_mission_filter(client):
    """Test listing hypotheses filtered by mission."""
    mission1 = client.post(
        "/api/missions", json={"question": "Mission 1", "budget_rounds": 2}
    ).json()["id"]
    mission2 = client.post(
        "/api/missions", json={"question": "Mission 2", "budget_rounds": 2}
    ).json()["id"]

    client.post(
        "/api/hypotheses",
        json={"mission_id": mission1, "proposal_json": {"change": "h1"}},
    )
    client.post(
        "/api/hypotheses",
        json={"mission_id": mission2, "proposal_json": {"change": "h2"}},
    )

    response = client.get(f"/api/hypotheses?mission_id={mission1}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["mission_id"] == mission1


def test_list_hypotheses_with_status_filter(client):
    """Test listing hypotheses filtered by status."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]

    client.post(
        "/api/hypotheses",
        json={"mission_id": mission_id, "proposal_json": {"change": "h1"}},
    )
    client.post(
        "/api/hypotheses",
        json={"mission_id": mission_id, "proposal_json": {"change": "h2"}},
    )

    response = client.get("/api/hypotheses?status=proposed")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    for h in data["items"]:
        assert h["status"] == "proposed"


def test_get_hypothesis(client):
    """Test getting a single hypothesis."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]

    create_response = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "test hypothesis", "details": "some details"},
        },
    )
    hypothesis_id = create_response.json()["id"]

    response = client.get(f"/api/hypotheses/{hypothesis_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == hypothesis_id
    assert data["mission_id"] == mission_id
    assert data["proposal_json"]["change"] == "test hypothesis"
    assert "experiments" in data


def test_get_hypothesis_not_found(client):
    """Test getting a non-existent hypothesis."""
    response = client.get("/api/hypotheses/nonexistent")
    assert response.status_code == 404


def test_update_hypothesis(client):
    """Test updating a hypothesis."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]

    create_response = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "original"},
        },
    )
    hypothesis_id = create_response.json()["id"]

    response = client.patch(
        f"/api/hypotheses/{hypothesis_id}",
        json={
            "proposal_json": {"change": "updated", "new_field": "value"},
            "status": "approved",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"

    # Verify the update
    get_response = client.get(f"/api/hypotheses/{hypothesis_id}")
    assert get_response.json()["proposal_json"]["change"] == "updated"


def test_update_hypothesis_invalid_status(client):
    """Test updating hypothesis with invalid status."""
    mission_id = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    ).json()["id"]

    create_response = client.post(
        "/api/hypotheses",
        json={
            "mission_id": mission_id,
            "proposal_json": {"change": "test"},
        },
    )
    hypothesis_id = create_response.json()["id"]

    response = client.patch(
        f"/api/hypotheses/{hypothesis_id}",
        json={
            "status": "invalid_status",
        },
    )
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
