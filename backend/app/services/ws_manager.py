"""WebSocket connection manager for ORBIT backend."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fastapi import WebSocket
from pydantic import ValidationError

from ..schemas.ws import (
    AgentMessagePayload,
    RunMetricsPayload,
    RunProgressPayload,
    SystemPayload,
    VerdictPayload,
    WSEvent,
)

LOG = logging.getLogger("orbit.ws")


@dataclass(unsafe_hash=True)
class Connection:
    """Represents a WebSocket connection."""

    websocket: WebSocket
    mission_id: str
    connected_at: float


class WSConnectionManager:
    """
    Manages WebSocket connections and broadcasts events.

    - Handles multiple clients per mission
    - Catches and removes dead connections
    - Validates outgoing events against schema
    """

    def __init__(self):
        self._connections: dict[str, set[Connection]] = (
            {}
        )  # mission_id -> set of connections
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, mission_id: str) -> None:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        connection = Connection(
            websocket=websocket,
            mission_id=mission_id,
            connected_at=asyncio.get_event_loop().time(),
        )
        async with self._lock:
            if mission_id not in self._connections:
                self._connections[mission_id] = set()
            self._connections[mission_id].add(connection)
        LOG.info(
            "WebSocket connected: mission=%s, total_connections=%d",
            mission_id,
            len(self._connections.get(mission_id, set())),
        )

    async def disconnect(self, websocket: WebSocket, mission_id: str) -> None:
        """Remove a WebSocket connection."""
        async with self._lock:
            if mission_id in self._connections:
                connections_to_remove = [
                    c for c in self._connections[mission_id] if c.websocket == websocket
                ]
                for conn in connections_to_remove:
                    self._connections[mission_id].discard(conn)
                if not self._connections[mission_id]:
                    del self._connections[mission_id]
        LOG.info(
            "WebSocket disconnected: mission=%s, remaining_connections=%d",
            mission_id,
            len(self._connections.get(mission_id, set())),
        )

    def _validate_event(self, event: WSEvent) -> bool:
        """Validate event against schema."""
        try:
            # Re-validate to ensure payload structure matches event type
            if event.event == "agent_message":
                AgentMessagePayload(**event.payload)
            elif event.event == "run_progress":
                RunProgressPayload(**event.payload)
            elif event.event == "run_metrics":
                RunMetricsPayload(**event.payload)
            elif event.event == "verdict":
                VerdictPayload(**event.payload)
            elif event.event == "system":
                SystemPayload(**event.payload)
            else:
                LOG.warning("Unknown event type: %s", event.event)
                return False
            return True
        except ValidationError as e:
            LOG.error("Event validation failed: %s", e)
            return False

    async def broadcast(self, mission_id: str, event: WSEvent) -> int:
        """
        Broadcast an event to all connections for a mission.

        Returns the number of connections the event was sent to.
        """
        if not self._validate_event(event):
            LOG.error("Invalid event, not broadcasting: %s", event.model_dump())
            return 0

        message = event.model_dump_json()
        sent_count = 0

        async with self._lock:
            connections = self._connections.get(mission_id, set()).copy()

        # Send to all connections, catching disconnected ones
        dead_connections = []
        for connection in connections:
            try:
                await connection.websocket.send_text(message)
                sent_count += 1
            except Exception as e:
                LOG.warning("Failed to send to connection: %s", e)
                dead_connections.append(connection)

        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                if mission_id in self._connections:
                    for dead in dead_connections:
                        self._connections[mission_id].discard(dead)
                    if not self._connections[mission_id]:
                        del self._connections[mission_id]

        LOG.debug(
            "Broadcast event %s to mission %s: %d sent, %d dead",
            event.event,
            mission_id,
            sent_count,
            len(dead_connections),
        )
        return sent_count

    async def broadcast_agent_message(
        self,
        mission_id: str,
        agent: str,
        round_num: int,
        msg_type: str,
        body: str,
        refs: list[str] | None = None,
    ) -> int:
        """Broadcast an agent message event."""
        event = WSEvent(
            event="agent_message",
            mission_id=mission_id,
            payload={
                "agent": agent,
                "round": round_num,
                "type": msg_type,
                "body": body,
                "refs": refs or [],
            },
        )
        return await self.broadcast(mission_id, event)

    async def broadcast_run_progress(
        self,
        mission_id: str,
        run_id: str,
        stage: str,
        percent: float,
    ) -> int:
        """Broadcast a run progress event."""
        event = WSEvent(
            event="run_progress",
            mission_id=mission_id,
            payload={
                "run_id": run_id,
                "stage": stage,
                "percent": percent,
            },
        )
        return await self.broadcast(mission_id, event)

    async def broadcast_run_metrics(
        self,
        mission_id: str,
        run_id: str,
        metrics: dict[str, float],
    ) -> int:
        """Broadcast run metrics event."""
        event = WSEvent(
            event="run_metrics",
            mission_id=mission_id,
            payload={
                "run_id": run_id,
                "metrics": metrics,
            },
        )
        return await self.broadcast(mission_id, event)

    async def broadcast_verdict(
        self,
        mission_id: str,
        run_id: str,
        kept: bool,
        rationale: str,
    ) -> int:
        """Broadcast a verdict event."""
        event = WSEvent(
            event="verdict",
            mission_id=mission_id,
            payload={
                "run_id": run_id,
                "kept": kept,
                "rationale": rationale,
            },
        )
        return await self.broadcast(mission_id, event)

    async def broadcast_system(
        self,
        mission_id: str,
        level: str,
        text: str,
    ) -> int:
        """Broadcast a system event."""
        event = WSEvent(
            event="system",
            mission_id=mission_id,
            payload={
                "level": level,
                "text": text,
            },
        )
        return await self.broadcast(mission_id, event)

    def get_connection_count(self, mission_id: str) -> int:
        """Get the number of active connections for a mission."""
        return len(self._connections.get(mission_id, set()))

    def get_all_missions(self) -> list[str]:
        """Get all mission IDs with active connections."""
        return list(self._connections.keys())


# Global manager instance
_ws_manager: WSConnectionManager | None = None


def get_ws_manager() -> WSConnectionManager:
    """Get the global WebSocket manager instance."""
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WSConnectionManager()
    return _ws_manager
