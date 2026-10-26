// ORBIT Frontend - Experiment Detail Page
// Detailed view of a single experiment with metrics, attempts, and promotion

import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  FlaskConical,
  ArrowLeft,
  ExternalLink,
  TrendingUp,
  Database,
  Copy,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge, StatusBadge } from '@/components/ui/Badge';
import { Tabs, TabList, TabTrigger, TabContent } from '@/components/ui/Tabs';
import { format } from 'date-fns';
import { toast } from 'sonner';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';

export function ExperimentDetail() {
  const { experimentId } = useParams<{ experimentId: string }>();
  const navigate = useNavigate();
  const { currentExperiment, setCurrentExperiment, champion, setChampion } = useOrbitStore();
  const [loading, setLoading] = useState(true);
  const [promoting, setPromoting] = useState(false);
  const [attempts, setAttempts] = useState<Array<{
    id: string;
    config_path: string;
    execution_status: string;
    duration_seconds: number;
    created_at: string;
    artifact_path?: string;
    error_message?: string;
  }>>([]);
  const [decisions, setDecisions] = useState<Array<{
    id: string;
    challenger_id: string;
    verdict_id: string;
    verdict: string;
    rationale: string;
    created_at: string;
  }>>([]);
  const [activeTab, setActiveTab] = useState<string>('overview');

  useEffect(() => {
    if (experimentId) {
      loadExperiment();
    }
  }, [experimentId]);

  const loadExperiment = async () => {
    setLoading(true);
    try {
      const exp = await apiClient.getExperiment(experimentId!);
      setCurrentExperiment(exp);

      // Load attempts
      const attemptsData = await apiClient.listExperimentAttempts(experimentId!);
      setAttempts(attemptsData.items);

      // Load decisions
      const decisionsData = await apiClient.getExperimentDecisions(experimentId!);
      setDecisions(decisionsData);
    } catch (error) {
      toast.error('Failed to load experiment');
      navigate('/experiments');
    } finally {
      setLoading(false);
    }
  };

  const handlePromote = async () => {
    if (!experimentId) return;
    setPromoting(true);
    try {
      const result = await apiClient.promoteExperiment(experimentId);
      toast.success(`Experiment ${result.verdict}: ${result.rationale}`);
      // Reload champion
      const championData = await apiClient.getChampion();
      setChampion(championData);
      loadExperiment();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to promote experiment');
    } finally {
      setPromoting(false);
    }
  };

  const copyToClipboard = async (text: string) => {
    await navigator.clipboard.writeText(text);
    toast.success('Copied to clipboard');
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card className="h-24" />
        <Card className="h-80" />
      </div>
    );
  }

  if (!currentExperiment) {
    return (
      <div className="text-center py-12">
        <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />
        <p className="text-orbit-text-secondary">Experiment not found</p>
        <Button variant="primary" onClick={() => navigate('/experiments')} className="mt-4">
          Back to Experiments
        </Button>
      </div>
    );
  }

  const exp = currentExperiment;
  const isChampion = champion?.id === exp.id;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" onClick={() => navigate('/experiments')}>
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold text-orbit-text-primary">{exp.id}</h1>
            <p className="text-orbit-text-secondary mt-1">
              {exp.model_family || 'Unknown'} • {exp.feature_set || 'Unknown features'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <StatusBadge status={exp.verdict} size="lg" />
          {exp.verdict === 'PENDING' && (
            <Button variant="primary" onClick={handlePromote} loading={promoting}>
              <TrendingUp className="h-4 w-4" aria-hidden="true" />
              Promote
            </Button>
          )}
          {isChampion && (
            <Badge variant="keep" className="gap-1.5">
              <Database className="h-3 w-3" />
              Champion
            </Badge>
          )}
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">F1 Score</p>
          <p className="text-3xl font-bold text-orbit-text-primary mt-1">{exp.metrics?.f1?.toFixed(4) || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">ROC AUC</p>
          <p className="text-3xl font-bold text-orbit-agent-hypothesizer mt-1">{exp.metrics?.roc_auc?.toFixed(4) || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">Precision</p>
          <p className="text-3xl font-bold text-orbit-text-primary mt-1">{exp.metrics?.precision?.toFixed(4) || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">Recall</p>
          <p className="text-3xl font-bold text-orbit-text-primary mt-1">{exp.metrics?.recall?.toFixed(4) || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">Accuracy</p>
          <p className="text-3xl font-bold text-orbit-text-primary mt-1">{exp.metrics?.accuracy?.toFixed(4) || 'N/A'}</p>
        </Card>
        <Card className="p-4">
          <p className="text-orbit-text-tertiary text-sm">Threshold</p>
          <p className="text-3xl font-bold text-orbit-text-primary mt-1">{exp.threshold?.toFixed(4) || 'N/A'}</p>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabList>
          <TabTrigger value="overview">Overview</TabTrigger>
          <TabTrigger value="metrics">All Metrics</TabTrigger>
          <TabTrigger value="attempts">Attempts ({attempts.length})</TabTrigger>
          <TabTrigger value="decisions">Decisions ({decisions.length})</TabTrigger>
        </TabList>

        <TabContent value="overview">
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Configuration</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-orbit-text-tertiary">Config Hash</p>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="font-mono text-xs text-orbit-text-primary bg-orbit-bg-tertiary px-2 py-1 rounded flex-1 break-all">{exp.config_hash}</code>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(exp.config_hash)}>
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Seed</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.seed}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Git Commit</p>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="font-mono text-xs text-orbit-text-primary bg-orbit-bg-tertiary px-2 py-1 rounded flex-1 break-all">{exp.git_commit}</code>
                      <Button variant="ghost" size="sm" onClick={() => copyToClipboard(exp.git_commit)}>
                        <Copy className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Git Dirty</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.git_dirty ? 'Yes' : 'No'}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Dataset Fingerprint</p>
                    <p className="font-mono text-xs text-orbit-text-primary mt-1 break-all">{exp.dataset_fingerprint}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Split Version</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.split_version}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Model</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.model || 'Unknown'}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Model Family</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.model_family || 'Unknown'}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Feature Set</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.feature_set || 'Unknown'}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Replayable</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.replayable ? 'Yes' : 'No'}</p>
                  </div>
                  <div>
                    <p className="text-orbit-text-tertiary">Duration</p>
                    <p className="font-mono text-orbit-text-primary mt-1">{exp.duration_seconds.toFixed(1)}s</p>
                  </div>
                  <div className="lg:col-span-2">
                    <p className="text-orbit-text-tertiary">Artifact Path</p>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="font-mono text-xs text-orbit-text-primary bg-orbit-bg-tertiary px-2 py-1 rounded flex-1 break-all">{exp.artifact_path}</code>
                      {exp.artifact_path && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => window.open(exp.artifact_path, '_blank', 'noopener noreferrer')}
                        >
                          <ExternalLink className="h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Threshold Info</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {exp.threshold_source && (
                  <div>
                    <p className="text-orbit-text-tertiary text-sm">Threshold Source</p>
                    <p className="font-mono text-sm text-orbit-text-primary mt-1">{exp.threshold_source}</p>
                  </div>
                )}
                {exp.candidate_inclusive_metrics && Object.keys(exp.candidate_inclusive_metrics).length > 0 && (
                  <div>
                    <p className="text-orbit-text-tertiary text-sm">Candidate Inclusive Metrics</p>
                    <pre className="mt-2 p-3 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-40">
                      {JSON.stringify(exp.candidate_inclusive_metrics, null, 2)}
                    </pre>
                  </div>
                )}
                {exp.diagnosis && (
                  <div className="pt-4 border-t border-orbit-border-primary/50">
                    <p className="text-orbit-text-tertiary text-sm">Diagnosis</p>
                    <p className="text-orbit-text-secondary mt-1">{exp.diagnosis}</p>
                  </div>
                )}
                <div className="pt-4 border-t border-orbit-border-primary/50">
                  <p className="text-orbit-text-tertiary text-sm">Created</p>
                  <p className="font-mono text-sm text-orbit-text-primary mt-1">{format(new Date(exp.created_at), 'MMM dd, yyyy HH:mm:ss')}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabContent>

        <TabContent value="metrics">
          <div className="mt-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle>Core Metrics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="h-80">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={[
                        { metric: 'Accuracy', value: exp.metrics?.accuracy || 0 },
                        { metric: 'Precision', value: exp.metrics?.precision || 0 },
                        { metric: 'Recall', value: exp.metrics?.recall || 0 },
                        { metric: 'F1', value: exp.metrics?.f1 || 0 },
                        { metric: 'ROC AUC', value: exp.metrics?.roc_auc || 0 },
                      ]}
                      layout="vertical"
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                      <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 1]} />
                      <YAxis dataKey="metric" type="category" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={{ stroke: '#1e293b' }} tickLine={false} width={80} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #1e293b', borderRadius: '8px' }} />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]} fill="#06b6d4" maxBarSize={30}>
                        {[
                          { metric: 'Accuracy', value: exp.metrics?.accuracy || 0 },
                          { metric: 'Precision', value: exp.metrics?.precision || 0 },
                          { metric: 'Recall', value: exp.metrics?.recall || 0 },
                          { metric: 'F1', value: exp.metrics?.f1 || 0 },
                          { metric: 'ROC AUC', value: exp.metrics?.roc_auc || 0 },
                        ].map((_entry, index) => (
                          <Cell key={`cell-${index}`} fill={index === 3 ? '#22c55e' : index === 4 ? '#a855f7' : '#06b6d4'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>All Metrics (JSON)</CardTitle>
              </CardHeader>
              <CardContent>
                <pre className="p-4 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-80 font-mono">
                  {JSON.stringify(exp.metrics, null, 2)}
                </pre>
              </CardContent>
            </Card>

            {exp.metrics_detail && Object.keys(exp.metrics_detail).length > 0 && (
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Detailed Metrics</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="p-4 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-80 font-mono">
                    {JSON.stringify(exp.metrics_detail, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}

            {exp.training && Object.keys(exp.training).length > 0 && (
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Training Info</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="p-4 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-80 font-mono">
                    {JSON.stringify(exp.training, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}

            {exp.split_sizes && Object.keys(exp.split_sizes).length > 0 && (
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Split Sizes</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="p-4 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-80 font-mono">
                    {JSON.stringify(exp.split_sizes, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}

            {exp.config && Object.keys(exp.config).length > 0 && (
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Full Config</CardTitle>
                </CardHeader>
                <CardContent>
                  <pre className="p-4 bg-orbit-bg-tertiary rounded text-xs text-orbit-text-secondary overflow-auto max-h-80 font-mono">
                    {JSON.stringify(exp.config, null, 2)}
                  </pre>
                </CardContent>
              </Card>
            )}
          </div>
        </TabContent>

        <TabContent value="attempts">
          <div className="mt-6">
            {attempts.length > 0 ? (
              <div className="space-y-3">
                {attempts.map((attempt) => (
                  <Card key={attempt.id} className="p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <FlaskConical className="h-5 w-5 text-orbit-agent-experimenter" />
                        <div>
                          <p className="font-mono text-sm">{attempt.id}</p>
                          <p className="text-xs text-orbit-text-tertiary">
                            {attempt.config_path} • {attempt.duration_seconds.toFixed(1)}s
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={attempt.execution_status} />
                        {attempt.artifact_path && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => window.open(attempt.artifact_path, '_blank', 'noopener noreferrer')}
                          >
                            <ExternalLink className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </div>
                    {attempt.error_message && (
                      <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded text-sm text-red-400 font-mono">
                        {attempt.error_message}
                      </div>
                    )}
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="p-8 text-center">
                <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-orbit-text-secondary">No execution attempts recorded</p>
              </Card>
            )}
          </div>
        </TabContent>

        <TabContent value="decisions">
          <div className="mt-6">
            {decisions.length > 0 ? (
              <div className="space-y-3">
                {decisions.map((decision) => (
                  <Card key={decision.id} className="p-4">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <Database className="h-5 w-5 text-orbit-accent-primary" />
                        <div>
                          <p className="font-mono text-sm">{decision.id}</p>
                          <p className="text-xs text-orbit-text-tertiary">
                            Challenger: {decision.challenger_id} • Verdict: {decision.verdict_id}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <StatusBadge status={decision.verdict} />
                      </div>
                    </div>
                    <div className="mt-3 p-3 bg-orbit-bg-tertiary rounded text-sm text-orbit-text-secondary">
                      {decision.rationale}
                    </div>
                    <p className="text-xs text-orbit-text-tertiary mt-2">
                      {format(new Date(decision.created_at), 'MMM dd, yyyy HH:mm:ss')}
                    </p>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="p-8 text-center">
                <Database className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-orbit-text-secondary">No promotion decisions recorded</p>
              </Card>
            )}
          </div>
        </TabContent>
      </Tabs>
    </div>
  );
}