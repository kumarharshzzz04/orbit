// ORBIT Frontend - Live Operations Page
// Real-time mission monitoring with WebSocket integration

import {  useState } from 'react';
// import { useParams } from 'react-router-dom';
import {
  Activity,
  MessageSquare,
  Zap,
  Wifi,
  Loader2,
  Trash2,
  
} from 'lucide-react';
import { useMissionWebSocket } from '@/hooks/useMissionWebSocket';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';
import { format } from 'date-fns';
import { toast } from 'sonner';

export function Live() {
  const { activeMissionId, setActiveMissionId, messages, runProgress, runMetrics, verdicts, systemMessages, clearAllWSData } = useOrbitStore();
  const [selectedMissionId, setSelectedMissionId] = useState<string>('');
  const [autoScroll, setAutoScroll] = useState(true);
  const [filterAgent, setFilterAgent] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [showBroadcastModal, setShowBroadcastModal] = useState(false);

  const {
    isConnected,
    isConnecting,
    sendEvent,
  } = useMissionWebSocket({
    missionId: selectedMissionId || activeMissionId,
    enabled: !!selectedMissionId || !!activeMissionId,
    onConnect: () => toast.success('Connected to mission WebSocket'),
    onDisconnect: () => toast.warning('Disconnected from mission WebSocket'),
    onError: () => toast.error('WebSocket connection error'),
  });

  const filteredMessages = messages
    .filter((m) => filterAgent === 'all' || m.agent === filterAgent)
    .filter((m) => filterType === 'all' || m.type === filterType);

  const agentTypes = [
    'researcher',
    'hypothesizer',
    'skeptic',
    'experimenter',
    'evaluator',
    'orchestrator',
  ];

  const messageTypes = [
    'evidence_card',
    'proposal',
    'critique',
    'run_record',
    'verdict',
    'status',
  ];

  const connectToMission = (missionId: string) => {
    setSelectedMissionId(missionId);
    setActiveMissionId(missionId);
    clearAllWSData();
  };

  const disconnect = () => {
    setSelectedMissionId('');
    setActiveMissionId(null);
  };

  const sendTestMessage = () => {
    if (!selectedMissionId && !activeMissionId) return;

    const event = {
      event: 'system' as const,
      mission_id: selectedMissionId || activeMissionId!,
      payload: {
        level: 'info' as const,
        text: 'Test message from Mission Control',
      },
    };

    sendEvent(event);
    toast.success('Test message sent');
  };

  if (!selectedMissionId && !activeMissionId) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">Live Operations</h1>
          <p className="text-orbit-text-secondary mt-1">
            Real-time mission monitoring and agent communication
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Connect to Mission</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <p className="text-orbit-text-secondary">
                Select a mission to monitor live agent activity, experiment progress, and system events.
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {/* In a real app, this would be populated from the missions list */}
                <Button
                  variant="secondary"
                  className="h-24 flex-col gap-2"
                  onClick={() => connectToMission('mission-001')}
                >
                  <Activity className="h-8 w-8 text-orbit-accent-primary" />
                  <span className="font-medium">Mission 001</span>
                  <span className="text-sm text-orbit-text-tertiary">Research: Fraud Detection</span>
                </Button>
                <Button
                  variant="secondary"
                  className="h-24 flex-col gap-2"
                  onClick={() => connectToMission('mission-002')}
                >
                  <Activity className="h-8 w-8 text-orbit-agent-hypothesizer" />
                  <span className="font-medium">Mission 002</span>
                  <span className="text-sm text-orbit-text-tertiary">Research: Anomaly Detection</span>
                </Button>
                <Button
                  variant="secondary"
                  className="h-24 flex-col gap-2"
                  onClick={() => connectToMission('mission-003')}
                >
                  <Activity className="h-8 w-8 text-orbit-agent-experimenter" />
                  <span className="font-medium">Mission 003</span>
                  <span className="text-sm text-orbit-text-tertiary">Research: Time Series</span>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const currentMissionId = selectedMissionId || activeMissionId!;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className="h-6 w-6 text-orbit-accent-primary" />
            <h1 className="text-2xl font-bold text-orbit-text-primary">Live Operations</h1>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-orbit-bg-tertiary border border-orbit-border-primary">
            {isConnecting ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin text-orbit-accent-warning" />
                <span className="text-sm text-orbit-text-secondary">Connecting...</span>
              </>
            ) : isConnected ? (
              <>
                <span className="status-dot connected" />
                <span className="text-sm font-medium text-orbit-accent-positive">Connected</span>
              </>
            ) : (
              <>
                <span className="status-dot disconnected" />
                <span className="text-sm font-medium text-orbit-accent-negative">Disconnected</span>
              </>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant="secondary" onClick={disconnect}>
            Disconnect
          </Button>
          <Button variant="secondary" onClick={sendTestMessage} disabled={!isConnected}>
            <MessageSquare className="h-4 w-4" />
            Send Test
          </Button>
          <Button variant="primary" onClick={() => setShowBroadcastModal(true)} disabled={!isConnected}>
            <Zap className="h-4 w-4" />
            Broadcast
          </Button>
        </div>
      </div>

      {/* Mission Context */}
      <Card className="p-4 bg-orbit-accent-primary/5 border-orbit-accent-primary/30">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Zap className="h-5 w-5 text-orbit-accent-primary" />
            <div>
              <p className="font-mono text-lg text-orbit-text-primary">{currentMissionId}</p>
              <p className="text-sm text-orbit-text-tertiary">Live WebSocket stream active</p>
            </div>
          </div>
          <div className="flex items-center gap-4 text-sm">
            <span className="flex items-center gap-1 text-orbit-text-secondary">
              <span className="status-dot connected" />
              Agent Stream
            </span>
            <span className="flex items-center gap-1 text-orbit-text-secondary">
              <span className="status-dot connected" />
              Progress
            </span>
            <span className="flex items-center gap-1 text-orbit-text-secondary">
              <span className="status-dot connected" />
              Metrics
            </span>
            <span className="flex items-center gap-1 text-orbit-text-secondary">
              <span className="status-dot connected" />
              Verdicts
            </span>
          </div>
        </div>
      </Card>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex items-center gap-2">
            <label className="text-sm text-orbit-text-tertiary">Agent:</label>
            <select
              value={filterAgent}
              onChange={(e) => setFilterAgent(e.target.value)}
              className="input-field w-auto"
            >
              <option value="all">All Agents</option>
              {agentTypes.map((a) => (
                <option key={a} value={a}>{a.charAt(0).toUpperCase() + a.slice(1)}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="text-sm text-orbit-text-tertiary">Type:</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="input-field w-auto"
            >
              <option value="all">All Types</option>
              {messageTypes.map((t) => (
                <option key={t} value={t}>{t.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase())}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-orbit-text-secondary">
              <input
                type="checkbox"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                className="h-4 w-4 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
              />
              Auto-scroll
            </label>
          </div>
          <Button variant="ghost" size="sm" onClick={() => clearAllWSData()}>
            <Trash2 className="h-4 w-4" />
            Clear
          </Button>
        </div>
      </Card>

      {/* Main Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Messages Panel */}
        <Card className="lg:col-span-2 flex flex-col">
          <CardHeader>
            <CardTitle subtitle={`${filteredMessages.length} messages`}>Agent Messages</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 min-h-0">
            <div
              className="space-y-3 max-h-[600px] overflow-y-auto"
              ref={(el) => {
                if (autoScroll && el) {
                  el.scrollTop = el.scrollHeight;
                }
              }}
            >
              {filteredMessages.length === 0 ? (
                <div className="text-center text-orbit-text-tertiary py-12">
                  <MessageSquare className="h-12 w-12 mx-auto mb-4 opacity-30" />
                  <p>No agent messages yet</p>
                  <p className="text-sm mt-1">Messages will appear here as agents communicate</p>
                </div>
              ) : (
                filteredMessages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`agent-bubble ${msg.agent} p-4`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2 h-2 rounded-full"
                          style={{
                            backgroundColor: `var(--orbit-agent-${msg.agent})`,
                          }}
                        />
                        <span className="font-medium text-sm capitalize">{msg.agent}</span>
                        <Badge variant="default" size="sm">Round {msg.round}</Badge>
                        <Badge variant="default" size="sm">{msg.type}</Badge>
                      </div>
                      <span className="text-xs text-orbit-text-tertiary">
                        {format(new Date(msg.timestamp), 'HH:mm:ss')}
                      </span>
                    </div>
                    <p className="text-orbit-text-secondary text-sm whitespace-pre-wrap">{msg.body}</p>
                    {msg.refs.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {msg.refs.map((ref) => (
                          <Badge key={ref} variant="default" size="sm" className="text-xs">
                            {ref}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        {/* Side Panel: Progress, Metrics, Verdicts, System */}
        <Card className="flex flex-col">
          <CardHeader>
            <CardTitle>Live Feeds</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 min-h-0 space-y-4">
            {/* Run Progress */}
            <div>
              <h4 className="font-medium text-orbit-text-secondary mb-2 flex items-center gap-2">
                <Zap className="h-4 w-4 text-orbit-accent-primary" />
                Run Progress
              </h4>
              <div className="space-y-3 max-h-48 overflow-y-auto">
                {Array.from(runProgress.values()).length === 0 ? (
                  <p className="text-orbit-text-tertiary text-sm text-center py-4">No active runs</p>
                ) : (
                  Array.from(runProgress.values())
                    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                    .map((progress) => (
                      <div key={progress.run_id} className="p-3 bg-orbit-bg-tertiary/50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-mono text-xs">{progress.run_id}</span>
                          <span className="text-xs text-orbit-text-tertiary">{progress.percent}%</span>
                        </div>
                        <div className="progress-bar">
                          <div
                            className="progress-bar-fill"
                            style={{ width: `${progress.percent}%` }}
                          />
                        </div>
                        <p className="text-xs text-orbit-text-tertiary mt-1">{progress.stage}</p>
                      </div>
                    ))
                )}
              </div>
            </div>

            {/* Run Metrics */}
            <div>
              <h4 className="font-medium text-orbit-text-secondary mb-2 flex items-center gap-2">
                <Activity className="h-4 w-4 text-orbit-agent-hypothesizer" />
                Latest Metrics
              </h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {Array.from(runMetrics.values()).length === 0 ? (
                  <p className="text-orbit-text-tertiary text-sm text-center py-4">No metrics received</p>
                ) : (
                  Array.from(runMetrics.values())
                    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
                    .slice(0, 10)
                    .map((metric) => (
                      <div key={metric.run_id} className="p-3 bg-orbit-bg-tertiary/50 rounded-lg">
                        <p className="font-mono text-xs mb-1">{metric.run_id}</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(metric.metrics).map(([key, value]) => (
                            <Badge key={key} variant="default" size="sm" className="text-xs">
                              {key}: {typeof value === 'number' ? value.toFixed(4) : value}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    ))
                )}
              </div>
            </div>

            {/* Verdicts */}
            <div>
              <h4 className="font-medium text-orbit-text-secondary mb-2 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-orbit-accent-positive" />
                Verdicts
              </h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {verdicts.length === 0 ? (
                  <p className="text-orbit-text-tertiary text-sm text-center py-4">No verdicts yet</p>
                ) : (
                  verdicts
                    .slice(-10)
                    .reverse()
                    .map((v, i) => (
                      <div key={`${v.run_id}-${i}`} className="p-3 bg-orbit-bg-tertiary/50 rounded-lg">
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-mono text-xs">{v.run_id}</span>
                          <StatusBadge status={v.kept ? 'KEEP' : 'REJECT'} size="sm" />
                        </div>
                        <p className="text-xs text-orbit-text-tertiary line-clamp-2">{v.rationale}</p>
                      </div>
                    ))
                )}
              </div>
            </div>

            {/* System Messages */}
            <div>
              <h4 className="font-medium text-orbit-text-secondary mb-2 flex items-center gap-2">
                <Wifi className="h-4 w-4 text-orbit-accent-warning" />
                System
              </h4>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {systemMessages.length === 0 ? (
                  <p className="text-orbit-text-tertiary text-sm text-center py-4">No system messages</p>
                ) : (
                  systemMessages
                    .slice(-10)
                    .reverse()
                    .map((msg, i) => (
                      <div
                        key={i}
                        className={`p-3 rounded-lg text-sm ${
                          msg.level === 'error'
                            ? 'bg-red-500/10 border border-red-500/20 text-red-400'
                            : msg.level === 'warn'
                            ? 'bg-amber-500/10 border border-amber-500/20 text-amber-400'
                            : 'bg-orbit-bg-tertiary/50 border border-orbit-border-primary/50 text-orbit-text-secondary'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium capitalize">{msg.level}</span>
                          <span className="text-xs text-orbit-text-tertiary">
                            {format(new Date(msg.timestamp), 'HH:mm:ss')}
                          </span>
                        </div>
                        <p className="mt-1">{msg.text}</p>
                      </div>
                    ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Broadcast Modal */}
      <Modal
        isOpen={showBroadcastModal}
        onClose={() => setShowBroadcastModal(false)}
        title="Broadcast Event"
        description="Send a custom event to all connected clients for this mission"
        size="lg"
      >
        <div className="space-y-4">
          <div>
            <label className="label-text">Event Type</label>
            <select className="input-field" defaultValue="system">
              <option value="agent_message">Agent Message</option>
              <option value="run_progress">Run Progress</option>
              <option value="run_metrics">Run Metrics</option>
              <option value="verdict">Verdict</option>
              <option value="system">System</option>
            </select>
          </div>
          <div>
            <label className="label-text">Payload (JSON)</label>
            <textarea
              className="input-field font-mono text-sm min-h-[150px]"
              defaultValue={JSON.stringify({
                level: 'info',
                text: 'Custom broadcast from Mission Control',
              }, null, 2)}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-orbit-border-primary/50">
            <Button variant="secondary" onClick={() => setShowBroadcastModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => { setShowBroadcastModal(false); toast.success('Event broadcasted'); }}>
              Broadcast
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// Need to import CheckCircle
import { CheckCircle } from 'lucide-react';