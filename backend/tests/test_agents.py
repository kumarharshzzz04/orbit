"""Tests for Module A - Agent orchestration."""

from __future__ import annotations

import os

import pytest

os.environ["LLM_MODE"] = "mock"

from app.services.agents import (
    AgentContext,
    AgentMessage,
    AgentType,
    BaseAgent,
    create_agent,
    run_agent_round,
)
from app.services.llm_connector import LLMConnector
from app.services.orchestrator import MissionOrchestrator, OrchestratorConfig


def test_llm_connector_mock_mode():
    """Test LLM connector in mock mode."""
    connector = LLMConnector()
    assert connector.mode == "mock"

    # Test default mock response
    response = connector._default_mock_response("researcher", "evidence_card", round=1)
    assert response["agent"] == "researcher"
    assert response["type"] == "evidence_card"
    assert "body" in response
    assert "refs" in response


def test_llm_connector_fixture_loading():
    """Test that fixture is loaded."""
    connector = LLMConnector()
    # Fixture should have some responses
    assert len(connector._mock_responses) > 0


@pytest.mark.asyncio
async def test_agent_creation():
    """Test agent factory."""
    for agent_type in AgentType:
        agent = create_agent(agent_type)
        assert isinstance(agent, BaseAgent)
        assert agent.agent_type == agent_type


@pytest.mark.asyncio
async def test_researcher_agent():
    """Test researcher agent produces evidence card."""
    agent = create_agent(AgentType.RESEARCHER)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.RESEARCHER
    assert message.type.value == "evidence_card"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_hypothesizer_agent():
    """Test hypothesizer agent produces proposal."""
    agent = create_agent(AgentType.HYPOTHESIZER)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.HYPOTHESIZER
    assert message.type.value == "proposal"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_skeptic_agent():
    """Test skeptic agent produces critique."""
    agent = create_agent(AgentType.SKEPTIC)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.SKEPTIC
    assert message.type.value == "critique"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_experimenter_agent():
    """Test experimenter agent produces status."""
    agent = create_agent(AgentType.EXPERIMENTER)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.EXPERIMENTER
    assert message.type.value == "status"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_evaluator_agent():
    """Test evaluator agent produces verdict."""
    agent = create_agent(AgentType.EVALUATOR)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.EVALUATOR
    assert message.type.value == "verdict"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_orchestrator_agent():
    """Test orchestrator agent produces status."""
    agent = create_agent(AgentType.ORCHESTRATOR)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    message = await agent.process(context)

    assert isinstance(message, AgentMessage)
    assert message.agent == AgentType.ORCHESTRATOR
    assert message.type.value == "status"
    assert len(message.body) > 0


@pytest.mark.asyncio
async def test_run_agent_round():
    """Test running a full agent round."""
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
    )

    broadcast_calls = []

    async def mock_broadcast(payload):
        broadcast_calls.append(payload)

    messages = await run_agent_round(
        agent_types=[
            AgentType.RESEARCHER,
            AgentType.HYPOTHESIZER,
            AgentType.SKEPTIC,
        ],
        context=context,
        broadcast_callback=mock_broadcast,
    )

    assert len(messages) == 3
    assert len(broadcast_calls) == 3
    assert messages[0].agent == AgentType.RESEARCHER
    assert messages[1].agent == AgentType.HYPOTHESIZER
    assert messages[2].agent == AgentType.SKEPTIC


def test_orchestrator_config():
    """Test orchestrator configuration."""
    config = OrchestratorConfig(
        max_rounds=5,
        auto_promote=False,
        promotion_margin=0.01,
    )
    assert config.max_rounds == 5
    assert config.auto_promote is False
    assert config.promotion_margin == 0.01


def test_mission_orchestrator_init():
    """Test mission orchestrator initialization."""
    config = OrchestratorConfig(max_rounds=2)
    orchestrator = MissionOrchestrator("test-mission", config)

    assert orchestrator.mission_id == "test-mission"
    assert orchestrator.config.max_rounds == 2
    assert orchestrator._running is False


def test_agent_message_ws_payload():
    """Test AgentMessage to WebSocket payload conversion."""
    from app.schemas.common import AgentMessageType

    message = AgentMessage(
        agent=AgentType.RESEARCHER,
        round=1,
        type=AgentMessageType.EVIDENCE_CARD,
        body="Test evidence",
        refs=["paper:test"],
    )

    payload = message.to_ws_payload("test-mission")

    assert payload["event"] == "agent_message"
    assert payload["mission_id"] == "test-mission"
    assert payload["payload"]["agent"] == "researcher"
    assert payload["payload"]["round"] == 1
    assert payload["payload"]["type"] == "evidence_card"
    assert payload["payload"]["body"] == "Test evidence"
    assert payload["payload"]["refs"] == ["paper:test"]


def test_agent_context_summary():
    """Test agent context summary building."""
    agent = create_agent(AgentType.RESEARCHER)
    context = AgentContext(
        mission_id="test-mission",
        mission_question="Find better exoplanet model",
        round_number=1,
        current_champion={
            "id": "champ_1",
            "metrics": {"f1": 0.85, "roc_auc": 0.92},
            "model": "baseline",
            "feature_set": "default",
        },
        previous_experiments=[
            {
                "id": "exp_1",
                "metrics": {"f1": 0.80, "roc_auc": 0.88},
                "verdict": "REJECT",
            }
        ],
    )

    summary = agent._build_context_summary(context)

    assert "Find better exoplanet model" in summary
    assert "Round: 1" in summary
    assert "champ_1" in summary
    assert "0.85" in summary
    assert "0.92" in summary
    assert "exp_1" in summary
    assert "REJECT" in summary
