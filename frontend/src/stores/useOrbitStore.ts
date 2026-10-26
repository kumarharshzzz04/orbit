// ORBIT Frontend - Global State Store
// Zustand store for mission data, WebSocket messages, and UI state

import { create } from 'zustand';
import { persist, devtools } from 'zustand/middleware';
import type {
  MissionResponse,
  MissionDetailResponse,
  HypothesisSummary,
  HypothesisDetailResponse,
  ExperimentSummary,
  ExperimentDetailResponse,
  // ExperimentAttemptSummary,
  // ExperimentDecisionDetailResponse,
  ChampionResponse,
  // Verdict,
  // ExecutionStatus,
} from '@/types/api';

// =============================================================================
// Type Definitions
// =============================================================================

export interface AgentMessage {
  id: string;
  mission_id: string;
  agent: string;
  round: number;
  type: string;
  body: string;
  refs: string[];
  timestamp: string;
}

export interface RunProgress {
  run_id: string;
  stage: string;
  percent: number;
  timestamp: string;
}

export interface RunMetrics {
  run_id: string;
  metrics: Record<string, number>;
  timestamp: string;
}

export interface VerdictEvent {
  run_id: string;
  kept: boolean;
  rationale: string;
  timestamp: string;
}

export interface SystemMessage {
  level: 'info' | 'warn' | 'error';
  text: string;
  timestamp: string;
}

export interface UIState {
  sidebarCollapsed: boolean;
  sidebarCompact: boolean;
  activeMissionId: string | null;
  theme: 'dark' | 'light';
}

// =============================================================================
// Store State
// =============================================================================

interface OrbitState extends UIState {
  // Missions
  missions: MissionResponse[];
  missionsTotal: number;
  currentMission: MissionDetailResponse | null;
  missionsLoading: boolean;
  missionsError: string | null;

  // Hypotheses
  hypotheses: HypothesisSummary[];
  hypothesesTotal: number;
  currentHypothesis: HypothesisDetailResponse | null;
  hypothesesLoading: boolean;
  hypothesesError: string | null;

  // Experiments
  experiments: ExperimentSummary[];
  experimentsTotal: number;
  currentExperiment: ExperimentDetailResponse | null;
  champion: ChampionResponse | null;
  experimentsLoading: boolean;
  experimentsError: string | null;

  // WebSocket Events
  messages: AgentMessage[];
  runProgress: Map<string, RunProgress>;
  runMetrics: Map<string, RunMetrics>;
  verdicts: VerdictEvent[];
  systemMessages: SystemMessage[];

  // Actions - Missions
  setMissions: (missions: MissionResponse[], total: number) => void;
  setCurrentMission: (mission: MissionDetailResponse | null) => void;
  addMission: (mission: MissionResponse) => void;
  updateMissionInList: (mission: MissionResponse) => void;
  removeMission: (missionId: string) => void;
  setMissionsLoading: (loading: boolean) => void;
  setMissionsError: (error: string | null) => void;

  // Actions - Hypotheses
  setHypotheses: (hypotheses: HypothesisSummary[], total: number) => void;
  setCurrentHypothesis: (hypothesis: HypothesisDetailResponse | null) => void;
  addHypothesis: (hypothesis: HypothesisSummary) => void;
  updateHypothesisInList: (hypothesis: HypothesisSummary) => void;
  removeHypothesis: (hypothesisId: string) => void;
  setHypothesesLoading: (loading: boolean) => void;
  setHypothesesError: (error: string | null) => void;

  // Actions - Experiments
  setExperiments: (experiments: ExperimentSummary[], total: number) => void;
  setCurrentExperiment: (experiment: ExperimentDetailResponse | null) => void;
  setChampion: (champion: ChampionResponse | null) => void;
  addExperiment: (experiment: ExperimentSummary) => void;
  updateExperimentInList: (experiment: ExperimentSummary) => void;
  removeExperiment: (experimentId: string) => void;
  setExperimentsLoading: (loading: boolean) => void;
  setExperimentsError: (error: string | null) => void;

  // Actions - WebSocket Events
  addMessage: (message: AgentMessage) => void;
  clearMessages: (missionId?: string) => void;
  addRunProgress: (progress: RunProgress) => void;
  updateRunMetrics: (runId: string, metrics: Record<string, number>) => void;
  addVerdict: (verdict: VerdictEvent) => void;
  clearVerdicts: () => void;
  addSystemMessage: (message: SystemMessage) => void;
  clearSystemMessages: () => void;
  clearAllWSData: () => void;

