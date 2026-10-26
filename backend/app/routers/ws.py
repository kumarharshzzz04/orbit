"""WebSocket API router for ORBIT backend."""

from __future__ import annotations

import json
import logging

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlmodel import Session

from ..db.config import get_session
from ..db.models import Mission
from ..schemas.ws import WSEvent
from ..services.ws_manager import WSConnectionManager, get_ws_manager

router = APIRouter(prefix="/ws", tags=["websocket"])

LOG = logging.getLogger("orbit.ws.router")


@router.websocket("/{mission_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    mission_id: str,
    session: Session = Depends(get_session),
):
    """
    WebSocket endpoint for mission real-time events.

    Connection is accepted and managed by the WSConnectionManager.
    The client can listen for agent_message, run_progress, run_metrics, verdict, and system events.
    """
    # Verify mission exists
    mission = session.get(Mission, mission_id)
    if not mission:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Mission not found"
        )
        return

    manager = get_ws_manager()
    await manager.connect(websocket, mission_id)

    try:
        # Send initial connection confirmation
        await websocket.send_text(
            json.dumps(
                {
                    "event": "system",
                    "mission_id": mission_id,
                    "payload": {
                        "level": "info",
                        "text": f"Connected to mission {mission_id}",
                    },
                }
            )
        )
        LOG.info("Sent connection confirmation to mission %s", mission_id)

        # Keep connection alive, handle incoming messages (if any)
        while True:
            try:
                data = await websocket.receive_text()
                # Handle incoming client messages if needed
                # For now, we just log them
                LOG.debug("Received WS message from mission %s: %s", mission_id, data)
            except WebSocketDisconnect:
                LOG.info("WebSocket disconnected for mission %s", mission_id)
                break
            except Exception as e:
                LOG.warning("Error receiving WS message: %s", e)
                break

    except WebSocketDisconnect:
        LOG.info("WebSocket disconnect caught for mission %s", mission_id)
        pass
    except Exception as e:
        LOG.error("WebSocket error for mission %s: %s", mission_id, e)
    finally:
        await manager.disconnect(websocket, mission_id)


@router.post("/{mission_id}/broadcast")
async def broadcast_event(
    mission_id: str,
    event: WSEvent,
    manager: WSConnectionManager = Depends(get_ws_manager),
    session: Session = Depends(get_session),
):
    """
    Broadcast a custom event to all connections for a mission.

    This is for internal use by the orchestrator/experimenter agents.
    """
    mission = session.get(Mission, mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    sent = await manager.broadcast(mission_id, event)
    return {"sent_to": sent, "mission_id": mission_id}


@router.get("/stats")
async def websocket_stats(
    manager: WSConnectionManager = Depends(get_ws_manager),
):
    """Get WebSocket connection statistics."""
    missions = manager.get_all_missions()
    return {
        "missions": missions,
        "total_connections": sum(manager.get_connection_count(m) for m in missions),
        "per_mission": {m: manager.get_connection_count(m) for m in missions},
    }
