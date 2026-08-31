import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '../../api/projects.api';
import { sprintsApi } from '../../api/sprints.api';
import { tasksApi } from '../../api/tasks.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Tabs } from '../../components/common/Tabs';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import {
  FolderGit2,
  Layers,
  ListTodo,
  ShieldCheck,
  Activity,
  ArrowLeft,
  Plus,
  KanbanSquare,
} from 'lucide-react';
import { formatDate } from '../../utils/dates';

export function ProjectDetailPage() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('overview'); // 'overview' | 'sprints' | 'tasks'

  const {
    data: project,
    isLoading: isProjectLoading,
    error: projectError,
  } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => projectsApi.getById(projectId),
  });

  const { data: sprints = [] } = useQuery({
    queryKey: ['sprints', 'project', projectId],
    queryFn: () => sprintsApi.listByProject(projectId),
    enabled: !!projectId,
  });

  const { data: tasks = [] } = useQuery({
    queryKey: ['tasks', 'project', projectId],
    queryFn: () => tasksApi.listByProject(projectId),
    enabled: !!projectId,
  });

  if (isProjectLoading) return <LoadingState message="Loading project details..." />;
  if (projectError) return <ErrorState message={projectError.message} onRetry={() => window.location.reload()} />;

  const sprintColumns = [
    { key: 'name', header: 'Sprint', render: (s) => <span style={{ fontWeight: '700' }}>{s.name}</span> },
    { key: 'status', header: 'Status', render: (s) => <StatusBadge status={s.status} /> },
    { key: 'goal', header: 'Sprint Goal', render: (s) => s.goal || '—' },
    { key: 'start_date', header: 'Start Date', render: (s) => formatDate(s.start_date) },
    { key: 'end_date', header: 'End Date', render: (s) => formatDate(s.end_date) },
    {
      key: 'action',
      header: 'Health',
      render: (s) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/sprints/${s.id}`)}
        >
          Plan vs Reality
        </Button>
      ),
    },
  ];

  const taskColumns = [
    { key: 'title', header: 'Task', render: (t) => <span style={{ fontWeight: '600' }}>{t.title}</span> },
    { key: 'assignee_id', header: 'Assignee', render: (t) => t.assignee_id || 'Unassigned' },
    { key: 'status', header: 'Status', render: (t) => <StatusBadge status={t.status} /> },
    { key: 'priority', header: 'Priority', render: (t) => <span style={{ textTransform: 'capitalize' }}>{t.priority}</span> },
    { key: 'due_date', header: 'Due Date', render: (t) => t.due_date || '—' },
  ];

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/projects')}>
          Back to Projects
        </Button>
      </div>

      <PageHeader
        title={project?.name || 'Project Details'}
        subtitle={project?.description || `Project ID: ${project?.id}`}
        badge={<StatusBadge status={project?.status} />}
        actions={
          <div style={{ display: 'flex', gap: '0.65rem' }}>
            <Button
              variant="secondary"
              leftIcon={<KanbanSquare size={16} />}
              onClick={() => navigate('/board')}
            >
              Project Board
            </Button>
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => navigate('/sprints')}
            >
              New Sprint
            </Button>
          </div>
        }
      />

      {/* Tabs */}
      <Tabs
        tabs={[
          { id: 'overview', label: 'Overview', icon: <FolderGit2 size={16} /> },
          { id: 'sprints', label: 'Sprints', icon: <Layers size={16} />, count: sprints.length },
          { id: 'tasks', label: 'Tasks', icon: <ListTodo size={16} />, count: tasks.length },
        ]}
        activeTab={activeTab}
        onChange={setActiveTab}
        className="mb-6"
      />

      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem', marginTop: '1.5rem' }}>
          <Card title="Project Metadata" subtitle="Core organizational associations">
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.875rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Project ID</span>
                <span className="font-mono">{project.id}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Assigned Team</span>
                <strong>{project.team_id || 'Unassigned'}</strong>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Main Module</span>
                <span>{project.main_module || '—'}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: 'var(--text-muted)' }}>Timeline</span>
                <span>{formatDate(project.start_date)} – {formatDate(project.end_date)}</span>
              </div>
            </div>
          </Card>

          <Card title="Delivery Health" subtitle="Plan vs Reality Intelligence summary">
            <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
              Project execution is tracked in real-time across sprints. The intelligence engine aggregates commit velocity,
              PR review latency, and blocked tasks to compute delivery risk.
            </p>
            <div style={{ marginTop: '1.25rem' }}>
              <Button variant="secondary" size="sm" onClick={() => navigate('/code-quality')}>
                View Code Quality for Project
              </Button>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'sprints' && (
        <div style={{ marginTop: '1.5rem' }}>
          <Table columns={sprintColumns} data={sprints} emptyMessage="No sprints found for this project." />
        </div>
      )}

      {activeTab === 'tasks' && (
        <div style={{ marginTop: '1.5rem' }}>
          <Table columns={taskColumns} data={tasks} emptyMessage="No tasks found for this project." />
        </div>
      )}
    </div>
  );
}
