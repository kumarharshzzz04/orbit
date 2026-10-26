"""Services package for ORBIT backend."""

from .agents import (
    AgentContext,
    AgentMessage,
    AgentType,
    BaseAgent,
    create_agent,
    run_agent_round,
)
from .execution import (
    ExecutionResult,
    MLExecutionService,
    get_execution_service,
    init_execution_service,
    shutdown_execution_service,
)
from .llm_connector import LLMConnector, get_llm_connector
from .orchestrator import (
    MissionOrchestrator,
    OrchestratorConfig,
    get_mission_orchestrator,
    start_mission_orchestrator,
    stop_all_orchestrators,
    stop_mission_orchestrator,
)
from .registry import (
    NULL_CHAMPION_AUC,
    NULL_CHAMPION_F1,
    GateResult,
    _evaluate_gate,
    bootstrap_champion,
    get_champion,
    get_decision,
    insert_experiment,
    list_experiments,
    promote,
    record_attempt_completion,
    record_attempt_start,
)
from .ws_manager import WSConnectionManager, get_ws_manager

__all__ = [
    "insert_experiment",
    "promote",
    "bootstrap_champion",
    "_evaluate_gate",
    "record_attempt_start",
    "record_attempt_completion",
    "get_decision",
    "get_champion",
    "list_experiments",
    "GateResult",
    "NULL_CHAMPION_F1",
    "NULL_CHAMPION_AUC",
    "get_ws_manager",
    "WSConnectionManager",
    "get_execution_service",
    "init_execution_service",
    "shutdown_execution_service",
    "MLExecutionService",
    "ExecutionResult",
    "AgentContext",
    "AgentMessage",
    "AgentType",
    "BaseAgent",
    "create_agent",
    "run_agent_round",
    "MissionOrchestrator",
    "OrchestratorConfig",
    "get_mission_orchestrator",
    "start_mission_orchestrator",
    "stop_all_orchestrators",
    "stop_mission_orchestrator",
    "get_llm_connector",
    "LLMConnector",
]
