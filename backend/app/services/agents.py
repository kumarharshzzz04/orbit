"""Agent classes for ORBIT autonomous research orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..schemas.common import (
    AgentMessageType,
    AgentType,
    WSMessageType,
)
from .llm_connector import get_llm_connector

LOG = logging.getLogger("orbit.agents")


@dataclass
class AgentContext:
    """Context passed to agents during a mission round."""

    mission_id: str
    mission_question: str
    round_number: int
    previous_hypotheses: list[dict[str, Any]] = field(default_factory=list)
    previous_experiments: list[dict[str, Any]] = field(default_factory=list)
    current_champion: dict[str, Any] | None = None
    available_configs: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AgentMessage:
    """Structured agent message for WebSocket broadcast."""

    agent: AgentType
    round: int
    type: AgentMessageType
    body: str
    refs: list[str] = field(default_factory=list)

    def to_ws_payload(self, mission_id: str) -> dict[str, Any]:
        """Convert to WebSocket event payload."""
        return {
            "event": WSMessageType.AGENT_MESSAGE.value,
            "mission_id": mission_id,
            "payload": {
                "agent": self.agent.value,
                "round": self.round,
                "type": self.type.value,
                "body": self.body,
                "refs": self.refs,
            },
        }


class BaseAgent:
    """Base class for all research agents."""

    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.llm = get_llm_connector()

    async def process(self, context: AgentContext) -> AgentMessage:
        """Process the context and generate a message. Override in subclasses."""
        raise NotImplementedError

    def _build_context_summary(self, context: AgentContext) -> str:
        """Build a text summary of context for LLM prompt."""
        parts = [
            f"Mission: {context.mission_question}",
            f"Round: {context.round_number}",
        ]

        if context.current_champion:
            champ = context.current_champion
            parts.append(
                f"Current champion: {champ.get('id', 'unknown')} "
                f"(F1={champ.get('metrics', {}).get('f1', 0):.4f}, "
                f"AUC={champ.get('metrics', {}).get('roc_auc', 0):.4f})"
            )

        if context.previous_experiments:
            parts.append("Previous experiments:")
            for exp in context.previous_experiments[-3:]:
                parts.append(
                    f"  - {exp.get('id', 'unknown')}: "
                    f"F1={exp.get('metrics', {}).get('f1', 0):.4f}, "
                    f"verdict={exp.get('verdict', 'PENDING')}"
                )

        return "\n".join(parts)


class ResearcherAgent(BaseAgent):
    """Research agent: surveys literature and provides evidence cards."""

    def __init__(self):
        super().__init__(AgentType.RESEARCHER)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Generate evidence card based on mission and prior work."""
        context_summary = self._build_context_summary(context)

        # In mock mode, get canned response
        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.EVIDENCE_CARD.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.EVIDENCE_CARD,
            body=response.get("body", "No relevant literature found."),
            refs=response.get("refs", []),
        )


class HypothesizerAgent(BaseAgent):
    """Hypothesis agent: proposes concrete experiment configurations."""

    def __init__(self):
        super().__init__(AgentType.HYPOTHESIZER)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Generate experiment proposal based on evidence and context."""
        context_summary = self._build_context_summary(context)

        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.PROPOSAL.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.PROPOSAL,
            body=response.get("body", "No hypothesis proposed."),
            refs=response.get("refs", []),
        )


class SkepticAgent(BaseAgent):
    """Skeptic agent: critiques proposals for methodological soundness."""

    def __init__(self):
        super().__init__(AgentType.SKEPTIC)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Critique the current proposal."""
        context_summary = self._build_context_summary(context)

        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.CRITIQUE.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.CRITIQUE,
            body=response.get("body", "No critique available."),
            refs=response.get("refs", []),
        )


class ExperimenterAgent(BaseAgent):
    """Experimenter agent: executes experiments and reports status."""

    def __init__(self):
        super().__init__(AgentType.EXPERIMENTER)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Report experiment execution status."""
        context_summary = self._build_context_summary(context)

        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.STATUS.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.STATUS,
            body=response.get("body", "Experiment status unknown."),
            refs=response.get("refs", []),
        )


class EvaluatorAgent(BaseAgent):
    """Evaluator agent: analyzes results and renders verdicts."""

    def __init__(self):
        super().__init__(AgentType.EVALUATOR)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Evaluate experiment results and provide verdict."""
        context_summary = self._build_context_summary(context)

        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.VERDICT.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.VERDICT,
            body=response.get("body", "No evaluation available."),
            refs=response.get("refs", []),
        )


class OrchestratorAgent(BaseAgent):
    """Orchestrator agent: coordinates the research loop."""

    def __init__(self):
        super().__init__(AgentType.ORCHESTRATOR)

    async def process(self, context: AgentContext) -> AgentMessage:
        """Provide orchestration status update."""
        context_summary = self._build_context_summary(context)

        response = await self.llm.generate_response(
            agent_type=self.agent_type.value,
            context=context_summary,
            message_type=AgentMessageType.STATUS.value,
            round=context.round_number,
        )

        return AgentMessage(
            agent=self.agent_type,
            round=context.round_number,
            type=AgentMessageType.STATUS,
            body=response.get("body", "Orchestration continuing."),
            refs=response.get("refs", []),
        )


# Agent factory
AGENT_CLASSES = {
    AgentType.RESEARCHER: ResearcherAgent,
    AgentType.HYPOTHESIZER: HypothesizerAgent,
    AgentType.SKEPTIC: SkepticAgent,
    AgentType.EXPERIMENTER: ExperimenterAgent,
    AgentType.EVALUATOR: EvaluatorAgent,
    AgentType.ORCHESTRATOR: OrchestratorAgent,
}


def create_agent(agent_type: AgentType) -> BaseAgent:
    """Create an agent instance by type."""
    agent_class = AGENT_CLASSES.get(agent_type)
    if not agent_class:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return agent_class()


async def run_agent_round(
    agent_types: list[AgentType],
    context: AgentContext,
    broadcast_callback: callable | None = None,
) -> list[AgentMessage]:
    """Run a round of agent interactions.

    Args:
        agent_types: Ordered list of agent types to run
        context: Mission context
        broadcast_callback: Optional async callback to broadcast messages

    Returns:
        List of agent messages generated
    """
    messages = []

    for agent_type in agent_types:
        agent = create_agent(agent_type)
        message = await agent.process(context)

        # Broadcast if callback provided
        if broadcast_callback:
            await broadcast_callback(message.to_ws_payload(context.mission_id))

        messages.append(message)

        # Add to context for next agent
        context.previous_hypotheses.append(
            {
                "agent": agent_type.value,
                "message": message.body,
                "type": message.type.value,
                "refs": message.refs,
            }
        )

    return messages
