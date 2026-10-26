// ORBIT Frontend - API Client
// Centralized Axios instance with typed API functions

import axios, { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type {
  MissionCreate,
  MissionUpdate,
  MissionResponse,
  MissionDetailResponse,
  MissionListResponse,
  HypothesisCreate,
  HypothesisUpdate,
  HypothesisSummary,
  HypothesisDetailResponse,
  HypothesisListResponse,
  ExperimentCreate,
  ExperimentSummary,
  ExperimentDetailResponse,
  ExperimentListResponse,
  ExperimentAttemptListResponse,
  ExperimentDecisionDetailResponse,
  ChampionResponse,
  HealthResponse,
  WSStats,
  WSEvent,
  PaginationParams,
  ErrorResponse,
} from '@/types/api';

// =============================================================================
// Configuration
// =============================================================================

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const REQUEST_TIMEOUT = 30000; // 30 seconds

// =============================================================================
// Axios Instance
// =============================================================================

class APIClient {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: REQUEST_TIMEOUT,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    this.setupInterceptors();
  }

  private setupInterceptors(): void {
    // Request interceptor
    this.client.interceptors.request.use(
      (config: InternalAxiosRequestConfig) => {
        // Add timestamp for cache busting if needed
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.client.interceptors.response.use(
      (response) => response,
      (error: AxiosError<ErrorResponse>) => {
        // Normalize error response
        const normalizedError = {
          message: error.response?.data?.detail || error.message || 'An error occurred',
          code: error.response?.data?.code || 'UNKNOWN_ERROR',
          status: error.response?.status,
        };
        return Promise.reject(normalizedError);
      }
    );
  }

  // =============================================================================
  // Health
  // =============================================================================

  async healthCheck(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }

  // =============================================================================
  // Missions
  // =============================================================================

  async createMission(data: MissionCreate): Promise<MissionResponse> {
    const response = await this.client.post<MissionResponse>('/api/missions', data);
    return response.data;
  }

  async listMissions(params?: PaginationParams & { status?: string }): Promise<MissionListResponse> {
    const response = await this.client.get<MissionListResponse>('/api/missions', { params });
    return response.data;
  }

  async getMission(missionId: string): Promise<MissionDetailResponse> {
    const response = await this.client.get<MissionDetailResponse>(`/api/missions/${missionId}`);
    return response.data;
  }

  async updateMission(missionId: string, data: MissionUpdate): Promise<MissionResponse> {
    const response = await this.client.patch<MissionResponse>(`/api/missions/${missionId}`, data);
    return response.data;
  }

  // =============================================================================
  // Hypotheses
  // =============================================================================

  async createHypothesis(data: HypothesisCreate): Promise<HypothesisSummary> {
    const response = await this.client.post<HypothesisSummary>('/api/hypotheses', data);
    return response.data;
  }

  async listHypotheses(params?: PaginationParams & { mission_id?: string; status?: string }): Promise<HypothesisListResponse> {
    const response = await this.client.get<HypothesisListResponse>('/api/hypotheses', { params });
    return response.data;
  }

  async getHypothesis(hypothesisId: string): Promise<HypothesisDetailResponse> {
    const response = await this.client.get<HypothesisDetailResponse>(`/api/hypotheses/${hypothesisId}`);
    return response.data;
  }

  async updateHypothesis(hypothesisId: string, data: HypothesisUpdate): Promise<HypothesisSummary> {
    const response = await this.client.patch<HypothesisSummary>(`/api/hypotheses/${hypothesisId}`, data);
    return response.data;
  }

  // =============================================================================
  // Experiments
  // =============================================================================

  async createExperiment(data: ExperimentCreate): Promise<ExperimentSummary> {
    const response = await this.client.post<ExperimentSummary>('/api/experiments', data);
    return response.data;
  }

  async listExperiments(params?: PaginationParams & { hypothesis_id?: string; verdict?: string }): Promise<ExperimentListResponse> {
    const response = await this.client.get<ExperimentListResponse>('/api/experiments', { params });
    return response.data;
  }

  async getChampion(): Promise<ChampionResponse> {
    const response = await this.client.get<ChampionResponse>('/api/experiments/champion');
    return response.data;
  }

  async getExperiment(experimentId: string): Promise<ExperimentDetailResponse> {
    const response = await this.client.get<ExperimentDetailResponse>(`/api/experiments/${experimentId}`);
    return response.data;
  }

  async listExperimentAttempts(experimentId: string, params?: PaginationParams): Promise<ExperimentAttemptListResponse> {
    const response = await this.client.get<ExperimentAttemptListResponse>(`/api/experiments/${experimentId}/attempts`, { params });
    return response.data;
  }

  async getExperimentDecisions(experimentId: string): Promise<ExperimentDecisionDetailResponse[]> {
    const response = await this.client.get<ExperimentDecisionDetailResponse[]>(`/api/experiments/${experimentId}/decisions`);
    return response.data;
  }

  async promoteExperiment(experimentId: string, margin?: number): Promise<{ experiment_id: string; verdict: string; rationale: string }> {
    const params = margin !== undefined ? { margin } : {};
    const response = await this.client.post<{ experiment_id: string; verdict: string; rationale: string }>(`/api/experiments/${experimentId}/promote`, null, { params });
    return response.data;
  }

  // =============================================================================
  // WebSocket
  // =============================================================================

  async broadcastEvent(missionId: string, event: WSEvent): Promise<{ sent_to: number; mission_id: string }> {
    const response = await this.client.post<{ sent_to: number; mission_id: string }>(`/ws/${missionId}/broadcast`, event);
    return response.data;
  }

  async getWSStats(): Promise<WSStats> {
    const response = await this.client.get<WSStats>('/ws/stats');
    return response.data;
  }

  // =============================================================================
  // Utility
  // =============================================================================

  getClient(): AxiosInstance {
    return this.client;
  }

  setAuthToken(token: string): void {
    this.client.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  }

  clearAuthToken(): void {
    delete this.client.defaults.headers.common['Authorization'];
  }
}

// Export singleton instance
export const apiClient = new APIClient();

// Export class for testing
export { APIClient };