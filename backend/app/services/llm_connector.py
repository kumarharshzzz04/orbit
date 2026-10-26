"""LLM connector for ORBIT agent orchestration.

Supports mock mode (replays canned responses) and real LLM mode via OpenAI-compatible API.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

LOG = logging.getLogger("orbit.llm")


class LLMConnector:
    """Connects to LLM for agent reasoning."""

    def __init__(self):
        self.mode = os.environ.get("LLM_MODE", "mock")
        self.base_url = os.environ.get("LLM_BASE_URL", "")
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.model = os.environ.get("LLM_MODEL", "llama-3.1-8b-instant")

        # Load mock responses from fixture
        self._mock_responses = self._load_mock_responses()
        self._mock_index = 0

    def _load_mock_responses(self) -> list[dict[str, Any]]:
        """Load mock agent responses from fixture file."""
        fixture_path = (
            Path(__file__).resolve().parents[3]
            / "docs"
            / "fixtures"
            / "ws_events.jsonl"
        )
        responses = []
        try:
            with fixture_path.open("r") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        event = json.loads(line)
                        if event.get("event") == "agent_message":
                            responses.append(event["payload"])
        except FileNotFoundError:
            LOG.warning("Mock fixture not found at %s", fixture_path)
        return responses

    async def generate_response(
        self,
        agent_type: str,
        context: str,
        message_type: str = "proposal",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Generate a response for the given agent type and context.

        In mock mode, returns canned responses from fixture.
        In real mode, calls the LLM API.
        """
        if self.mode == "mock":
            return self._get_mock_response(agent_type, message_type, **kwargs)

        # Real LLM mode - would call OpenAI-compatible API
        return await self._call_real_llm(agent_type, context, message_type, **kwargs)

    def _get_mock_response(
        self, agent_type: str, message_type: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Get next mock response matching agent type."""
        # Cycle through mock responses
        if not self._mock_responses:
            return self._default_mock_response(agent_type, message_type, **kwargs)

        response = self._mock_responses[self._mock_index % len(self._mock_responses)]
        self._mock_index += 1

        # Override agent type if needed
        response = response.copy()
        response["agent"] = agent_type
        response["type"] = message_type

        return response

    def _default_mock_response(
        self, agent_type: str, message_type: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Generate a default mock response."""
        defaults = {
            "researcher": {
                "type": "evidence_card",
                "body": "Literature review suggests adding vetting features improves F1 by ~0.05 on Kepler data.",
                "refs": ["paper:exominer2021", "KOI-7.01"],
            },
            "hypothesizer": {
                "type": "proposal",
                "body": "Add two fold-derived vetting features to the champion GBM. Expected F1 gain 0.05+.",
                "refs": ["runs/challenger_vetting_features.json"],
            },
            "skeptic": {
                "type": "critique",
                "body": "PASS. Features derived from folded light curve, not labels. Host-grouped split prevents leakage.",
                "refs": ["data/stub/splits/v1.json"],
            },
            "experimenter": {
                "type": "status",
                "body": "Running experiment on frozen split v1. Single config change, seed 42.",
                "refs": ["artifacts/challenger_vetting_features/run_record.json"],
            },
            "evaluator": {
                "type": "verdict",
                "body": "KEEP. F1 improved and AUC maintained. Run is replayable.",
                "refs": [],
            },
            "orchestrator": {
                "type": "status",
                "body": "Mission proceeding to next round.",
                "refs": [],
            },
        }

        return {
            "agent": agent_type,
            "round": kwargs.get("round", 1),
            "type": message_type,
            **defaults.get(
                agent_type, {"body": f"Mock response from {agent_type}", "refs": []}
            ),
        }

    async def _call_real_llm(
        self,
        agent_type: str,
        context: str,
        message_type: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Call real LLM API (OpenAI-compatible)."""
        # This would be implemented with httpx/aiohttp for actual API calls
        # For now, fall back to mock
        LOG.info("Real LLM mode not fully implemented, falling back to mock")
        return self._get_mock_response(agent_type, message_type)


# Global connector instance
_connector: LLMConnector | None = None


def get_llm_connector() -> LLMConnector:
    """Get or create the global LLM connector."""
    global _connector
    if _connector is None:
        _connector = LLMConnector()
    return _connector
