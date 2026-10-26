"""Tests for WebSocket functionality."""

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


def test_websocket_connect(client):
    """Test WebSocket connection to mission."""
    # Create a mission first
    mission_resp = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    # Connect via WebSocket
    with client.websocket_connect(f"/ws/{mission_id}") as ws:
        # Should receive connection confirmation
        data = ws.receive_json()
        assert data["event"] == "system"
        assert data["mission_id"] == mission_id
        assert data["payload"]["level"] == "info"
        assert "Connected to mission" in data["payload"]["text"]


def test_websocket_connect_invalid_mission(client):
    """Test WebSocket connection to non-existent mission."""
    with pytest.raises(Exception) as exc_info:
        with client.websocket_connect("/ws/nonexistent") as _:
            pass
    # WebSocket connection should fail with 1008 policy violation
    exc = exc_info.value
    # Check for WebSocketDisconnect with code 1008
    assert hasattr(exc, "code") and exc.code == 1008
    assert hasattr(exc, "reason") and "not found" in exc.reason.lower()


def test_websocket_stats(client):
    """Test WebSocket stats endpoint."""
    mission_resp = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    # Connect
    with client.websocket_connect(f"/ws/{mission_id}") as ws:
        ws.receive_json()  # connection confirmation

        # Check stats
        response = client.get("/ws/stats")
        assert response.status_code == 200
        data = response.json()
        assert mission_id in data["missions"]
        assert data["per_mission"][mission_id] == 1
        assert data["total_connections"] == 1


def test_websocket_multiple_clients(client):
    """Test multiple clients on same mission."""
    mission_resp = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    with client.websocket_connect(f"/ws/{mission_id}") as ws1:
        ws1.receive_json()
        with client.websocket_connect(f"/ws/{mission_id}") as ws2:
            ws2.receive_json()

            # Check stats
            response = client.get("/ws/stats")
            data = response.json()
            assert data["per_mission"][mission_id] == 2
            assert data["total_connections"] == 2


def test_websocket_disconnect(client):
    """Test WebSocket disconnect cleanup."""
    mission_resp = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    with client.websocket_connect(f"/ws/{mission_id}") as ws:
        ws.receive_json()

    # After disconnect, stats should show 0
    response = client.get("/ws/stats")
    data = response.json()
    assert data["per_mission"].get(mission_id, 0) == 0


def test_websocket_broadcast_endpoint(client):
    """Test broadcasting via HTTP endpoint."""
    mission_resp = client.post(
        "/api/missions", json={"question": "Test", "budget_rounds": 2}
    )
    mission_id = mission_resp.json()["id"]

    with client.websocket_connect(f"/ws/{mission_id}") as ws:
        ws.receive_json()  # connection confirmation

        # Broadcast an event
        response = client.post(
            f"/ws/{mission_id}/broadcast",
            json={
                "event": "system",
                "mission_id": mission_id,
                "payload": {"level": "info", "text": "Test broadcast"},
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["sent_to"] == 1

        # Receive the broadcast
        msg = ws.receive_json()
        assert msg["event"] == "system"
        assert msg["payload"]["text"] == "Test broadcast"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
