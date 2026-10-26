
// ORBIT Frontend - Hypotheses Page
// Hypothesis management with list, creation, and detail views

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus,
  Search,
  Filter,
  Lightbulb,
  Loader2,
  Edit,
  ExternalLink,
  ChevronDown,
} from 'lucide-react';
import { format } from 'date-fns';
import { toast } from 'sonner';

import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Input, Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/Badge';
import { Modal } from '@/components/ui/Modal';

// Validation schema
const hypothesisSchema = z.object({
  mission_id: z.string().min(1, 'Mission is required'),
  proposal_json: z.object({
    title: z.string().min(1, 'Title is required'),
    description: z.string().min(1, 'Description is required'),
    expected_f1_gain: z.number().optional(),
    config_changes: z.record(z.unknown()).optional(),
  }),
});

type HypothesisFormData = z.infer<typeof hypothesisSchema>;

export function Hypotheses() {
  const navigate = useNavigate();

  const {
    missions,
    hypotheses,
    hypothesesTotal,
    hypothesesLoading,
    setHypotheses,
    setHypothesesLoading,
    setHypothesesError,
    addHypothesis,
  } = useOrbitStore();

  const [missionOptions, setMissionOptions] = useState(missions);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [missionFilter, setMissionFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<HypothesisFormData>({
    resolver: zodResolver(hypothesisSchema),
    defaultValues: {
      mission_id: '',
      proposal_json: {
        title: '',
        description: '',
        config_changes: {},
      },
    },
  });

  // Load hypotheses when filters change.
  useEffect(() => {
    let active = true;

    const loadHypotheses = async () => {
      setHypothesesLoading(true);

      try {
        const response = await apiClient.listHypotheses({
          limit: 100,
          status: statusFilter || undefined,
          mission_id: missionFilter || undefined,
        });

        if (active) {
          setHypotheses(response.items, response.total);
        }
      } catch (error) {
        if (active) {
          setHypothesesError(
            error instanceof Error
              ? error.message
              : 'Failed to load hypotheses'
          );
          toast.error('Failed to load hypotheses');
        }
      } finally {
        if (active) {
          setHypothesesLoading(false);
        }
      }
    };

    void loadHypotheses();

    return () => {
      active = false;
    };
  }, [
    statusFilter,
    missionFilter,
    setHypotheses,
    setHypothesesLoading,
    setHypothesesError,
  ]);

  // Load available missions for the creation form.
  useEffect(() => {
    let active = true;

    const loadMissionsForSelect = async () => {
      try {
        const response = await apiClient.listMissions({ limit: 100 });

        if (active) {
          setMissionOptions(response.items);
        }
      } catch (error) {
        console.error('Failed to load missions for select:', error);
      }
    };

    void loadMissionsForSelect();

    return () => {
      active = false;
    };
  }, []);

  const onCreateHypothesis = async (data: HypothesisFormData) => {
    setCreating(true);

    try {
      const hypothesis = await apiClient.createHypothesis({
        mission_id: data.mission_id,
        proposal_json: data.proposal_json,
      });

      addHypothesis(hypothesis);
      toast.success('Hypothesis created successfully');
      setShowCreateModal(false);
      reset();

      navigate(`/hypotheses/${hypothesis.id}`);
    } catch (error) {
      toast.error(
        error instanceof Error
          ? error.message
          : 'Failed to create hypothesis'
      );
    } finally {
      setCreating(false);
    }
  };

  // Filter hypotheses
  const filteredHypotheses = hypotheses.filter((hypothesis) => {
    const matchesSearch = hypothesis.id
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesStatus =
      !statusFilter || hypothesis.status === statusFilter;

    const matchesMission =
      !missionFilter || hypothesis.mission_id === missionFilter;

    return matchesSearch && matchesStatus && matchesMission;
  });

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'proposed', label: 'Proposed' },
    { value: 'approved', label: 'Approved' },
    { value: 'vetoed', label: 'Vetoed' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Hypotheses
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Manage research hypotheses across missions
          </p>
        </div>

        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Hypothesis
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
              placeholder="Search hypotheses..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              className="input-field pl-10"
            />
          </div>

          <div className="relative">
            <Filter
              className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-orbit-text-tertiary"
              aria-hidden="true"
            />

            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="input-field pl-10 pr-8 appearance-none"
            >
              {statusOptions.map((option) => (
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

          <div className="relative">
            <select
              value={missionFilter}
              onChange={(event) => setMissionFilter(event.target.value)}
              className="input-field pr-8 appearance-none"
            >
              <option value="">All Missions</option>

              {missions.map((mission) => (
                <option key={mission.id} value={mission.id}>
                  {mission.id}
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

      {/* Hypotheses Table */}
      <Card>
        <CardContent className="p-0">
          {hypothesesLoading ? (
            <div className="p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-orbit-accent-primary mx-auto mb-2" />
              <p className="text-orbit-text-secondary">
                Loading hypotheses...
              </p>
            </div>
          ) : filteredHypotheses.length === 0 ? (
            <div className="p-8 text-center">
              <Lightbulb className="h-12 w-12 mx-auto mb-4 opacity-30" />

              <p className="text-orbit-text-secondary">
                No hypotheses found
              </p>

              <p className="text-sm text-orbit-text-tertiary mt-1">
                {search || statusFilter || missionFilter
                  ? 'Try adjusting your search or filter'
                  : 'Create your first hypothesis to get started'}
              </p>

              {!search && !statusFilter && !missionFilter && (
                <Button
                  variant="primary"
                  onClick={() => setShowCreateModal(true)}
                  className="mt-4"
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  Create Hypothesis
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-8"></th>
                    <th>Hypothesis ID</th>
                    <th>Mission</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th className="w-24">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredHypotheses.map((hypothesis) => (
                    <tr key={hypothesis.id}>
                      <td>
                        <Lightbulb
                          className="h-5 w-5 text-orbit-agent-hypothesizer"
                          aria-hidden="true"
                        />
                      </td>

                      <td className="font-mono text-sm">
                        {hypothesis.id}
                      </td>

                      <td className="font-mono text-sm">
                        {hypothesis.mission_id}
                      </td>

                      <td>
                        <StatusBadge status={hypothesis.status} />
                      </td>

                      <td className="text-sm text-orbit-text-secondary">
                        {format(
                          new Date(hypothesis.created_at),
                          'MMM dd, yyyy HH:mm'
                        )}
                      </td>

                      <td>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`View hypothesis ${hypothesis.id}`}
                            onClick={() =>
                              navigate(`/hypotheses/${hypothesis.id}`)
                            }
                          >
                            <ExternalLink
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit hypothesis ${hypothesis.id}`}
                            onClick={() =>
                              navigate(
                                `/hypotheses/${hypothesis.id}/edit`
                              )
                            }
                          >
                            <Edit
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>
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
              Showing {filteredHypotheses.length} of {hypothesesTotal}{' '}
              hypotheses
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

      {/* Create Hypothesis Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Propose New Hypothesis"
        description="Define a research hypothesis for investigation"
        size="lg"
      >
        <form
          onSubmit={handleSubmit(onCreateHypothesis)}
          className="space-y-4"
        >
          <div>
            <label className="label-text" htmlFor="mission_id">
              Mission
            </label>

            <select
              id="mission_id"
              {...register('mission_id')}
              className="input-field"
              required
            >
              <option value="">Select a mission</option>

              {missionOptions.map((mission) => (
                <option key={mission.id} value={mission.id}>
                  {mission.id} — {mission.question.substring(0, 60)}...
                </option>
              ))}
            </select>

            {errors.mission_id?.message && (
              <p
                className="mt-1.5 text-sm text-orbit-accent-negative"
                role="alert"
              >
                {errors.mission_id.message}
              </p>
            )}
          </div>

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
            label="Expected F1 Gain (optional)"
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
              onClick={() => setShowCreateModal(false)}
            >
              Cancel
            </Button>

            <Button
              type="submit"
              variant="primary"
              loading={creating}
            >
              Create Hypothesis
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