  // Actions - UI
  setSidebarCollapsed: (collapsed: boolean) => void;
  setSidebarCompact: (compact: boolean) => void;
  setActiveMissionId: (missionId: string | null) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  resetStore: () => void;
}

// =============================================================================
// Initial State
// =============================================================================

const initialUIState: UIState = {
  sidebarCollapsed: false,
  sidebarCompact: false,
  activeMissionId: null,
  theme: 'dark',
};

// =============================================================================
// Store Creation
// =============================================================================

export const useOrbitStore = create<OrbitState>()(
  devtools(
    persist(
      (set) => ({
        ...initialUIState,

        // Missions
        missions: [],
        missionsTotal: 0,
        currentMission: null,
        missionsLoading: false,
        missionsError: null,

        setMissions: (missions, total) =>
          set({ missions, missionsTotal: total }, false, 'setMissions'),

        setCurrentMission: (mission) =>
          set({ currentMission: mission }, false, 'setCurrentMission'),

        addMission: (mission) =>
          set((state) => ({
            missions: [mission, ...state.missions],
            missionsTotal: state.missionsTotal + 1,
          }), false, 'addMission'),

        updateMissionInList: (mission) =>
          set((state) => ({
            missions: state.missions.map((m) => (m.id === mission.id ? mission : m)),
            currentMission:
              state.currentMission?.id === mission.id
                ? { ...state.currentMission, ...mission }
                : state.currentMission,
          }), false, 'updateMissionInList'),

        removeMission: (missionId) =>
          set((state) => ({
            missions: state.missions.filter((m) => m.id !== missionId),
            missionsTotal: state.missionsTotal - 1,
            currentMission: state.currentMission?.id === missionId ? null : state.currentMission,
          }), false, 'removeMission'),

        setMissionsLoading: (loading) =>
          set({ missionsLoading: loading }, false, 'setMissionsLoading'),

        setMissionsError: (error) =>
          set({ missionsError: error }, false, 'setMissionsError'),

        // Hypotheses
        hypotheses: [],
        hypothesesTotal: 0,
        currentHypothesis: null,
        hypothesesLoading: false,
        hypothesesError: null,

        setHypotheses: (hypotheses, total) =>
          set({ hypotheses, hypothesesTotal: total }, false, 'setHypotheses'),

        setCurrentHypothesis: (hypothesis) =>
          set({ currentHypothesis: hypothesis }, false, 'setCurrentHypothesis'),

        addHypothesis: (hypothesis) =>
          set((state) => ({
            hypotheses: [hypothesis, ...state.hypotheses],
            hypothesesTotal: state.hypothesesTotal + 1,
          }), false, 'addHypothesis'),

        updateHypothesisInList: (hypothesis) =>
          set((state) => ({
            hypotheses: state.hypotheses.map((h) => (h.id === hypothesis.id ? hypothesis : h)),
            currentHypothesis:
              state.currentHypothesis?.id === hypothesis.id
                ? { ...state.currentHypothesis, ...hypothesis }
                : state.currentHypothesis,
          }), false, 'updateHypothesisInList'),

        removeHypothesis: (hypothesisId) =>
          set((state) => ({
            hypotheses: state.hypotheses.filter((h) => h.id !== hypothesisId),
            hypothesesTotal: state.hypothesesTotal - 1,
            currentHypothesis:
              state.currentHypothesis?.id === hypothesisId ? null : state.currentHypothesis,
          }), false, 'removeHypothesis'),

        setHypothesesLoading: (loading) =>
          set({ hypothesesLoading: loading }, false, 'setHypothesesLoading'),

        setHypothesesError: (error) =>
          set({ hypothesesError: error }, false, 'setHypothesesError'),

        // Experiments
        experiments: [],
        experimentsTotal: 0,
        currentExperiment: null,
        champion: null,
        experimentsLoading: false,
        experimentsError: null,

        setExperiments: (experiments, total) =>
          set({ experiments, experimentsTotal: total }, false, 'setExperiments'),

        setCurrentExperiment: (experiment) =>
          set({ currentExperiment: experiment }, false, 'setCurrentExperiment'),

        setChampion: (champion) =>
          set({ champion }, false, 'setChampion'),

        addExperiment: (experiment) =>
          set((state) => ({
            experiments: [experiment, ...state.experiments],
            experimentsTotal: state.experimentsTotal + 1,
          }), false, 'addExperiment'),

        updateExperimentInList: (experiment) =>
          set((state) => ({
            experiments: state.experiments.map((e) => (e.id === experiment.id ? experiment : e)),
            currentExperiment:
              state.currentExperiment?.id === experiment.id
                ? { ...state.currentExperiment, ...experiment }
                : state.currentExperiment,
            champion:
              state.champion?.id === experiment.id
                ? { ...state.champion, ...experiment }
                : state.champion,
          }), false, 'updateExperimentInList'),

        removeExperiment: (experimentId) =>
          set((state) => ({
            experiments: state.experiments.filter((e) => e.id !== experimentId),
            experimentsTotal: state.experimentsTotal - 1,
            currentExperiment:
              state.currentExperiment?.id === experimentId ? null : state.currentExperiment,
            champion: state.champion?.id === experimentId ? null : state.champion,
          }), false, 'removeExperiment'),

        setExperimentsLoading: (loading) =>
          set({ experimentsLoading: loading }, false, 'setExperimentsLoading'),

        setExperimentsError: (error) =>
          set({ experimentsError: error }, false, 'setExperimentsError'),

        // WebSocket Events
        messages: [],
        runProgress: new Map(),
        runMetrics: new Map(),
        verdicts: [],
        systemMessages: [],

        addMessage: (message) =>
          set((state) => ({
            messages: [...state.messages, message].slice(-500), // Keep last 500 messages
          }), false, 'addMessage'),

        clearMessages: (missionId) =>
          set((state) => ({
            messages: missionId
              ? state.messages.filter((m) => m.mission_id !== missionId)
              : [],
          }), false, 'clearMessages'),

        addRunProgress: (progress) =>
          set((state) => {
            const newMap = new Map(state.runProgress);
            newMap.set(progress.run_id, progress);
            return { runProgress: newMap };
          }, false, 'addRunProgress'),

        updateRunMetrics: (runId, metrics) =>
          set((state) => {
            const newMap = new Map(state.runMetrics);
            const existing = newMap.get(runId);
            newMap.set(runId, {
              run_id: runId,
              metrics: { ...existing?.metrics, ...metrics },
              timestamp: new Date().toISOString(),
            });
            return { runMetrics: newMap };
          }, false, 'updateRunMetrics'),

        addVerdict: (verdict) =>
          set((state) => ({
            verdicts: [...state.verdicts, verdict].slice(-100),
          }), false, 'addVerdict'),

        clearVerdicts: () =>
          set({ verdicts: [] }, false, 'clearVerdicts'),

        addSystemMessage: (message) =>
          set((state) => ({
            systemMessages: [...state.systemMessages, message].slice(-100),
          }), false, 'addSystemMessage'),

        clearSystemMessages: () =>
          set({ systemMessages: [] }, false, 'clearSystemMessages'),

        clearAllWSData: () =>
          set(
            {
              messages: [],
              runProgress: new Map(),
              runMetrics: new Map(),
              verdicts: [],
              systemMessages: [],
            },
            false,
            'clearAllWSData'
          ),

        // UI Actions
        setSidebarCollapsed: (collapsed) =>
          set({ sidebarCollapsed: collapsed }, false, 'setSidebarCollapsed'),

        setSidebarCompact: (compact) =>
          set({ sidebarCompact: compact }, false, 'setSidebarCompact'),

        setActiveMissionId: (missionId) =>
          set({ activeMissionId: missionId }, false, 'setActiveMissionId'),

        setTheme: (theme) =>
          set({ theme }, false, 'setTheme'),

        resetStore: () =>
          set(
            {
              ...initialUIState,
              missions: [],
              missionsTotal: 0,
              currentMission: null,
              missionsLoading: false,
              missionsError: null,
              hypotheses: [],
              hypothesesTotal: 0,
              currentHypothesis: null,
              hypothesesLoading: false,
              hypothesesError: null,
              experiments: [],
              experimentsTotal: 0,
              currentExperiment: null,
              champion: null,
              experimentsLoading: false,
              experimentsError: null,
              messages: [],
              runProgress: new Map(),
              runMetrics: new Map(),
              verdicts: [],
              systemMessages: [],
            },
            false,
            'resetStore'
          ),
      }),
      {
        name: 'orbit-store',
        partialize: (state) => ({
          sidebarCollapsed: state.sidebarCollapsed,
          sidebarCompact: state.sidebarCompact,
          theme: state.theme,
        }),
      }
    ),
    { name: 'OrbitStore' }
  )
);