"""Main orchestrator for ORBIT autonomous research loop.

Coordinates agents, experiment execution, and backend integration.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..db.config import session_scope
from ..db.models import Hypothesis, Mission, MissionStatus, Verdict
from ..services.execution import get_execution_service
from ..services.registry import get_champion, promote
from ..services.ws_manager import get_ws_manager
from .agents import (
    AgentContext,
    AgentMessage,
    AgentType,
    run_agent_round,
)
from .llm_connector import get_llm_connector

LOG = logging.getLogger("orbit.orchestrator")


@dataclass
class OrchestratorConfig:
    """Configuration for the orchestrator."""

    max_rounds: int = 3
    agent_sequence: list[AgentType] = field(
        default_factory=lambda: [
            AgentType.RESEARCHER,
            AgentType.HYPOTHESIZER,
            AgentType.SKEPTIC,
            AgentType.EXPERIMENTER,
            AgentType.EVALUATOR,
        ]
    )
    auto_promote: bool = True
    promotion_margin: float = 0.0


class MissionOrchestrator:
    """Orchestrates the complete research workflow for a mission."""

    def __init__(self, mission_id: str, config: OrchestratorConfig | None = None):
        self.mission_id = mission_id
        self.config = config or OrchestratorConfig()
        self.llm = get_llm_connector()
        self.ws_manager = get_ws_manager()
        self.execution_service = get_execution_service()
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the orchestration loop for this mission."""
        if self._running:
            LOG.warning("Orchestrator already running for mission %s", self.mission_id)
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        LOG.info("Started orchestrator for mission %s", self.mission_id)

    async def stop(self) -> None:
        """Stop the orchestration loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        LOG.info("Stopped orchestrator for mission %s", self.mission_id)

    async def _run_loop(self) -> None:
        """Main orchestration loop."""
        try:
            # Load mission and initialize context
            mission_question, context = await self._initialize_context()

            # Broadcast mission start
            await self._broadcast_system(
                f"Mission started: {mission_question}",
                level="info",
            )

            for round_num in range(1, self.config.max_rounds + 1):
                if not self._running:
                    break

                context.round_number = round_num
                LOG.info("Mission %s: starting round %d", self.mission_id, round_num)

                # Broadcast round start
                await self._broadcast_system(
                    f"Starting round {round_num}/{self.config.max_rounds}",
                    level="info",
                )

                # Run agent round
                messages = await run_agent_round(
                    agent_types=self.config.agent_sequence,
                    context=context,
                    broadcast_callback=self._broadcast_agent_message,
                )

                # Process the round results
                await self._process_round_results(context, messages)

                # Check if mission should continue
                if not self._should_continue(context):
                    LOG.info("Mission %s: stopping early", self.mission_id)
                    break

            # Mission complete
            await self._broadcast_system(
                f"Mission {self.mission_id} completed after {context.round_number} round(s)",
                level="info",
            )

            # Update mission status
            await self._update_mission_status(MissionStatus.COMPLETED)

        except asyncio.CancelledError:
            LOG.info("Orchestrator cancelled for mission %s", self.mission_id)
            await self._broadcast_system("Mission cancelled", level="warn")
            await self._update_mission_status(MissionStatus.FAILED)
            raise
        except Exception as e:
            LOG.error("Orchestrator error for mission %s: %s", self.mission_id, e)
            await self._broadcast_system(f"Mission failed: {e}", level="error")
            await self._update_mission_status(MissionStatus.FAILED)

    async def _initialize_context(self) -> tuple[str, AgentContext]:
        """Load mission and build initial agent context."""
        with session_scope() as session:
            mission = session.get(Mission, self.mission_id)
            if not mission:
                raise ValueError(f"Mission not found: {self.mission_id}")

            mission_question = mission.question

            # Get current champion
            champion = get_champion(session)
            champion_data = None
            if champion:
                champion_data = {
                    "id": champion.id,
                    "metrics": champion.metrics,
                    "model": champion.model,
                    "feature_set": champion.feature_set,
                }

            # Get previous hypotheses and experiments
            hypotheses = session.exec(
                session.query(Hypothesis).where(
                    Hypothesis.mission_id == self.mission_id
                )
            ).all()

            previous_hypotheses = []
            previous_experiments = []

            for hyp in hypotheses:
                previous_hypotheses.append(
                    {
                        "id": hyp.id,
                        "proposal": hyp.proposal_json,
                    }
                )

            # Available configs from runs/
            repo_root = Path(__file__).resolve().parents[3]
            runs_dir = repo_root / "runs"
            available_configs = []
            if runs_dir.exists():
                for config_file in runs_dir.glob("*.json"):
                    try:
                        with config_file.open() as f:
                            config = json.load(f)
                            config["_file"] = config_file.name
                            available_configs.append(config)
                    except Exception:
                        pass

            context = AgentContext(
                mission_id=self.mission_id,
                mission_question=mission_question,
                round_number=0,
                previous_hypotheses=previous_hypotheses,
                previous_experiments=previous_experiments,
                current_champion=champion_data,
                available_configs=available_configs,
            )

            return mission_question, context

    async def _process_round_results(
        self,
        context: AgentContext,
        messages: list[AgentMessage],
    ) -> None:
        """Process agent round results: create hypothesis, run experiment, evaluate."""
        # Extract proposal from hypothesizer message
        proposal_msg = next(
            (m for m in messages if m.agent == AgentType.HYPOTHESIZER),
            None,
        )
        if not proposal_msg:
            LOG.warning("No hypothesis proposed in round %d", context.round_number)
            return

        # Create hypothesis in database
        hypothesis_id = await self._create_hypothesis(proposal_msg.body)

        # Extract config reference from proposal
        config_name = self._extract_config_from_proposal(proposal_msg.body)
        if not config_name:
            LOG.warning("No config reference in proposal: %s", proposal_msg.body)
            return

        # Find matching config file
        config_path = self._find_config_file(config_name)
        if not config_path:
            LOG.warning("Config file not found: %s", config_name)
            return

        # Execute experiment
        run_id = f"run_{self.mission_id}_r{context.round_number}_{uuid.uuid4().hex[:8]}"
        await self._broadcast_system(
            f"Starting experiment: {config_name}",
            level="info",
        )

        result = await self.execution_service.execute_and_register(
            config_path=str(config_path),
            mission_id=self.mission_id,
            hypothesis_id=hypothesis_id,
            run_id=run_id,
        )

        if not result.success:
            await self._broadcast_system(
                f"Experiment failed: {result.error_message}",
                level="error",
            )
            return

        # Experiment completed, register in registry
        experiment_id = result.experiment_id
        LOG.info("Experiment registered: %s", experiment_id)

        # Broadcast metrics
        if result.run_record:
            await self._broadcast_run_metrics(result.run_record)

        # Evaluate and promote if configured
        if self.config.auto_promote and experiment_id:
            await self._evaluate_and_promote(experiment_id, context)

    async def _create_hypothesis(self, proposal: str) -> str:
        """Create a hypothesis record in the database."""
        hypothesis_id = f"hyp_{self.mission_id}_r{uuid.uuid4().hex[:8]}"

        with session_scope() as session:
            hypothesis = Hypothesis(
                id=hypothesis_id,
                mission_id=self.mission_id,
                proposal_json=json.dumps({"proposal": proposal}),
                status="proposed",
            )
            session.add(hypothesis)
            session.commit()

        LOG.info("Created hypothesis: %s", hypothesis_id)
        return hypothesis_id

    def _extract_config_from_proposal(self, proposal: str) -> str | None:
        """Extract config file name from proposal text."""
        # Look for references like runs/challenger_vetting_features.json
        import re

        matches = re.findall(r"runs/([\w_]+)\.json", proposal)
        if matches:
            return matches[0]

        # Check available configs for keywords
        for config in self._get_available_configs():
            if config.get("name", "").lower() in proposal.lower():
                return config.get("_file", "").replace(".json", "")

        # Default to baseline
        return "baseline_v1"

    def _find_config_file(self, config_name: str) -> Path | None:
        """Find config file by name."""
        repo_root = Path(__file__).resolve().parents[3]
        runs_dir = repo_root / "runs"

        # Try exact match
        for ext in [".json", ""]:
            config_file = runs_dir / f"{config_name}{ext}"
            if config_file.exists():
                return config_file

        # Try partial match
        for config_file in runs_dir.glob("*.json"):
            if config_name in config_file.stem:
                return config_file

        return None

    def _get_available_configs(self) -> list[dict[str, Any]]:
        """Get list of available config files."""
        repo_root = Path(__file__).resolve().parents[3]
        runs_dir = repo_root / "runs"
        configs = []

        if runs_dir.exists():
            for config_file in runs_dir.glob("*.json"):
                try:
                    with config_file.open() as f:
                        config = json.load(f)
                        config["_file"] = config_file.name
                        configs.append(config)
                except Exception:
                    pass

        return configs

    async def _evaluate_and_promote(
        self, experiment_id: str, context: AgentContext
    ) -> None:
        """Evaluate experiment and promote through gate."""
        with session_scope() as session:
            from ..services.registry import bootstrap_champion, get_champion

            champion = get_champion(session)
            if champion is None:
                # Need to bootstrap champion first
                # Get the experiment's run_record
                from ..db.models import Experiment

                exp = session.get(Experiment, experiment_id)
                if exp:
                    # Build run_record from experiment
                    run_record = {
                        "id": exp.id,
                        "config_hash": exp.config_hash,
                        "seed": exp.seed,
                        "git_commit": exp.git_commit,
                        "git_dirty": exp.git_dirty,
                        "dataset_fingerprint": exp.dataset_fingerprint,
                        "split_fingerprint": exp.split_fingerprint,
                        "split_version": exp.split_version,
                        "metrics": exp.metrics,
                        "artifact_path": exp.artifact_path,
                        "verdict": exp.verdict.value,
                        "diagnosis": exp.diagnosis,
                        "created_at": exp.created_at,
                        "replayable": exp.replayable,
                        "model": exp.model,
                        "model_family": exp.model_family,
                        "feature_set": exp.feature_set,
                        "threshold": exp.threshold,
                        "threshold_source": exp.threshold_source,
                        "candidate_inclusive_metrics": exp.candidate_inclusive_metrics,
                        "metrics_detail": exp.metrics_detail,
                        "training": exp.training,
                        "split_sizes": exp.split_sizes,
                        "duration_seconds": exp.duration_seconds,
                        "config": exp.config,
                    }
                    try:
                        champ = bootstrap_champion(session, run_record)
                        session.commit()
                        verdict = Verdict.KEEP
                        rationale = f"Bootstrapped champion: {champ.id}"
                    except RuntimeError as e:
                        # Bootstrap failed (e.g., gate rejected)
                        verdict = Verdict.REJECT
                        rationale = str(e)
                        session.commit()
                else:
                    verdict = Verdict.REJECT
                    rationale = f"Experiment {experiment_id} not found"
            else:
                verdict, rationale = promote(
                    session,
                    experiment_id,
                    margin=self.config.promotion_margin,
                )
                session.commit()

        kept = verdict == Verdict.KEEP

        # Broadcast verdict
        await self._broadcast_verdict(experiment_id, kept, rationale)

        # Update context with result
        with session_scope() as session:
            from ..db.models import Experiment

            exp = session.get(Experiment, experiment_id)
            if exp:
                context.previous_experiments.append(
                    {
                        "id": exp.id,
                        "metrics": exp.metrics,
                        "verdict": exp.verdict.value,
                    }
                )

        LOG.info(
            "Promotion result for %s: %s - %s", experiment_id, verdict.value, rationale
        )

    async def _broadcast_agent_message(self, payload: dict[str, Any]) -> None:
        """Broadcast agent message via WebSocket."""
        try:
            await self.ws_manager.broadcast_agent_message(
                mission_id=payload["mission_id"],
                agent=payload["payload"]["agent"],
                round_num=payload["payload"]["round"],
                msg_type=payload["payload"]["type"],
                body=payload["payload"]["body"],
                refs=payload["payload"]["refs"],
            )
        except Exception as e:
            LOG.warning("Failed to broadcast agent message: %s", e)

    async def _broadcast_system(self, text: str, level: str = "info") -> None:
        """Broadcast system message via WebSocket."""
        try:
            await self.ws_manager.broadcast_system(
                mission_id=self.mission_id,
                level=level,
                text=text,
            )
        except Exception as e:
            LOG.warning("Failed to broadcast system message: %s", e)

    async def _broadcast_verdict(self, run_id: str, kept: bool, rationale: str) -> None:
        """Broadcast verdict via WebSocket."""
        try:
            await self.ws_manager.broadcast_verdict(
                mission_id=self.mission_id,
                run_id=run_id,
                kept=kept,
                rationale=rationale,
            )
        except Exception as e:
            LOG.warning("Failed to broadcast verdict: %s", e)

    async def _broadcast_run_metrics(self, run_record: dict[str, Any]) -> None:
        """Broadcast run metrics via WebSocket."""
        try:
            await self.ws_manager.broadcast_run_metrics(
                mission_id=self.mission_id,
                run_id=run_record.get("id", ""),
                metrics=run_record.get("metrics", {}),
            )
        except Exception as e:
            LOG.warning("Failed to broadcast metrics: %s", e)

    async def _update_mission_status(self, status: MissionStatus) -> None:
        """Update mission status in database."""
        try:
            with session_scope() as session:
                mission = session.get(Mission, self.mission_id)
                if mission:
                    mission.status = status.value
                    mission.updated_at = datetime.now(UTC).isoformat(timespec="seconds")
                    session.add(mission)
                    session.commit()
        except Exception as e:
            LOG.warning("Failed to update mission status: %s", e)

    def _should_continue(self, context: AgentContext) -> bool:
        """Determine if mission should continue to next round."""
        # Stop if we have a successful KEEP
        recent_keeps = [
            e for e in context.previous_experiments if e.get("verdict") == "KEEP"
        ]
        if recent_keeps:
            return False

        # Stop if max rounds reached (handled by loop)
        return True


# Global orchestrator registry
_active_orchestrators: dict[str, MissionOrchestrator] = {}


async def start_mission_orchestrator(
    mission_id: str,
    config: OrchestratorConfig | None = None,
) -> MissionOrchestrator:
    """Start an orchestrator for a mission."""
    if mission_id in _active_orchestrators:
        LOG.warning("Orchestrator already exists for mission %s", mission_id)
        return _active_orchestrators[mission_id]

    orchestrator = MissionOrchestrator(mission_id, config)
    _active_orchestrators[mission_id] = orchestrator
    await orchestrator.start()
    return orchestrator


async def stop_mission_orchestrator(mission_id: str) -> None:
    """Stop an orchestrator for a mission."""
    orchestrator = _active_orchestrators.pop(mission_id, None)
    if orchestrator:
        await orchestrator.stop()


async def get_mission_orchestrator(mission_id: str) -> MissionOrchestrator | None:
    """Get active orchestrator for a mission."""
    return _active_orchestrators.get(mission_id)


async def stop_all_orchestrators() -> None:
    """Stop all active orchestrators."""
    for orchestrator in _active_orchestrators.values():
        await orchestrator.stop()
    _active_orchestrators.clear()
