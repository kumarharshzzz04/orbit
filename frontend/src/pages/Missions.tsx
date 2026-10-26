
// ORBIT Frontend - Missions Page
// Mission management with list, creation, and detail views

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import {
  Plus,
  Search,
  Filter,
  ChevronDown,
  Target,
  Loader2,
  Edit,
  Trash2,
  ExternalLink,
} from 'lucide-react';

import { apiClient } from '@/api/client';
import { useOrbitStore } from '@/stores/useOrbitStore';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {  Textarea } from '@/components/ui/Input';
import { StatusBadge } from '@/components/ui/Badge';
import { Modal, ConfirmDialog } from '@/components/ui/Modal';
import { format } from 'date-fns';
import { toast } from 'sonner';

// Validation schema
const missionSchema = z.object({
  question: z
    .string()
    .min(1, 'Research question is required')
    .max(1000, 'Question too long'),
  budget_rounds: z
    .number()
    .min(1, 'At least 1 round')
    .max(10, 'Maximum 10 rounds'),
});

type MissionFormData = z.infer<typeof missionSchema>;

export function Missions() {
  const navigate = useNavigate();

  const {
    missions,
    missionsTotal,
    missionsLoading,
    setMissions,
    setMissionsLoading,
    setMissionsError,
    addMission,
    removeMission,
  } = useOrbitStore();

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<MissionFormData>({
    resolver: zodResolver(missionSchema),
    defaultValues: {
      question: '',
      budget_rounds: 2,
    },
  });

  // Load missions on mount
  useEffect(() => {
    void loadMissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadMissions = async () => {
    setMissionsLoading(true);

    try {
      const data = await apiClient.listMissions({
        limit: 100,
        status: statusFilter || undefined,
      });

      setMissions(data.items, data.total);
    } catch (error) {
      setMissionsError(
        error instanceof Error ? error.message : 'Failed to load missions'
      );
      toast.error('Failed to load missions');
    } finally {
      setMissionsLoading(false);
    }
  };

  const onCreateMission = async (data: MissionFormData) => {
    setCreating(true);

    try {
      const mission = await apiClient.createMission(data);

      addMission(mission);
      toast.success('Mission created successfully');
      setShowCreateModal(false);
      reset();
      navigate(`/missions/${mission.id}`);
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to create mission'
      );
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (missionId: string) => {
    setDeletingId(missionId);

    try {
      // The backend currently has no DELETE endpoint.
      // This removes the mission from the local store only.
      removeMission(missionId);
      toast.success('Mission removed from the current view');
    } catch {
      toast.error('Failed to remove mission');
    } finally {
      setDeletingId(null);
    }
  };

  // Filter missions based on search
  const filteredMissions = missions.filter((mission) => {
    const matchesSearch =
      mission.question.toLowerCase().includes(search.toLowerCase()) ||
      mission.id.toLowerCase().includes(search.toLowerCase());

    const matchesStatus =
      !statusFilter || mission.status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  const statusOptions = [
    { value: '', label: 'All Statuses' },
    { value: 'pending', label: 'Pending' },
    { value: 'running', label: 'Running' },
    { value: 'completed', label: 'Completed' },
    { value: 'failed', label: 'Failed' },
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-orbit-text-primary">
            Missions
          </h1>
          <p className="text-orbit-text-secondary mt-1">
            Manage research missions and track progress
          </p>
        </div>

        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Mission
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
              placeholder="Search missions..."
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
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="input-field pl-10 pr-8 appearance-none"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
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

      {/* Missions Table */}
      <Card>
        <CardContent className="p-0">
          {missionsLoading ? (
            <div className="p-8 text-center">
              <Loader2 className="h-8 w-8 animate-spin text-orbit-accent-primary mx-auto mb-2" />
              <p className="text-orbit-text-secondary">
                Loading missions...
              </p>
            </div>
          ) : filteredMissions.length === 0 ? (
            <div className="p-8 text-center">
              <Target className="h-12 w-12 mx-auto mb-4 opacity-30" />

              <p className="text-orbit-text-secondary">
                No missions found
              </p>

              <p className="text-sm text-orbit-text-tertiary mt-1">
                {search || statusFilter
                  ? 'Try adjusting your search or filter'
                  : 'Create your first mission to get started'}
              </p>

              {!search && !statusFilter && (
                <Button
                  variant="primary"
                  className="mt-4"
                  onClick={() => setShowCreateModal(true)}
                >
                  Create Mission
                </Button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th className="w-8"></th>
                    <th>Mission ID</th>
                    <th>Research Question</th>
                    <th>Status</th>
                    <th>Rounds</th>
                    <th>Created</th>
                    <th className="w-32">Actions</th>
                  </tr>
                </thead>

                <tbody>
                  {filteredMissions.map((mission) => (
                    <tr key={mission.id}>
                      <td>
                        <Target
                          className="h-5 w-5 text-orbit-accent-primary"
                          aria-hidden="true"
                        />
                      </td>

                      <td className="font-mono text-sm">
                        {mission.id}
                      </td>

                      <td className="max-w-xs truncate">
                        {mission.question}
                      </td>

                      <td>
                        <StatusBadge status={mission.status} />
                      </td>

                      <td>
                        <span className="font-mono text-sm">
                          {mission.current_round} / {mission.budget_rounds}
                        </span>
                      </td>

                      <td className="text-sm text-orbit-text-secondary">
                        {format(
                          new Date(mission.created_at),
                          'MMM dd, yyyy HH:mm'
                        )}
                      </td>

                      <td>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`View mission ${mission.id}`}
                            onClick={() => navigate(`/missions/${mission.id}`)}
                          >
                            <ExternalLink
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit mission ${mission.id}`}
                            onClick={() =>
                              navigate(`/missions/${mission.id}/edit`)
                            }
                          >
                            <Edit
                              className="h-4 w-4"
                              aria-hidden="true"
                            />
                          </Button>

                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeletingId(mission.id)}
                            disabled={deletingId === mission.id}
                            aria-label={`Delete mission ${mission.id}`}
                          >
                            <Trash2
                              className="h-4 w-4 text-orbit-accent-negative"
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
              Showing {filteredMissions.length} of {missionsTotal} missions
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

      {/* Create Mission Modal */}
      <Modal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        title="Create New Mission"
        description="Define a new research mission for autonomous exploration"
        size="lg"
      >
        <form
          onSubmit={handleSubmit(onCreateMission)}
          className="space-y-4"
        >
          <Textarea
            label="Research Question"
            placeholder="What scientific question should this mission investigate?"
            error={errors.question?.message}
            rows={3}
            {...register('question')}
          />

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label-text">Budget Rounds</label>

              <select
                {...register('budget_rounds', { valueAsNumber: true })}
                className="input-field"
              >
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((n) => (
                  <option key={n} value={n}>
                    {n} round{n > 1 ? 's' : ''}
                  </option>
                ))}
              </select>
            </div>
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
              Create Mission
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation */}
      <ConfirmDialog
        isOpen={!!deletingId}
        onClose={() => setDeletingId(null)}
        onConfirm={() => {
          if (deletingId) {
            void handleDelete(deletingId);
          }
        }}
        title="Delete Mission"
        message="Are you sure you want to delete this mission? This action cannot be undone."
        confirmText="Delete"
        variant="danger"
        loading={deletingId !== null}
      />
    </div>
  );
}
