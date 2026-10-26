
// ORBIT Frontend - Experiments Page
// Experiment management with list, creation, and detail views

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus,
  Search,
  Filter,
  FlaskConical,
  Loader2,
  ExternalLink,
  ChevronDown,
  TrendingUp,
} from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';

import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';

// Validation schema
const experimentSchema = z.object({
  hypothesis_id: z.string().optional(),
  config_hash: z.string().min(1, 'Config hash is required'),
  seed: z.number().min(0),
  git_commit: z.string().min(1, 'Git commit is required'),
  git_dirty: z.boolean().default(false),
  dataset_fingerprint: z.string().min(1, 'Dataset fingerprint is required'),
  split_fingerprint: z.string().optional(),
  split_version: z.string().default('v1'),
  metrics: z.record(z.string(), z.number()),
  artifact_path: z.string().min(1, 'Artifact path is required'),
  replayable: z.boolean().default(false),
  model: z.string().optional(),
  model_family: z.string().optional(),
  feature_set: z.string().optional(),
  threshold: z.number().optional(),
  threshold_source: z.string().optional(),
  candidate_inclusive_metrics: z.record(z.string(), z.number()).default({}),
  metrics_detail: z.record(z.string(), z.unknown()).default({}),
  training: z.record(z.string(), z.unknown()).default({}),
  split_sizes: z.record(z.string(), z.number()).default({}),
  duration_seconds: z.number().default(0),
  config: z.record(z.string(), z.unknown()).default({}),
});

type ExperimentFormData = z.infer<typeof experimentSchema>;

