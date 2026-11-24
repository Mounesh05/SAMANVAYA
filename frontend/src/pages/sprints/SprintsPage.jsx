import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { sprintsApi } from '../../api/sprints.api';
import { projectsApi } from '../../api/projects.api';
import { useSessionScope } from '../../store/useSessionScope';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { ProgressBar } from '../../components/common/ProgressBar';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { Plus, Activity, AlertTriangle, Play, CheckCircle2 } from 'lucide-react';
import { formatDate } from '../../utils/dates';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS, hasPermission } from '../../auth/permissions';
import { useAuthStore } from '../../store/useAuthStore';

export function SprintsPage() {
  const sessionScope = useSessionScope();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedHealthSprint, setSelectedHealthSprint] = useState(null);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [completing, setCompleting] = useState(null);
  const { user } = useAuthStore();
  // Same permission the backend checks for creating, starting and completing sprints.
  const canManageSprints = hasPermission(user, PERMISSIONS.CREATE_SPRINT);

  const [formData, setFormData] = useState({
    name: '',
    project_id: '',
    goal: '',
    start_date: '',
    end_date: '',
  });

  const queryClient = useQueryClient();

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'list', sessionScope],
    queryFn: () => projectsApi.list(),
  });

  // Select first project by default if available
  const activeProjectId = selectedProjectId || projects[0]?.id || '';

  const {
    data: sprints = [],
    isLoading: isSprintsLoading,
    error: sprintsError,
    refetch,
  } = useQuery({
    queryKey: ['sprints', 'project', activeProjectId],
    queryFn: () => sprintsApi.listByProject(activeProjectId),
    enabled: !!activeProjectId,
  });

  // Sprint Health query
  const { data: sprintHealth, isLoading: isHealthLoading } = useQuery({
    queryKey: ['sprint-health', selectedHealthSprint?.id],
    queryFn: () => sprintsApi.getHealth(selectedHealthSprint?.id),
    enabled: !!selectedHealthSprint?.id,
  });

  const createMutation = useMutation({
    mutationFn: (data) => sprintsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sprints'] });
      setIsCreateModalOpen(false);
      setFormData({ name: '', project_id: '', goal: '', start_date: '', end_date: '' });
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ sprintId, status }) => sprintsApi.changeStatus(sprintId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sprints'] });
      queryClient.invalidateQueries({ queryKey: ['role-dashboard'] });
      setCompleting(null);
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    createMutation.mutate({
      ...formData,
      project_id: formData.project_id || activeProjectId,
    });
  };

  const columns = [
    { key: 'name', header: 'Sprint Name', render: (s) => <span style={{ fontWeight: '600' }}>{s.name}</span> },
    { key: 'id', header: 'Sprint ID', render: (s) => <span className="font-mono">{s.id}</span> },
    { key: 'status', header: 'Status', render: (s) => <StatusBadge status={s.status} /> },
    { key: 'goal', header: 'Sprint Goal', render: (s) => s.goal || '—' },
    { key: 'start_date', header: 'Start Date', render: (s) => formatDate(s.start_date) },
    { key: 'end_date', header: 'End Date', render: (s) => formatDate(s.end_date) },
    {
      key: 'actions',
      header: 'Actions',
      render: (s) => (
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <Button
            variant="secondary"
            size="sm"
            leftIcon={<Activity size={14} />}
            onClick={(e) => {
              e.stopPropagation();
              setSelectedHealthSprint(s);
            }}
          >
            Plan vs Reality
          </Button>
          {canManageSprints && s.status === 'planning' && (
            <Button
              variant="primary"
              size="sm"
              leftIcon={<Play size={14} />}
              isLoading={statusMutation.isPending && statusMutation.variables?.sprintId === s.id}
              onClick={(e) => {
                e.stopPropagation();
                statusMutation.mutate({ sprintId: s.id, status: 'active' });
              }}
            >
              Start sprint
            </Button>
          )}
          {canManageSprints && s.status === 'active' && (
            <Button
              variant="secondary"
              size="sm"
              leftIcon={<CheckCircle2 size={14} />}
              onClick={(e) => {
                e.stopPropagation();
                statusMutation.reset();
                setCompleting(s);
              }}
            >
              Complete sprint
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Sprint Management & Health"
        subtitle="Manage sprint execution, story point velocity, and Plan vs Reality health analysis."
        actions={
          <PermissionGuard permission={PERMISSIONS.CREATE_SPRINT}>
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => {
                setFormData({ ...formData, project_id: activeProjectId });
                setIsCreateModalOpen(true);
              }}
            >
              Create Sprint
            </Button>
          </PermissionGuard>
        }
      />

      {/* Project Selector Bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-muted)' }}>
          Active Project:
        </span>
        <div style={{ width: '280px' }}>
          <Select
            value={activeProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            options={projects.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
          />
        </div>
      </div>

      {isSprintsLoading ? (
        <LoadingState message="Loading sprints..." />
      ) : sprintsError ? (
        <ErrorState message={sprintsError.message} onRetry={refetch} />
      ) : (
        <>
          {statusMutation.error && !completing && (
            <p role="alert" style={{ marginBottom: '1rem', fontSize: '0.875rem', color: 'var(--danger)' }}>
              {statusMutation.error.message}
            </p>
          )}
          <Table columns={columns} data={sprints} emptyMessage="No sprints found for this project." />
        </>
      )}

      <Modal
        isOpen={!!completing}
        onClose={() => setCompleting(null)}
        title="Complete sprint"
        subtitle={completing?.name}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCompleting(null)}>Cancel</Button>
            <Button
              variant="primary"
              isLoading={statusMutation.isPending}
              onClick={() => statusMutation.mutate({ sprintId: completing.id, status: 'completed' })}
            >
              Complete sprint
            </Button>
          </>
        }
      >
        <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
          Final completion and velocity are recorded from the sprint's tasks. Unfinished tasks stay open.
          This cannot be undone.
        </p>
        {statusMutation.error && (
          <p role="alert" style={{ marginTop: '0.75rem', fontSize: '0.8125rem', color: 'var(--danger)' }}>
            {statusMutation.error.message}
          </p>
        )}
      </Modal>

      {/* Sprint Health Modal (Plan vs Reality) */}
      <Modal
        isOpen={!!selectedHealthSprint}
        onClose={() => setSelectedHealthSprint(null)}
        title={`Sprint Health: ${selectedHealthSprint?.name || 'Analysis'}`}
        subtitle="Plan vs Reality analysis computed by Layer 5 Intelligence Engine"
        maxWidth="600px"
        footer={
          <Button variant="secondary" onClick={() => setSelectedHealthSprint(null)}>
            Close
          </Button>
        }
      >
        {isHealthLoading ? (
          <LoadingState message="Analyzing sprint execution..." />
        ) : sprintHealth ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            {/* Completion and Risk Header */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '1rem',
                padding: '1rem',
                backgroundColor: 'var(--bg-elevated)',
                borderRadius: 'var(--radius-md)',
              }}
            >
              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                  COMPLETION RATE
                </span>
                <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {sprintHealth.completion_pct?.toFixed(1) || 0}%
                </div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.1rem' }}>
                  {sprintHealth.completed_stories || 0} / {sprintHealth.total_stories || 0} stories done
                </div>
              </div>

              <div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                  RISK ASSESSMENT
                </span>
                <div style={{ marginTop: '0.4rem' }}>
                  <RiskBadge level={sprintHealth.risk_level || 'LOW'} score={sprintHealth.risk_score} size="md" />
                </div>
              </div>
            </div>

            {/* Progress bar */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: '0.35rem' }}>
                <span style={{ fontWeight: '600', color: 'var(--text-secondary)' }}>Sprint Progress</span>
                <span style={{ fontWeight: '600', color: 'var(--primary)' }}>
                  {sprintHealth.completion_pct?.toFixed(0) || 0}%
                </span>
              </div>
              <ProgressBar value={sprintHealth.completion_pct || 0} color="primary" height="10px" />
            </div>

            {/* Risk Factors */}
            {sprintHealth.risk_factors && sprintHealth.risk_factors.length > 0 && (
              <div>
                <h4 style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                  Identified Risk Factors
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                  {sprintHealth.risk_factors.map((factor, idx) => (
                    <div
                      key={idx}
                      style={{
                        padding: '0.65rem 0.85rem',
                        borderRadius: 'var(--radius-sm)',
                        backgroundColor: 'var(--warning-light)',
                        border: '1px solid var(--warning-border)',
                        color: 'var(--warning)',
                        fontSize: '0.8125rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                      }}
                    >
                      <AlertTriangle size={15} style={{ flexShrink: 0 }} />
                      <span>{factor}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ) : (
          <EmptyState title="No health data" description="Sprint has not started yet or has no stories." />
        )}
      </Modal>

      {/* Create Sprint Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Sprint"
        subtitle="PM & Tech Lead Sprint Planning"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} isLoading={createMutation.isPending}>
              Create Sprint
            </Button>
          </>
        }
      >
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Sprint Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="Enter the sprint name"
            required
          />
          <Select
            label="Project"
            value={formData.project_id || activeProjectId}
            onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
            options={projects.map((p) => ({ value: p.id, label: p.name }))}
            required
          />
          <Input
            label="Sprint Goal"
            value={formData.goal}
            onChange={(e) => setFormData({ ...formData, goal: e.target.value })}
            placeholder="Describe the sprint objective"
            required
          />
          <div className="form-columns">
            <Input
              label="Start Date"
              type="date"
              value={formData.start_date}
              onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
              required
            />
            <Input
              label="End Date"
              type="date"
              value={formData.end_date}
              onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
              required
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
