// ORBIT Frontend - WebSocket Hook
// Real-time connection management with reconnection and event parsing

import { useEffect, useRef, useCallback, useState } from 'react';
import type { WSEvent, WSMessageType, AgentType, AgentMessageType, SystemLevel } from '@/types/api';
import { useOrbitStore } from '@/stores/useOrbitStore';

interface UseMissionWebSocketOptions {
  missionId: string | null;
  enabled?: boolean;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

interface UseMissionWebSocketReturn {
  isConnected: boolean;
  isConnecting: boolean;
  connectionError: string | null;
  sendEvent: (event: WSEvent) => void;
  reconnect: () => void;
  disconnect: () => void;
}

const RECONNECT_BASE_DELAY = 1000; // 1 second
const RECONNECT_MAX_DELAY = 30000; // 30 seconds
const RECONNECT_MAX_ATTEMPTS = 10;
const HEARTBEAT_INTERVAL = 30000; // 30 seconds

// Browser-compatible timeout type
type TimeoutHandle = ReturnType<typeof setTimeout>;

export function useMissionWebSocket(options: UseMissionWebSocketOptions): UseMissionWebSocketReturn {
  const { missionId, enabled = true, onConnect, onDisconnect, onError } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<TimeoutHandle | null>(null);
  const heartbeatIntervalRef = useRef<TimeoutHandle | null>(null);
  const missionIdRef = useRef(missionId);

  const [isConnected, setIsConnected] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  // Store actions
  const addMessage = useOrbitStore((state) => state.addMessage);
  const addRunProgress = useOrbitStore((state) => state.addRunProgress);
  const updateRunMetrics = useOrbitStore((state) => state.updateRunMetrics);
  const addVerdict = useOrbitStore((state) => state.addVerdict);
  const addSystemMessage = useOrbitStore((state) => state.addSystemMessage);
  const setActiveMissionId = useOrbitStore((state) => state.setActiveMissionId);

  // Keep missionId ref updated
  useEffect(() => {
    missionIdRef.current = missionId;
  }, [missionId]);

  // Parse WebSocket message
  const parseMessage = useCallback((data: string): WSEvent | null => {
    try {
      const parsed = JSON.parse(data);

      // Validate basic structure
      if (!parsed.event || !parsed.mission_id || !parsed.payload) {
        console.warn('Invalid WS message structure:', parsed);
        return null;
      }

      // Validate event type
      const validEvents: WSMessageType[] = ['agent_message', 'run_progress', 'run_metrics', 'verdict', 'system'];
      if (!validEvents.includes(parsed.event)) {
        console.warn('Unknown WS event type:', parsed.event);
        // Still return it for unknown type handling
      }

      return parsed as WSEvent;
    } catch (error) {
      console.error('Failed to parse WS message:', error);
      return null;
    }
  }, []);

  // Handle incoming message
  const handleMessage = useCallback((event: MessageEvent) => {
    const wsEvent = parseMessage(event.data);
    if (!wsEvent) return;

    // Route to appropriate store action
    switch (wsEvent.event) {
      case 'agent_message': {
        const payload = wsEvent.payload as {
          agent: AgentType;
          round: number;
          type: AgentMessageType;
          body: string;
          refs: string[];
        };
        addMessage({
          id: `${wsEvent.mission_id}-${payload.agent}-${payload.round}-${Date.now()}`,
          mission_id: wsEvent.mission_id,
          agent: payload.agent,
          round: payload.round,
          type: payload.type,
          body: payload.body,
          refs: payload.refs,
          timestamp: new Date().toISOString(),
        });
        break;
      }

      case 'run_progress': {
        const payload = wsEvent.payload as { run_id: string; stage: string; percent: number };
        addRunProgress({
          run_id: payload.run_id,
          stage: payload.stage,
          percent: payload.percent,
          timestamp: new Date().toISOString(),
        });
        break;
      }

      case 'run_metrics': {
        const payload = wsEvent.payload as { run_id: string; metrics: Record<string, number> };
        updateRunMetrics(payload.run_id, payload.metrics);
        break;
      }

      case 'verdict': {
        const payload = wsEvent.payload as { run_id: string; kept: boolean; rationale: string };
        addVerdict({
          run_id: payload.run_id,
          kept: payload.kept,
          rationale: payload.rationale,
          timestamp: new Date().toISOString(),
        });
        break;
      }

      case 'system': {
        const payload = wsEvent.payload as { level: SystemLevel; text: string };
        addSystemMessage({
          level: payload.level,
          text: payload.text,
          timestamp: new Date().toISOString(),
        });
        break;
      }

      default:
        // Unknown event type - store as system message for visibility
        addSystemMessage({
          level: 'info',
          text: `Unknown event: ${wsEvent.event}`,
          timestamp: new Date().toISOString(),
        });
    }
  }, [parseMessage, addMessage, addRunProgress, updateRunMetrics, addVerdict, addSystemMessage]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (!missionIdRef.current || !enabled) return;
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    setIsConnecting(true);
    setConnectionError(null);

    const wsUrl = `${import.meta.env.VITE_WS_BASE_URL || 'ws://127.0.0.1:8000'}/ws/${missionIdRef.current}`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[WS] Connected to mission:', missionIdRef.current);
      setIsConnected(true);
      setIsConnecting(false);
      setConnectionError(null);
      reconnectAttemptsRef.current = 0;
      onConnect?.();

      // Start heartbeat
      heartbeatIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, HEARTBEAT_INTERVAL);
    };

    ws.onmessage = handleMessage;

    ws.onclose = (event) => {
      console.log('[WS] Disconnected:', event.code, event.reason);
      setIsConnected(false);
      setIsConnecting(false);

      // Clear heartbeat
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
        heartbeatIntervalRef.current = null;
      }

      onDisconnect?.();

      // Attempt reconnection if not a clean close
      if (event.code !== 1000 && event.code !== 1001 && enabled) {
        scheduleReconnect();
      }
    };

    ws.onerror = (error) => {
      console.error('[WS] Error:', error);
      setConnectionError('WebSocket connection error');
      onError?.(error);
    };

    wsRef.current = ws;
  }, [enabled, handleMessage, onConnect, onDisconnect, onError]);

  // Schedule reconnection with exponential backoff
  const scheduleReconnect = useCallback(() => {
    if (reconnectAttemptsRef.current >= RECONNECT_MAX_ATTEMPTS) {
      setConnectionError('Max reconnection attempts reached');
      return;
    }

    const delay = Math.min(
      RECONNECT_BASE_DELAY * Math.pow(2, reconnectAttemptsRef.current) + Math.random() * 1000,
      RECONNECT_MAX_DELAY
    );

    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1})`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      connect();
    }, delay);
  }, [connect]);

  // Send event
  const sendEvent = useCallback((event: WSEvent) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(event));
    } else {
      console.warn('[WS] Cannot send event: not connected');
    }
  }, []);

  // Manual reconnect
  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    disconnect();
    connect();
  }, [connect]);

  // Disconnect
  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Client disconnect');
      wsRef.current = null;
    }

    setIsConnected(false);
    setIsConnecting(false);
  }, []);

  // Effect for missionId changes
  useEffect(() => {
    if (missionId && enabled) {
      setActiveMissionId(missionId);
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [missionId, enabled, connect, disconnect, setActiveMissionId]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (heartbeatIntervalRef.current) {
        clearInterval(heartbeatIntervalRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Unmount');
      }
    };
  }, []);

  return {
    isConnected,
    isConnecting,
    connectionError,
    sendEvent,
    reconnect,
    disconnect,
  };
}