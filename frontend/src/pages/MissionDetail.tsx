
 // ORBIT Frontend - Mission Detail Page
 // Detailed view of a single mission with hypotheses, experiments, and activity

import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Target,
  Lightbulb,
  FlaskConical,
  ArrowLeft,
  Edit,
  Plus,
  ExternalLink,
} from 'lucide-react';
import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { StatusBadge } from '@/components/ui/Badge';
import { Input, Textarea } from '@/components/ui/Input';
import { Modal } from '@/components/ui/Modal';
import { format } from 'date-fns';
import { toast } from 'sonner';
import { Tabs, TabList, TabTrigger, TabContent } from '@/components/ui/Tabs';

// Validation schema for hypothesis creation
const hypothesisSchema = z.object({
  proposal_json: z.object({
    title: z.string().min(1, 'Title is required'),
    description: z.string().min(1, 'Description is required'),
    expected_f1_gain: z.number().optional(),
    config_changes: z.record(z.unknown()).optional(),
  }),
});

type HypothesisFormData = z.infer<typeof hypothesisSchema>;

export function MissionDetail() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();

  const { currentMission, setCurrentMission, addHypothesis } = useOrbitStore();

  const [loading, setLoading] = useState(true);
  const [creatingHypothesis, setCreatingHypothesis] = useState(false);
  const [showHypothesisModal, setShowHypothesisModal] = useState(false);
  const [activeTab, setActiveTab] = useState('overview');

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<HypothesisFormData>({
    resolver: zodResolver(hypothesisSchema),
    defaultValues: {
      proposal_json: {
        title: '',
        description: '',
        expected_f1_gain: undefined,
        config_changes: {},
      },
    },
  });

  // Load mission detail on mount
  useEffect(() => {
    if (missionId) {
      void loadMission();
    }
  }, [missionId]);

  const loadMission = async () => {
    if (!missionId) return;

    setLoading(true);

    try {
      const mission = await apiClient.getMission(missionId);
      setCurrentMission(mission);
    } catch {
      toast.error('Failed to load mission');
      navigate('/missions');
    } finally {
      setLoading(false);
    }
  };

  const onCreateHypothesis = async (data: HypothesisFormData) => {
    if (!missionId) return;

    setCreatingHypothesis(true);

    try {
      const hypothesis = await apiClient.createHypothesis({
        mission_id: missionId,
        proposal_json: data.proposal_json,
      });

      addHypothesis(hypothesis);
      toast.success('Hypothesis created successfully');
      setShowHypothesisModal(false);
      reset();
      setActiveTab('hypotheses');
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to create hypothesis'
      );
    } finally {
      setCreatingHypothesis(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <Card className="h-24" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <Card className="h-64" />
          <Card className="lg:col-span-2 h-64" />
        </div>
      </div>
    );
  }

  if (!currentMission) {
    return (
      <div className="text-center py-12">
        <Target className="h-12 w-12 mx-auto mb-4 opacity-30" />
        <p className="text-orbit-text-secondary">Mission not found</p>
        <Button
          variant="primary"
          className="mt-4"
          onClick={() => navigate('/missions')}
        >
          Back to Missions
        </Button>
      </div>
    );
  }

  const { hypotheses, attempts } = currentMission;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate('/missions')}
          >
            <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          </Button>

          <div>
            <h1 className="text-3xl font-bold text-orbit-text-primary">
              {currentMission.id}
            </h1>
            <p className="text-orbit-text-secondary mt-1">
              {currentMission.question}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <StatusBadge status={currentMission.status} size="lg" />

          <Button
            variant="secondary"
            onClick={() => navigate(`/missions/${currentMission.id}/edit`)}
          >
            <Edit className="h-4 w-4" aria-hidden="true" />
            Edit
          </Button>
        </div>
      </div>

      {/* Mission Meta */}
      <Card className="p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-orbit-text-tertiary">Budget Rounds</p>
            <p className="font-mono text-orbit-text-primary">
              {currentMission.current_round} / {currentMission.budget_rounds}
            </p>
          </div>

          <div>
            <p className="text-orbit-text-tertiary">Hypotheses</p>
            <p className="font-mono text-orbit-text-primary">
              {hypotheses.length}
            </p>
          </div>

          <div>
            <p className="text-orbit-text-tertiary">Experiments</p>
            <p className="font-mono text-orbit-text-primary">
              {attempts.length}
            </p>
          </div>

          <div>
            <p className="text-orbit-text-tertiary">Created</p>
            <p className="font-mono text-orbit-text-primary">
              {format(new Date(currentMission.created_at), 'MMM dd, yyyy HH:mm')}
            </p>
          </div>
        </div>
      </Card>

      {/* Tabs */}
      <Tabs
        value={activeTab}
        onValueChange={(value: string) => setActiveTab(value)}
      >
        <TabList>
          <TabTrigger value="overview">Overview</TabTrigger>
          <TabTrigger value="hypotheses">
            Hypotheses ({hypotheses.length})
          </TabTrigger>
          <TabTrigger value="experiments">
            Experiments ({attempts.length})
          </TabTrigger>
          <TabTrigger value="activity">Activity</TabTrigger>
        </TabList>

        {/* Overview */}
        <TabContent value="overview">
          <div className="space-y-6 mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Mission Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-orbit-text-secondary whitespace-pre-wrap">
                  {currentMission.question}
                </p>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle>Hypothesis Status</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {hypotheses.length > 0 ? (
                      hypotheses.map((hypothesis) => (
                        <div
                          key={hypothesis.id}
                          className="flex items-center justify-between p-3 bg-orbit-bg-tertiary/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <Lightbulb className="h-5 w-5 text-orbit-agent-hypothesizer" />
                            <span className="font-mono text-sm">
                              {hypothesis.id}
                            </span>
                          </div>
                          <StatusBadge status={hypothesis.status} />
                        </div>
                      ))
                    ) : (
                      <p className="text-orbit-text-tertiary text-center py-4">
                        No hypotheses yet
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Execution Attempts</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {attempts.length > 0 ? (
                      attempts.slice(0, 5).map((attempt) => (
                        <div
                          key={attempt.id}
                          className="flex items-center justify-between p-3 bg-orbit-bg-tertiary/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <FlaskConical className="h-5 w-5 text-orbit-agent-experimenter" />
                            <span className="font-mono text-sm">
                              {attempt.id}
                            </span>
                          </div>
                          <StatusBadge status={attempt.execution_status} />
                        </div>
                      ))
                    ) : (
                      <p className="text-orbit-text-tertiary text-center py-4">
                        No execution attempts yet
                      </p>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
        </TabContent>

        {/* Hypotheses */}
        <TabContent value="hypotheses">
          <div className="mt-6 space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-semibold">Hypotheses</h3>
              <Button onClick={() => setShowHypothesisModal(true)}>
                <Plus className="h-4 w-4" aria-hidden="true" />
                New Hypothesis
              </Button>
            </div>

            {hypotheses.length > 0 ? (
              <div className="space-y-3">
                {hypotheses.map((hypothesis) => (
                  <Card
                    key={hypothesis.id}
                    className="p-4 hover:border-orbit-border-secondary transition-colors"
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <Lightbulb className="h-5 w-5 text-orbit-agent-hypothesizer" />
                          <span className="font-mono text-sm">
                            {hypothesis.id}
                          </span>
                          <StatusBadge status={hypothesis.status} />
                        </div>

                        <p className="text-sm text-orbit-text-tertiary">
                          Created {format(
                            new Date(hypothesis.created_at),
                            'MMM dd, yyyy HH:mm'
                          )}
                        </p>
                      </div>

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => navigate(`/hypotheses/${hypothesis.id}`)}
                        aria-label={`View hypothesis ${hypothesis.id}`}
                      >
                        <ExternalLink className="h-4 w-4" aria-hidden="true" />
                        View
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="p-8 text-center">
                <Lightbulb className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-orbit-text-secondary">
                  No hypotheses proposed yet
                </p>
                <p className="text-sm text-orbit-text-tertiary mt-1">
                  Create a hypothesis to begin research
                </p>
                <Button
                  variant="primary"
                  onClick={() => setShowHypothesisModal(true)}
                  className="mt-4"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Propose Hypothesis
                </Button>
              </Card>
            )}
          </div>
        </TabContent>

        {/* Experiments */}
        <TabContent value="experiments">
          <div className="mt-6 space-y-4">
            <h3 className="text-lg font-semibold">Execution Attempts</h3>

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
                            aria-label={`Open artifacts for ${attempt.id}`}
                            onClick={() =>
                              window.open(
                                attempt.artifact_path,
                                '_blank',
                                'noopener,noreferrer'
                              )
                            }
                          >
                            <ExternalLink className="h-4 w-4" aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Card className="p-8 text-center">
                <FlaskConical className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p className="text-orbit-text-secondary">
                  No execution attempts yet
                </p>
              </Card>
            )}
          </div>
        </TabContent>

        {/* Activity */}
        <TabContent value="activity">
          <div className="mt-6">
            <Card>
              <CardHeader>
                <CardTitle>Mission Activity</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {[
                    ...hypotheses.map((hypothesis) => ({
                      id: hypothesis.id,
                      type: 'hypothesis' as const,
                      title: 'Hypothesis Proposed',
                      time: hypothesis.created_at,
                    })),
                    ...attempts.map((attempt) => ({
                      id: attempt.id,
                      type: 'experiment' as const,
                      title: 'Experiment Executed',
                      time: attempt.created_at,
                    })),
                  ]
                    .sort(
                      (a, b) =>
                        new Date(b.time).getTime() -
                        new Date(a.time).getTime()
                    )
                    .map((activity) => (
                      <div
                        key={activity.id}
                        className="flex items-center gap-4 p-3 bg-orbit-bg-tertiary/50 rounded-lg"
                      >
                        <div className="w-8 h-8 rounded-full flex items-center justify-center bg-orbit-bg-card border border-orbit-border-primary flex-shrink-0">
                          {activity.type === 'hypothesis' && (
                            <Lightbulb className="h-4 w-4 text-orbit-agent-hypothesizer" />
                          )}
                          {activity.type === 'experiment' && (
                            <FlaskConical className="h-4 w-4 text-orbit-agent-experimenter" />
                          )}
                        </div>

                        <div className="flex-1">
                          <p className="font-medium text-orbit-text-primary">
                            {activity.title}
                          </p>
                          <p className="text-sm text-orbit-text-tertiary">
                            {activity.id}
                          </p>
                        </div>

                        <span className="text-xs text-orbit-text-tertiary whitespace-nowrap">
                          {format(
                            new Date(activity.time),
                            'MMM dd, yyyy HH:mm:ss'
                          )}
                        </span>
                      </div>
                    ))}

                  {hypotheses.length === 0 && attempts.length === 0 && (
                    <p className="text-orbit-text-tertiary text-center py-8">
                      No activity yet
                    </p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabContent>
      </Tabs>

      {/* Create Hypothesis Modal */}
      <Modal
        isOpen={showHypothesisModal}
        onClose={() => setShowHypothesisModal(false)}
        title="Propose New Hypothesis"
        description="Define a research hypothesis for this mission"
        size="lg"
      >
        <form
          onSubmit={handleSubmit(onCreateHypothesis)}
          className="space-y-4"
        >
          <Input
            label="Title"
            placeholder="Brief title for this hypothesis"
            error={errors.proposal_json?.title?.message}
            {...register('proposal_json.title')}
          />

          <Textarea
            label="Description"
            placeholder="Detailed description of the hypothesis and expected outcome"
            rows={4}
            error={errors.proposal_json?.description?.message}
            {...register('proposal_json.description')}
          />

          <Input
            label="Expected F1 Gain"
            placeholder="0.05"
            type="number"
            step="0.01"
            {...register('proposal_json.expected_f1_gain', {
              setValueAs: (value: string) =>
                value === '' ? undefined : Number(value),
            })}
          />

          <div className="flex justify-end gap-3 pt-4 border-t border-orbit-border-primary/50">
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowHypothesisModal(false)}
            >
              Cancel
            </Button>

            <Button
              type="submit"
              variant="primary"
              loading={creatingHypothesis}
            >
              Create Hypothesis
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
