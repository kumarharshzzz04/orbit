
import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Target,
  Lightbulb,
  FlaskConical,
  Database,
  TrendingUp,
  Clock,
  CheckCircle,
  AlertCircle,
  Zap,
  RefreshCw,
} from 'lucide-react';
import { format } from 'date-fns';
import {
  
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from 'recharts';

import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from '@/components/ui/Card';
import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface HealthStatus {
  status: string;
  database: string;
  ml_sandbox: string;
}

interface ActivityItem {
  id: string;
  type: 'mission' | 'hypothesis' | 'experiment' | 'verdict';
  title: string;
  description: string;
  timestamp: string;
  status?: string;
}

export function Overview() {
  const navigate = useNavigate();

  const {
    missions,
    missionsTotal,
    hypotheses,
    hypothesesTotal,
    experiments,
    experimentsTotal,
    champion,
    setChampion,
  } = useOrbitStore();

  const [loading, setLoading] = useState(true);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);

  const buildRecentActivity = useCallback(() => {
    const activities: ActivityItem[] = [];

    missions.slice(0, 3).forEach((mission) => {
      activities.push({
        id: `mission-${mission.id}`,
        type: 'mission',
        title: 'Mission Created',
        description:
          mission.question.substring(0, 80) +
          (mission.question.length > 80 ? '...' : ''),
        timestamp: mission.created_at,
        status: mission.status,
      });
    });

    hypotheses.slice(0, 3).forEach((hypothesis) => {
      activities.push({
        id: `hypothesis-${hypothesis.id}`,
        type: 'hypothesis',
        title: 'Hypothesis Proposed',
        description: `For mission ${hypothesis.mission_id}`,
        timestamp: hypothesis.created_at,
        status: hypothesis.status,
      });
    });

    experiments.slice(0, 3).forEach((experiment) => {
      activities.push({
        id: `experiment-${experiment.id}`,
        type: 'experiment',
        title:
          experiment.verdict === 'KEEP'
            ? 'Experiment Promoted'
            : 'Experiment Completed',
        description: `${experiment.model_family || 'Unknown'} • F1: ${
          experiment.metrics?.f1?.toFixed(4) || 'N/A'
        }`,
        timestamp: experiment.created_at,
        status: experiment.verdict,
      });
    });

    activities.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() -
        new Date(a.timestamp).getTime()
    );

    setRecentActivity(activities.slice(0, 10));
  }, [missions, hypotheses, experiments]);

  const loadDashboardData = useCallback(async () => {
    setLoading(true);

    try {
      const healthData = await apiClient.healthCheck();
      setHealth(healthData);

      try {
        const championData = await apiClient.getChampion();
        setChampion(championData);
      } catch {
        // No champion has been promoted yet.
        setChampion(null);
      }
    } catch (error) {
      console.error('Failed to load dashboard data:', error);
      setHealth(null);
    } finally {
      setLoading(false);
    }
  }, [setChampion]);

  useEffect(() => {
    void loadDashboardData();
  }, [loadDashboardData]);

  useEffect(() => {
    buildRecentActivity();
  }, [buildRecentActivity]);

  const activeMissions = missions.filter(
    (mission) => mission.status === 'running'
  ).length;

  const completedExperiments = experiments.filter(
    (experiment) => experiment.verdict === 'KEEP'
  ).length;

  const rejectedExperiments = experiments.filter(
    (experiment) => experiment.verdict === 'REJECT'
  ).length;

  const pendingExperiments = experiments.filter(
    (experiment) => experiment.verdict === 'PENDING'
  ).length;

  const metricCards = [
    {
      label: 'Total Missions',
      value: missionsTotal,
      icon: Target,
      color: 'text-orbit-accent-primary',
      description: 'Registered research missions',
    },
    {
      label: 'Active Missions',
      value: activeMissions,
      icon: Zap,
      color: 'text-orbit-accent-positive',
      description: 'Currently running',
    },
    {
      label: 'Hypotheses',
      value: hypothesesTotal,
      icon: Lightbulb,
      color: 'text-orbit-agent-hypothesizer',
      description: 'Research proposals',
    },
    {
      label: 'Experiments',
      value: experimentsTotal,
      icon: FlaskConical,
      color: 'text-orbit-agent-experimenter',
      description: `${completedExperiments} kept · ${rejectedExperiments} rejected`,
    },
    {
      label: 'Champion F1',
      value: champion?.metrics?.f1 != null
        ? champion.metrics.f1.toFixed(4)
        : '—',
      icon: TrendingUp,
      color: 'text-orbit-accent-positive',
      description: champion
        ? `AUC: ${champion.metrics?.roc_auc?.toFixed(4) || 'N/A'}`
        : 'No champion promoted',
    },
    {
      label: 'System Health',
      value:
        health?.status === 'healthy'
          ? 'Healthy'
          : health
            ? 'Degraded'
            : 'Unknown',
      icon:
        health?.status === 'healthy'
          ? CheckCircle
          : AlertCircle,
      color:
        health?.status === 'healthy'
          ? 'text-orbit-accent-positive'
          : 'text-orbit-accent-warning',
      description: health
        ? `DB: ${health.database} · ML: ${health.ml_sandbox}`
        : 'Health status unavailable',
    },
  ];

  const experimentOutcomeData = [
    {
      name: 'KEEP',
      value: completedExperiments,
      color: '#22c55e',
    },
    {
      name: 'REJECT',
      value: rejectedExperiments,
      color: '#ef4444',
    },
    {
      name: 'PENDING',
      value: pendingExperiments,
      color: '#f59e0b',
    },
  ].filter((item) => item.value > 0);

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
          {Array.from({ length: 6 }).map((_, index) => (
            <Card key={index} className="h-24" />
          ))}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="h-80" />
          <Card className="h-80" />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="h-80" />
          <Card className="h-80" />
        </div>

        <Card className="h-64" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Mission Control
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            ORBIT autonomous research platform — real-time mission monitoring
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="secondary"
            onClick={() => void loadDashboardData()}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
            Refresh
          </Button>

          <Button
            variant="primary"
            onClick={() => navigate('/missions/new')}
          >
            <Zap className="h-4 w-4" aria-hidden="true" />
            New Mission
          </Button>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {metricCards.map((metric, index) => (
          <Card
            key={metric.label}
            className={`metric-card stagger-${index + 1}`}
            style={{ animationDelay: `${index * 50}ms` }}
          >
            <div className="flex items-start justify-between">
              <div>
                <p className="text-orbit-text-tertiary text-sm font-medium">
                  {metric.label}
                </p>
                <p className="text-2xl font-bold text-orbit-text-primary mt-1">
                  {metric.value}
                </p>
                <p className="text-xs text-orbit-text-tertiary mt-2">
                  {metric.description}
                </p>
              </div>

              <div className={`p-3 rounded-xl bg-orbit-bg-tertiary ${metric.color}`}>
                <metric.icon className="h-6 w-6" aria-hidden="true" />
              </div>
            </div>
          </Card>
        ))}
      </div>

      {/* Charts Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Model Performance */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="Historical model evaluation metrics">
              Model Performance
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="h-72 flex items-center justify-center">
              <div className="text-center text-orbit-text-tertiary">
                <TrendingUp className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>No historical performance data available</p>
                <p className="text-sm mt-1">
                  Evaluation history will appear here when available from the backend
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Experiment Outcome Distribution */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="Distribution of experiment verdicts">
              Experiment Outcomes
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="h-72 flex items-center justify-center">
              {experimentOutcomeData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={experimentOutcomeData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={100}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                      label={({ name, percent }) =>
                        `${name} ${((percent ?? 0) * 100).toFixed(0)}%`
                      }
                      labelLine={false}
                    >
                      {experimentOutcomeData.map((entry) => (
                        <Cell
                          key={entry.name}
                          fill={entry.color}
                        />
                      ))}
                    </Pie>

                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '8px',
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="text-center text-orbit-text-tertiary">
                  <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />
                  <p>No experiment verdicts yet</p>
                  <p className="text-sm mt-1">
                    Run experiments to see their outcomes
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Mission Activity Timeline */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="Recent mission and experiment activity">
              Activity Timeline
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="h-72">
              {recentActivity.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={recentActivity
                      .slice(0, 10)
                      .reverse()
                      .map((activity) => ({
                        label: format(
                          new Date(activity.timestamp),
                          'MMM dd HH:mm'
                        ),
                        count: 1,
                        type: activity.type,
                      }))}
                    layout="vertical"
                    margin={{
                      top: 10,
                      right: 30,
                      left: 80,
                      bottom: 0,
                    }}
                  >
                    <CartesianGrid
                      strokeDasharray="3 3"
                      stroke="#1e293b"
                      horizontal={false}
                    />

                    <XAxis
                      type="number"
                      tick={{ fill: '#64748b', fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />

                    <YAxis
                      dataKey="label"
                      type="category"
                      tick={{ fill: '#64748b', fontSize: 11 }}
                      axisLine={{ stroke: '#1e293b' }}
                      tickLine={false}
                      width={80}
                    />

                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0f172a',
                        border: '1px solid #1e293b',
                        borderRadius: '8px',
                      }}
                    />

                    <Bar
                      dataKey="count"
                      radius={[0, 4, 4, 0]}
                      fill="#06b6d4"
                      maxBarSize={30}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-orbit-text-tertiary">
                  <Clock className="h-12 w-12 mb-4 opacity-30" />
                  <p>No recent activity</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Latest Evaluation Summary */}
        <Card>
          <CardHeader>
            <CardTitle subtitle="Latest evaluation and promotion decisions">
              Latest Evaluations
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-4 max-h-72 overflow-y-auto">
              {experiments.length > 0 ? (
                experiments.slice(0, 5).map((experiment) => (
                  <div
                    key={experiment.id}
                    className="flex items-center justify-between p-4 bg-orbit-bg-tertiary/50 rounded-lg border border-orbit-border-primary/50"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-orbit-bg-card border border-orbit-border-primary">
                        <StatusBadge
                          status={experiment.verdict}
                          size="sm"
                        />
                      </div>

                      <div>
                        <p className="font-mono text-sm text-orbit-text-primary">
                          {experiment.id}
                        </p>
                        <p className="text-xs text-orbit-text-tertiary">
                          {experiment.model_family || 'Unknown'} • F1:{' '}
                          {experiment.metrics?.f1?.toFixed(4) || 'N/A'}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="text-xs text-orbit-text-tertiary">
                        {format(
                          new Date(experiment.created_at),
                          'MMM dd, HH:mm'
                        )}
                      </p>
                      <StatusBadge
                        status={experiment.verdict}
                        size="sm"
                      />
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center text-orbit-text-tertiary py-8">
                  <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />
                  <p>No evaluations yet</p>
                  <p className="text-sm mt-1">
                    Experiments will appear here after evaluation
                  </p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Champion Model Panel */}
      <Card className="border-orbit-accent-primary/30 bg-orbit-accent-primary/5">
        <CardHeader>
          <CardTitle
            subtitle={
              champion
                ? `Promoted ${format(
                    new Date(champion.created_at),
                    'MMM dd, yyyy'
                  )}`
                : 'No champion model promoted yet'
            }
          >
            <div className="flex items-center gap-2">
              <Database className="h-5 w-5 text-orbit-accent-primary" />
              Champion Model
            </div>
          </CardTitle>
        </CardHeader>

        <CardContent>
          {champion ? (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  Experiment ID
                </p>
                <p className="font-mono text-orbit-text-primary">
                  {champion.id}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  F1 Score
                </p>
                <p className="text-2xl font-bold text-orbit-accent-positive">
                  {champion.metrics?.f1?.toFixed(4) || 'N/A'}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  ROC AUC
                </p>
                <p className="text-2xl font-bold text-orbit-agent-hypothesizer">
                  {champion.metrics?.roc_auc?.toFixed(4) || 'N/A'}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  Precision / Recall
                </p>
                <p className="font-mono text-orbit-text-primary">
                  {champion.metrics?.precision?.toFixed(4) || 'N/A'} /{' '}
                  {champion.metrics?.recall?.toFixed(4) || 'N/A'}
                </p>
              </div>

              <div className="md:col-span-4 pt-4 border-t border-orbit-border-primary/50">
                <p className="text-orbit-text-tertiary text-sm">
                  Artifact Path
                </p>
                <p className="font-mono text-sm text-orbit-text-secondary break-all">
                  {champion.artifact_path}
                </p>
              </div>

              {champion.diagnosis && (
                <div className="md:col-span-4 pt-4">
                  <p className="text-orbit-text-tertiary text-sm">
                    Diagnosis
                  </p>
                  <p className="text-orbit-text-secondary">
                    {champion.diagnosis}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <Database className="h-12 w-12 mx-auto mb-4 opacity-30 text-orbit-accent-primary" />
              <p className="text-orbit-text-secondary">
                No champion model has been promoted
              </p>
              <p className="text-sm text-orbit-text-tertiary mt-1">
                Run experiments and promote the best performer
              </p>

              <Button
                variant="primary"
                className="mt-4"
                onClick={() => navigate('/experiments')}
              >
                View Experiments
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Activity List */}
      <Card>
        <CardHeader>
          <CardTitle subtitle="Latest system activity">
            Recent Activity
          </CardTitle>
        </CardHeader>

        <CardContent>
          <div className="space-y-3 max-h-96 overflow-y-auto">
            {recentActivity.length > 0 ? (
              recentActivity.map((activity) => {
                const destination =
                  activity.type === 'mission'
                    ? `/missions/${activity.id.replace('mission-', '')}`
                    : activity.type === 'hypothesis'
                      ? `/hypotheses/${activity.id.replace('hypothesis-', '')}`
                      : `/experiments/${activity.id.replace('experiment-', '')}`;

                return (
                  <Link
                    key={activity.id}
                    to={destination}
                    className="flex items-center gap-4 p-3 bg-orbit-bg-tertiary/50 rounded-lg border border-orbit-border-primary/50 hover:border-orbit-border-secondary transition-colors group"
                  >
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-orbit-bg-card border border-orbit-border-primary flex-shrink-0">
                      {activity.type === 'mission' && (
                        <Target className="h-5 w-5 text-orbit-accent-primary" />
                      )}

                      {activity.type === 'hypothesis' && (
                        <Lightbulb className="h-5 w-5 text-orbit-agent-hypothesizer" />
                      )}

                      {activity.type === 'experiment' && (
                        <FlaskConical className="h-5 w-5 text-orbit-agent-experimenter" />
                      )}

                      {activity.type === 'verdict' && (
                        <CheckCircle className="h-5 w-5 text-orbit-accent-positive" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-orbit-text-primary truncate">
                        {activity.title}
                      </p>
                      <p className="text-sm text-orbit-text-tertiary truncate">
                        {activity.description}
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      {activity.status && (
                        <StatusBadge
                          status={activity.status}
                          size="sm"
                        />
                      )}

                      <span className="text-xs text-orbit-text-tertiary whitespace-nowrap">
                        {format(
                          new Date(activity.timestamp),
                          'MMM dd, HH:mm'
                        )}
                      </span>
                    </div>
                  </Link>
                );
              })
            ) : (
              <div className="text-center text-orbit-text-tertiary py-8">
                <Clock className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>No recent activity</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
