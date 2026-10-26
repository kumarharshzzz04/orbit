// ORBIT Frontend - API Type Definitions
// Generated from backend Pydantic schemas

// =============================================================================
// Common Types
// =============================================================================

export type Verdict = 'KEEP' | 'REJECT' | 'PENDING';
export type ExecutionStatus = 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
export type MissionStatus = 'pending' | 'running' | 'completed' | 'failed';
export type HypothesisStatus = 'proposed' | 'approved' | 'vetoed';
export type WSMessageType = 'agent_message' | 'run_progress' | 'run_metrics' | 'verdict' | 'system';
export type AgentType = 'researcher' | 'hypothesizer' | 'skeptic' | 'experimenter' | 'evaluator' | 'orchestrator';
export type AgentMessageType = 'evidence_card' | 'proposal' | 'critique' | 'run_record' | 'verdict' | 'status';
export type SystemLevel = 'info' | 'warn' | 'error';

export interface PaginationParams {
  limit?: number;
  offset?: number;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ErrorResponse {
  detail: string;
  code?: string;
}

export interface HealthResponse {
  status: string;
  database: string;
  ml_sandbox: string;
  timestamp: string;
}

// =============================================================================
// Mission Types
// =============================================================================

export interface MissionCreate {
  question: string;
  budget_rounds?: number;
}

export interface MissionUpdate {
  question?: string;
  budget_rounds?: number;
  status?: string;
}

export interface MissionResponse {
  id: string;
  question: string;
  budget_rounds: number;
  current_round: number;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MissionDetailResponse extends MissionResponse {
  hypotheses: HypothesisSummary[];
  attempts: ExperimentAttemptSummary[];
}

export interface MissionListResponse extends PaginatedResponse<MissionResponse> {}

// =============================================================================
// Hypothesis Types
// =============================================================================

export interface HypothesisCreate {
  mission_id: string;
  proposal_json: Record<string, unknown>;
}

export interface HypothesisUpdate {
  proposal_json?: Record<string, unknown>;
  status?: string;
}

export interface HypothesisSummary {
  id: string;
  mission_id: string;
  status: string;
  created_at: string;
}

export interface HypothesisDetailResponse extends HypothesisSummary {
  proposal_json: Record<string, unknown>;
  experiments: ExperimentSummary[];
}

export interface HypothesisListResponse extends PaginatedResponse<HypothesisSummary> {}

// =============================================================================
// Experiment Types
// =============================================================================

export interface ExperimentAttemptSummary {
  id: string;
  mission_id?: string;
  hypothesis_id?: string;
  experiment_id?: string;
  config_path: string;
  config_hash?: string;
  execution_status: ExecutionStatus;
  error_type?: string;
  error_message?: string;
  artifact_path?: string;
  duration_seconds: number;
  created_at: string;
}

export interface ExperimentAttemptDetailResponse extends ExperimentAttemptSummary {
  stdout_tail?: string;
  stderr_tail?: string;
}

export interface ExperimentDecisionSummary {
  id: string;
  challenger_id: string;
  verdict_id: string;
  verdict: Verdict;
  rationale: string;
  created_at: string;
}

export interface ExperimentDecisionDetailResponse extends ExperimentDecisionSummary {
  challenger?: ExperimentSummary;
  verdict_experiment?: ExperimentSummary;
}

export interface ExperimentCreate {
  hypothesis_id?: string;
  config_hash: string;
  seed: number;
  git_commit: string;
  git_dirty?: boolean;
  dataset_fingerprint: string;
  split_fingerprint?: string;
  split_version?: string;
  metrics: Record<string, number>;
  artifact_path: string;
  replayable?: boolean;
  model?: string;
  model_family?: string;
  feature_set?: string;
  threshold?: number;
  threshold_source?: string;
  candidate_inclusive_metrics?: Record<string, number>;
  metrics_detail?: Record<string, unknown>;
  training?: Record<string, unknown>;
  split_sizes?: Record<string, number>;
  duration_seconds?: number;
  config?: Record<string, unknown>;
}

export interface ExperimentSummary {
  id: string;
  hypothesis_id?: string;
  verdict: Verdict;
  execution_status: ExecutionStatus;
  metrics: Record<string, number>;
  created_at: string;
  model?: string;
  model_family?: string;
  feature_set?: string;
}

export interface ExperimentDetailResponse extends ExperimentSummary {
  config_hash: string;
  seed: number;
  git_commit: string;
  git_dirty: boolean;
  dataset_fingerprint: string;
  split_fingerprint?: string;
  split_version: string;
  artifact_path: string;
  replayable: boolean;
  diagnosis?: string;
  threshold?: number;
  threshold_source?: string;
  candidate_inclusive_metrics: Record<string, number>;
  metrics_detail: Record<string, unknown>;
  training: Record<string, unknown>;
  split_sizes: Record<string, number>;
  duration_seconds: number;
  config: Record<string, unknown>;
  attempts: ExperimentAttemptSummary[];
  decisions: ExperimentDecisionSummary[];
}

export interface ExperimentListResponse extends PaginatedResponse<ExperimentSummary> {}
export interface ExperimentAttemptListResponse extends PaginatedResponse<ExperimentAttemptSummary> {}

export interface ChampionResponse {
  id: string;
  metrics: Record<string, number>;
  artifact_path: string;
  created_at: string;
  diagnosis?: string;
}

// =============================================================================
// WebSocket Types
// =============================================================================

export interface AgentMessagePayload {
  agent: AgentType;
  round: number;
  type: AgentMessageType;
  body: string;
  refs: string[];
}

export interface RunProgressPayload {
  run_id: string;
  stage: string;
  percent: number;
}

export interface RunMetricsPayload {
  run_id: string;
  metrics: Record<string, number>;
}

export interface VerdictPayload {
  run_id: string;
  kept: boolean;
  rationale: string;
}

export interface SystemPayload {
  level: SystemLevel;
  text: string;
}

export type WSPayload = AgentMessagePayload | RunProgressPayload | RunMetricsPayload | VerdictPayload | SystemPayload;

export interface WSEvent {
  event: WSMessageType;
  mission_id: string;
  payload: WSPayload;
}

// =============================================================================
// WebSocket Stats
// =============================================================================

export interface WSStats {
  missions: string[];
  total_connections: number;
  per_mission: Record<string, number>;
}

// =============================================================================
// Broadcast Request
// =============================================================================

export interface BroadcastRequest {
  event: WSEvent;
}