import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { projectsApi } from '../../api/projects.api';
import { DEFAULT_ORG_ID } from '../../utils/constants';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import {
  FolderGit2,
  TrendingUp,
  AlertTriangle,
  Layers,
  Plus,
  ArrowRight,
} from 'lucide-react';

export function PMDashboardPage() {
  const navigate = useNavigate();

  const { data: projects = [], isLoading, error, refetch } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
  });

  if (isLoading) return <LoadingState message="Loading Project Manager dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const activeProjects = projects.filter((p) => p.status === 'active');

  const projectColumns = [
    { key: 'name', header: 'Project', render: (p) => <span style={{ fontWeight: '700' }}>{p.name}</span> },
    { key: 'team_id', header: 'Team', render: (p) => p.team_id || 'Unassigned' },
    { key: 'status', header: 'Status', render: (p) => <StatusBadge status={p.status} /> },
    { key: 'start_date', header: 'Start Date', render: (p) => p.start_date || '—' },
    { key: 'end_date', header: 'Target End', render: (p) => p.end_date || '—' },
    {
      key: 'action',
      header: 'Action',
      render: (p) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/projects/${p.id}`);
          }}
        >
          View Health
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Project Delivery Dashboard"
        subtitle="Track delivery confidence, milestone timelines, sprint velocity, and project risks."
        actions={
          <Button
            variant="primary"
            leftIcon={<Plus size={16} />}
            onClick={() => navigate('/projects')}
          >
            Create Project
          </Button>
        }
      />

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <MetricCard
          title="Active Projects"
          value={activeProjects.length}
          subtitle={`Total tracked: ${projects.length}`}
          icon={<FolderGit2 size={20} />}
          color="primary"
        />
        <MetricCard
          title="Delivery Confidence"
          value="82%"
          subtitle="Plan vs Reality aligned"
          icon={<TrendingUp size={20} />}
          color="success"
        />
        <MetricCard
          title="Sprints in Progress"
          value="4"
          subtitle="Active delivery cycles"
          icon={<Layers size={20} />}
          color="cyan"
          onClick={() => navigate('/sprints')}
        />
        <MetricCard
          title="Flagged Risks"
          value="2"
          subtitle="Behind schedule / blocked"
          icon={<AlertTriangle size={20} />}
          color="warning"
        />
      </div>

      {/* Project Portfolio Table */}
      <Card
        title="Active Project Portfolio"
        subtitle="Manage scopes, milestones, and sprint execution"
        action={
          <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
            Portfolio Overview
          </Button>
        }
      >
        <Table
          columns={projectColumns}
          data={projects}
          emptyMessage="No projects created yet. Click 'Create Project' to start."
          onRowClick={(p) => navigate(`/projects/${p.id}`)}
        />
      </Card>
    </div>
  );
}