export function Experiments() {
  const navigate = useNavigate();

  const {
    experiments,
    experimentsTotal,
    experimentsLoading,
    setExperiments,
    setExperimentsLoading,
    setExperimentsError,
    addExperiment,
  } = useOrbitStore();

  const [search, setSearch] = useState('');
  const [verdictFilter, setVerdictFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ExperimentFormData>({
    resolver: zodResolver(experimentSchema),
    defaultValues: {
      hypothesis_id: '',
      config_hash: '',
      seed: 42,
      git_commit: '',
      git_dirty: false,
      dataset_fingerprint: '',
      split_version: 'v1',
      metrics: {},
      artifact_path: '',
      replayable: false,
    },
  });

  // Load experiments when the page mounts or filter changes.
  useEffect(() => {
    const loadExperiments = async () => {
      setExperimentsLoading(true);

      try {
        const data = await apiClient.listExperiments({
          limit: 100,
          verdict: verdictFilter || undefined,
        });

        setExperiments(data.items, data.total);
      } catch (error) {
        setExperimentsError(
          error instanceof Error
            ? error.message
            : 'Failed to load experiments'
        );
        toast.error('Failed to load experiments');
      } finally {
        setExperimentsLoading(false);
      }
    };

    void loadExperiments();
  }, [
    verdictFilter,
    setExperiments,
    setExperimentsLoading,
    setExperimentsError,
  ]);

  const onCreateExperiment = async (data: ExperimentFormData) => {
    setCreating(true);

    try {
      const experiment = await apiClient.createExperiment(data);

      addExperiment(experiment);
      toast.success('Experiment registered successfully');
      setShowCreateModal(false);
      reset();

      navigate(`/experiments/${experiment.id}`);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to register experiment'
      );
    } finally {
      setCreating(false);
    }
  };

  // Filter experiments
  const filteredExperiments = experiments.filter((exp) => {
    const query = search.toLowerCase();

    const matchesSearch =
      exp.id.toLowerCase().includes(query) ||
      exp.hypothesis_id?.toLowerCase().includes(query) ||
      exp.model_family?.toLowerCase().includes(query);

    const matchesVerdict =
      !verdictFilter || exp.verdict === verdictFilter;

    return matchesSearch && matchesVerdict;
  });

  const verdictOptions = [
    { value: '', label: 'All Verdicts' },
    { value: 'KEEP', label: 'KEEP' },
    { value: 'REJECT', label: 'REJECT' },
    { value: 'PENDING', label: 'PENDING' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Experiments
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Manage and track experiment executions
          </p>
        </div>

        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          Register Experiment
        </Button>
      </div>

      {/* Search and Filter */}
      <Card className="p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary"
              aria-hidden="true"
            />
            <input
              type="text"
              placeholder="Search experiments..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field pl-10"
            />
          </div>

          <div className="relative">
            <Filter
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary"
              aria-hidden="true"
            />
            <select
              value={verdictFilter}
              onChange={(e) => setVerdictFilter(e.target.value)}
              className="input-field pl-10 pr-8 appearance-none"
            >
              {verdictOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <ChevronDown
              className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary pointer-events-none"
              aria-hidden="true"
            />
          </div>
        </div>
      </Card>

      {/* Experiments Table */}
      <Card>
        <CardContent className="p-0">
          {experimentsLoading ? (
            <div className="p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-orbit-accent-primary mx-auto mb-2" />
              <p className="text-orbit-text-secondary">
                Loading experiments...
              </p>
            </div>
          ) : filteredExperiments.length === 0 ? (
            <div className="p-8 text-center">
              <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />

              <p className="text-orbit-text-secondary">
                No experiments found
              </p>

              <p className="text-sm text-orbit-text-tertiary mt-1">
                {search || verdictFilter
                  ? 'Try adjusting your search or filter'
                  : 'Register your first experiment to get started'}
              </p>

              {!search && !verdictFilter && (
                <Button
                  variant="primary"
                  onClick={() => setShowCreateModal(true)}
                  className="mt-4"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Register Experiment
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-8"></th>
                    <th>Experiment ID</th>
                    <th>Hypothesis</th>
                    <th>Model</th>
                    <th>Verdict</th>
                    <th>F1 Score</th>
                    <th>ROC AUC</th>
                    <th>Created</th>
                    <th className="w-24">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredExperiments.map((exp) => (
                    <tr key={exp.id}>
                      <td>
                        <FlaskConical
                          className="h-5 w-5 text-orbit-agent-experimenter"
                          aria-hidden="true"
                        />
                      </td>

                      <td className="font-mono text-sm">{exp.id}</td>

                      <td className="font-mono text-sm">
                        {exp.hypothesis_id || '—'}
                      </td>

                      <td className="font-mono text-sm">
                        {exp.model_family || exp.model || '—'}
                      </td>

                      <td>
                        <StatusBadge status={exp.verdict} />
                      </td>

                      <td className="font-mono text-sm">
                        {exp.metrics?.f1?.toFixed(4) || 'N/A'}
                      </td>

                      <td className="font-mono text-sm">
                        {exp.metrics?.roc_auc?.toFixed(4) || 'N/A'}
                      </td>

                      <td className="text-sm text-orbit-text-secondary">
                        {format(
                          new Date(exp.created_at),
                          'MMM dd, yyyy HH:mm'
                        )}
                      </td>

                      <td>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`View experiment ${exp.id}`}
                            onClick={() =>
                              navigate(`/experiments/${exp.id}`)
                            }
                          >
                            <ExternalLink
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>

                          {exp.verdict === 'PENDING' && (
                            <Button
                              variant="ghost"
                              size="sm"
                              aria-label={`Promote experiment ${exp.id}`}
                              onClick={() =>
                                navigate(
                                  `/experiments/${exp.id}/promote`
                                )
                              }
                            >
                              <TrendingUp
                                className="h-4 w-4 text-orbit-accent-positive"
                                aria-hidden="true"
                              />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>

        <CardContent className="px-6 py-4 border-t border-orbit-border-primary/50">
          <div className="flex items-center justify-between">
            <p className="text-sm text-orbit-text-tertiary">
              Showing {filteredExperiments.length} of {experimentsTotal}{' '}
              experiments
            </p>

            <div className="flex gap-2">
              <Button variant="ghost" size="sm" disabled>
                Previous
              </Button>

              <Button variant="ghost" size="sm" disabled>
                Next
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Create Experiment Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Register Experiment"
        description="Record a completed experiment with its metrics and artifacts"
        size="xl"
      >
        <form
          onSubmit={handleSubmit(onCreateExperiment)}
          className="space-y-4"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Config Hash (SHA1)"
              placeholder="a1b2c3d4e5f6..."
              error={errors.config_hash?.message}
              {...register('config_hash')}
            />

            <Input
              label="Seed"
              type="number"
              error={errors.seed?.message}
              {...register('seed', { valueAsNumber: true })}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Git Commit (SHA)"
              placeholder="abcdef123456..."
              error={errors.git_commit?.message}
              {...register('git_commit')}
            />

            <Input
              label="Dataset Fingerprint"
              placeholder="sha1 fingerprint..."
              error={errors.dataset_fingerprint?.message}
              {...register('dataset_fingerprint')}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              label="Split Fingerprint (optional)"
              placeholder="sha1 fingerprint..."
              {...register('split_fingerprint')}
            />

            <Input
              label="Split Version"
              error={errors.split_version?.message}
              {...register('split_version')}
            />

            <Input
              label="Model Family"
              placeholder="gbm, cnn, etc."
              {...register('model_family')}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Input
              label="Artifact Path"
              placeholder="artifacts/run_id/"
              error={errors.artifact_path?.message}
              {...register('artifact_path')}
            />

            <Input
              label="Model Name"
              placeholder="e.g., HistGradientBoosting"
              {...register('model')}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input
              label="Feature Set"
              placeholder="catalog_v1, vetting_v1, etc."
              {...register('feature_set')}
            />

            <Input
              label="Threshold (optional)"
              type="number"
              step="0.001"
              {...register('threshold', { valueAsNumber: true })}
            />

            <Input
              label="Duration (seconds)"
              type="number"
              step="0.1"
              {...register('duration_seconds', { valueAsNumber: true })}
            />
          </div>

          <div>
            <label className="label-text">Metrics (JSON)</label>

            <textarea
              {...register('metrics', {
                setValueAs: (value: string) => {
                  try {
                    return JSON.parse(value || '{}') as Record<
                      string,
                      number
                    >;
                  } catch {
                    return value;
                  }
                },
              })}
              className="input-field font-mono text-sm min-h-[100px]"
              placeholder='{"accuracy": 0.9, "precision": 0.88, "recall": 0.92, "f1": 0.90, "roc_auc": 0.97}'
            />

            {typeof errors.metrics?.message === 'string' && (
              <p
                className="mt-1.5 text-sm text-orbit-accent-negative"
                role="alert"
              >
                {errors.metrics.message}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="replayable"
              {...register('replayable')}
              className="h-4 w-4 rounded border-orbit-border-primary text-orbit-accent-primary focus:ring-orbit-accent-primary"
            />

            <label
              htmlFor="replayable"
              className="text-sm text-orbit-text-secondary"
            >
              Replayable (run produces identical results)
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-orbit-border-primary/50">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>

            <Button
              type="submit"
              variant="primary"
              loading={creating}
            >
              Register Experiment
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
