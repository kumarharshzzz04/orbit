"""Tests for Mission API endpoints."""

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

    # Cleanup
    # db_path.unlink(missing_ok=True)


@pytest.fixture
def client(temp_db):
    """Create a test client with temp database."""
    import os

    os.environ["ORBIT_DB_PATH"] = str(temp_db)

    # Need to recreate the app with the temp db
    engine = create_engine_with_pragmas(temp_db)
    SQLModel.metadata.create_all(engine)

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client

    engine.dispose()


def test_create_mission(client):
    """Test creating a new mission."""
    response = client.post(
        "/api/missions",
        json={
            "question": "Find a better exoplanet vetting model",
            "budget_rounds": 2,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["question"] == "Find a better exoplanet vetting model"
    assert data["budget_rounds"] == 2
    assert data["status"] == "pending"
    assert data["current_round"] == 0
    assert "id" in data
    assert data["id"].startswith("mission_")


def test_list_missions(client):
    """Test listing missions."""
    # Create a few missions
    client.post("/api/missions", json={"question": "Mission 1", "budget_rounds": 2})
    client.post("/api/missions", json={"question": "Mission 2", "budget_rounds": 3})

    response = client.get("/api/missions")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2
    assert data["limit"] == 50
    assert data["offset"] == 0


def test_list_missions_with_filter(client):
    """Test listing missions with status filter."""
    client.post("/api/missions", json={"question": "Mission 1", "budget_rounds": 2})
    client.post("/api/missions", json={"question": "Mission 2", "budget_rounds": 3})

    response = client.get("/api/missions?status=pending")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    for mission in data["items"]:
        assert mission["status"] == "pending"


def test_list_missions_invalid_status(client):
    """Test listing missions with invalid status filter."""
    response = client.get("/api/missions?status=invalid")
    assert response.status_code == 400


def test_get_mission(client):
    """Test getting a single mission."""
    create_response = client.post(
        "/api/missions",
        json={
            "question": "Test Mission",
            "budget_rounds": 2,
        },
    )
    mission_id = create_response.json()["id"]

    response = client.get(f"/api/missions/{mission_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == mission_id
    assert data["question"] == "Test Mission"
    assert "hypotheses" in data
    assert "attempts" in data


def test_get_mission_not_found(client):
    """Test getting a non-existent mission."""
    response = client.get("/api/missions/nonexistent")
    assert response.status_code == 404


def test_update_mission(client):
    """Test updating a mission."""
    create_response = client.post(
        "/api/missions",
        json={
            "question": "Original Question",
            "budget_rounds": 2,
        },
    )
    mission_id = create_response.json()["id"]

    response = client.patch(
        f"/api/missions/{mission_id}",
        json={
            "question": "Updated Question",
            "budget_rounds": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["question"] == "Updated Question"
    assert data["budget_rounds"] == 3


def test_update_mission_status(client):
    """Test updating mission status."""
    create_response = client.post(
        "/api/missions",
        json={
            "question": "Test Mission",
            "budget_rounds": 2,
        },
    )
    mission_id = create_response.json()["id"]

    response = client.patch(
        f"/api/missions/{mission_id}",
        json={
            "status": "running",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"


def test_update_mission_invalid_status(client):
    """Test updating mission with invalid status."""
    create_response = client.post(
        "/api/missions",
        json={
            "question": "Test Mission",
            "budget_rounds": 2,
        },
    )
    mission_id = create_response.json()["id"]

    response = client.patch(
        f"/api/missions/{mission_id}",
        json={
            "status": "invalid_status",
        },
    )
    assert response.status_code == 400


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
