
// ORBIT Frontend - Model Registry Page
// Champion model and candidate experiment tracking

import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Trophy,
  TrendingUp,
  TrendingDown,
  CheckCircle,
  XCircle,
} from 'lucide-react';
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
  Legend,
} from 'recharts';

import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from '@/components/ui/Card';
// import { StatusBadge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';

interface RegistryExperiment {
  id: string;
  metrics: Record<string, number>;
  verdict: string;
  created_at: string;
  model_family?: string;
  feature_set?: string;
}

interface ChampionModel {
  id: string;
  metrics: Record<string, number>;
  artifact_path: string;
  created_at: string;
  diagnosis?: string;
}

export function Registry() {
  const navigate = useNavigate();
  const { setChampion } = useOrbitStore();

  const [loading, setLoading] = useState(true);
  const [championData, setChampionData] =
    useState<ChampionModel | null>(null);
  const [candidates, setCandidates] =
    useState<RegistryExperiment[]>([]);

  const loadRegistry = useCallback(async () => {
    setLoading(true);

    try {
      try {
        const champ = await apiClient.getChampion();
        setChampionData(champ);
        setChampion(champ);
      } catch {
        setChampionData(null);
        setChampion(null);
      }

      const expData = await apiClient.listExperiments({ limit: 100 });
      setCandidates(expData.items);
    } catch {
      toast.error('Failed to load registry');
    } finally {
      setLoading(false);
    }
  }, [setChampion]);

  useEffect(() => {
    void loadRegistry();
  }, [loadRegistry]);

  const keepCandidates = candidates.filter(
    (candidate) => candidate.verdict === 'KEEP'
  );

  const rejectCandidates = candidates.filter(
    (candidate) => candidate.verdict === 'REJECT'
  );

  const pendingCandidates = candidates.filter(
    (candidate) => candidate.verdict === 'PENDING'
  );

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card className="h-24" />
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card className="h-80" />
          <Card className="h-80" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Model Registry
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Champion model and candidate experiment tracking
          </p>
        </div>

        <Button
          variant="secondary"
          onClick={() => void loadRegistry()}
        >
          Refresh Registry
        </Button>
      </div>

      {/* Champion Section */}
      <Card
        className={
          championData
            ? 'border-orbit-accent-positive/30 bg-green-500/5'
            : 'border-orbit-border-primary'
        }
      >
        <CardHeader>
          <CardTitle
            subtitle={
              championData
                ? `Promoted ${format(
                    new Date(championData.created_at),
                    'MMM dd, yyyy HH:mm'
                  )}`
                : 'No champion model promoted yet'
            }
          >
            <div className="flex items-center gap-2">
              <Trophy className="h-5 w-5 text-orbit-accent-positive" />
              Champion Model
            </div>
          </CardTitle>
        </CardHeader>

        <CardContent>
          {championData ? (
            <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 gap-6">
              <div className="md:col-span-2 lg:col-span-2">
                <p className="text-orbit-text-tertiary text-sm">
                  Experiment ID
                </p>
                <p className="font-mono text-orbit-text-primary text-lg">
                  {championData.id}
                </p>
                <p className="text-xs text-orbit-text-tertiary mt-1 break-all">
                  Artifact: {championData.artifact_path}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  F1 Score
                </p>
                <p className="text-3xl font-bold text-orbit-accent-positive mt-1">
                  {championData.metrics?.f1?.toFixed(4) || 'N/A'}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  ROC AUC
                </p>
                <p className="text-3xl font-bold text-orbit-agent-hypothesizer mt-1">
                  {championData.metrics?.roc_auc?.toFixed(4) || 'N/A'}
                </p>
              </div>

              <div>
                <p className="text-orbit-text-tertiary text-sm">
                  Precision / Recall
                </p>
                <p className="font-mono text-orbit-text-primary mt-1">
                  {championData.metrics?.precision?.toFixed(4) || 'N/A'} /{' '}
                  {championData.metrics?.recall?.toFixed(4) || 'N/A'}
                </p>
              </div>

              {championData.diagnosis && (
                <div className="md:col-span-4 lg:col-span-5 pt-4 border-t border-orbit-border-primary/50">
                  <p className="text-orbit-text-tertiary text-sm">
                    Diagnosis
                  </p>
                  <p className="text-orbit-text-secondary">
                    {championData.diagnosis}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12">
              <Trophy className="h-16 w-16 mx-auto mb-4 opacity-30 text-orbit-accent-positive" />
              <p className="text-orbit-text-secondary text-lg">
                No champion model yet
              </p>
              <p className="text-sm text-orbit-text-tertiary mt-1">
                Promote a KEEP experiment to establish the champion
              </p>
              <Button
                variant="primary"
                className="mt-4"
                onClick={() => navigate('/experiments')}
              >
                Browse Experiments
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Metrics Comparison Chart */}
      {championData && keepCandidates.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle subtitle="Comparing champion against KEEP candidates">
              Performance Comparison
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={[
                    {
                      model: 'Champion',
                      f1: championData.metrics?.f1 || 0,
                      auc: championData.metrics?.roc_auc || 0,
                    },
                    ...keepCandidates.slice(0, 8).map((candidate) => ({
                      model:
                        candidate.id.length > 20
                          ? `${candidate.id.substring(0, 20)}...`
                          : candidate.id,
                      f1: candidate.metrics?.f1 || 0,
                      auc: candidate.metrics?.roc_auc || 0,
                    })),
                  ]}
                  layout="vertical"
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
                    domain={[0, 1]}
                  />
                  <YAxis
                    dataKey="model"
                    type="category"
                    tick={{ fill: '#64748b', fontSize: 11 }}
                    axisLine={{ stroke: '#1e293b' }}
                    tickLine={false}
                    width={180}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      border: '1px solid #1e293b',
                      borderRadius: '8px',
                    }}
                  />
                  <Legend
                    wrapperStyle={{ paddingTop: '20px' }}
                    layout="horizontal"
                    align="center"
                  />
                  <Bar
                    dataKey="f1"
                    name="F1 Score"
                    radius={[0, 4, 4, 0]}
                    fill="#06b6d4"
                    maxBarSize={20}
                  />
                  <Bar
                    dataKey="auc"
                    name="ROC AUC"
                    radius={[0, 4, 4, 0]}
                    fill="#a855f7"
                    maxBarSize={20}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Candidate Sections */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* KEEP Candidates */}
        <Card>
          <CardHeader>
            <CardTitle
              subtitle={`${keepCandidates.length} KEEP candidates`}
            >
              <div className="flex items-center gap-2">
                <CheckCircle className="h-5 w-5 text-orbit-accent-positive" />
                KEEP Candidates
              </div>
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {keepCandidates.length > 0 ? (
                keepCandidates.map((candidate) => (
                  <Link
                    key={candidate.id}
                    to={`/experiments/${candidate.id}`}
                    className="flex items-center justify-between p-3 bg-orbit-bg-tertiary/50 rounded-lg border border-orbit-border-primary/50 hover:border-orbit-border-secondary transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-orbit-bg-card border border-orbit-border-primary">
                        <TrendingUp className="h-5 w-5 text-orbit-accent-positive" />
                      </div>

                      <div>
                        <p className="font-mono text-sm text-orbit-text-primary">
                          {candidate.id}
                        </p>
                        <p className="text-xs text-orbit-text-tertiary">
                          {candidate.model_family || 'Unknown'} •{' '}
                          {candidate.feature_set || 'Unknown'}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="font-mono text-sm text-orbit-accent-positive">
                        F1: {candidate.metrics?.f1?.toFixed(4) || 'N/A'}
                      </p>
                      <p className="text-xs text-orbit-text-tertiary">
                        AUC: {candidate.metrics?.roc_auc?.toFixed(4) || 'N/A'}
                      </p>
                      <p className="text-xs text-orbit-text-tertiary">
                        {format(
                          new Date(candidate.created_at),
                          'MMM dd, HH:mm'
                        )}
                      </p>
                    </div>
                  </Link>
                ))
              ) : (
                <p className="text-orbit-text-tertiary text-center py-8">
                  No KEEP candidates yet
                </p>
              )}
            </div>
          </CardContent>
        </Card>

        {/* REJECT Candidates */}
        <Card>
          <CardHeader>
            <CardTitle
              subtitle={`${rejectCandidates.length} rejected candidates`}
            >
              <div className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-orbit-accent-negative" />
                REJECT Candidates
              </div>
            </CardTitle>
          </CardHeader>

          <CardContent>
            <div className="space-y-3 max-h-96 overflow-y-auto">
              {rejectCandidates.length > 0 ? (
                rejectCandidates.slice(0, 20).map((candidate) => (
                  <Link
                    key={candidate.id}
                    to={`/experiments/${candidate.id}`}
                    className="flex items-center justify-between p-3 bg-orbit-bg-tertiary/50 rounded-lg border border-orbit-border-primary/50 hover:border-orbit-border-secondary transition-colors group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg flex items-center justify-center bg-orbit-bg-card border border-orbit-border-primary">
                        <TrendingDown className="h-5 w-5 text-orbit-accent-negative" />
                      </div>

                      <div>
                        <p className="font-mono text-sm text-orbit-text-primary">
                          {candidate.id}
                        </p>
                        <p className="text-xs text-orbit-text-tertiary">
                          {candidate.model_family || 'Unknown'} •{' '}
                          {candidate.feature_set || 'Unknown'}
                        </p>
                      </div>
                    </div>

                    <div className="text-right">
                      <p className="font-mono text-sm text-orbit-accent-negative">
                        F1: {candidate.metrics?.f1?.toFixed(4) || 'N/A'}
                      </p>
                      <p className="text-xs text-orbit-text-tertiary">
                        AUC: {candidate.metrics?.roc_auc?.toFixed(4) || 'N/A'}
                      </p>
                      <p className="text-xs text-orbit-text-tertiary">
                        {format(
                          new Date(candidate.created_at),
                          'MMM dd, HH:mm'
                        )}
                      </p>
                    </div>
                  </Link>
                ))
              ) : (
                <p className="text-orbit-text-tertiary text-center py-8">
                  No REJECT candidates yet
                </p>
              )}

              {rejectCandidates.length > 20 && (
                <p className="text-center text-xs text-orbit-text-tertiary mt-2">
                  Showing 20 of {rejectCandidates.length} rejected candidates
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Verdict Distribution */}
      <Card>
        <CardHeader>
          <CardTitle subtitle="Overall experiment verdict distribution">
            Verdict Summary
          </CardTitle>
        </CardHeader>

        <CardContent>
          <div className="grid grid-cols-3 gap-6">
            <div className="text-center p-4 bg-green-500/10 border border-green-500/20 rounded-xl">
              <p className="text-3xl font-bold text-orbit-accent-positive">
                {keepCandidates.length}
              </p>
              <p className="text-orbit-text-tertiary mt-1">KEEP</p>
            </div>

            <div className="text-center p-4 bg-red-500/10 border border-red-500/20 rounded-xl">
              <p className="text-3xl font-bold text-orbit-accent-negative">
                {rejectCandidates.length}
              </p>
              <p className="text-orbit-text-tertiary mt-1">REJECT</p>
            </div>

            <div className="text-center p-4 bg-amber-500/10 border border-amber-500/20 rounded-xl">
              <p className="text-3xl font-bold text-orbit-accent-warning">
                {pendingCandidates.length}
              </p>
              <p className="text-orbit-text-tertiary mt-1">PENDING</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
