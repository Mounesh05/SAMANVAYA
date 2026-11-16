import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { projectsApi } from '../../api/projects.api';
import { rolesApi } from '../../api/roles.api';
import { useSessionScope } from '../../store/useSessionScope';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { BarList, Meter, Timeline } from '../../components/charts/Charts';
import '../../components/dashboard/Dashboard.css';
import { FolderGit2, TrendingUp, AlertTriangle, Layers, Plus } from 'lucide-react';

// Projects still being delivered (backend statuses: active, paused, completed, archived).
const OPEN_STATUSES = new Set(['active', 'paused']);
const statusLabel = (status) => (status ? status.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) : 'No status');

export function PMDashboardPage() {
  const sessionScope = useSessionScope();
  const navigate = useNavigate();

  const { data: projects = [], isLoading, error, refetch } = useQuery({
    queryKey: ['projects', 'list', sessionScope],
    queryFn: () => projectsApi.list(),
  });
  const { data: dashboardData } = useQuery({
    queryKey: ['role-dashboard', 'pm'],
    queryFn: () => rolesApi.getPMDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading the project delivery dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = dashboardData?.summary || {};
  const activeProjects = projects.filter((p) => p.status === 'active');
  const confidence = summary.delivery_confidence ? parseFloat(summary.delivery_confidence) : null;

  const statusCounts = projects.reduce((counts, project) => {
    const key = project.status || 'none';
    counts[key] = (counts[key] || 0) + 1;
    return counts;
  }, {});

  const projectColumns = [
    { key: 'name', header: 'Project', render: (p) => <span style={{ fontWeight: '600' }}>{p.name}</span> },
    { key: 'team_id', header: 'Team', render: (p) => p.team_id || 'Unassigned' },
    { key: 'status', header: 'Status', render: (p) => <StatusBadge status={p.status} /> },
    { key: 'start_date', header: 'Start', render: (p) => p.start_date || '—' },
    { key: 'end_date', header: 'Target end', render: (p) => p.end_date || '—' },
    {
      key: 'action',
      header: '',
      align: 'right',
      render: (p) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/projects/${p.id}`);
          }}
        >
          View health
        </Button>
      ),
    },
  ];

  return (
    <div className="dash">
      <PageHeader
        title="Project delivery"
        subtitle="Schedules, sprints and risks."
        actions={
          <Button variant="primary" leftIcon={<Plus size={16} />} onClick={() => navigate('/projects')}>
            Create project
          </Button>
        }
      />

      <div className="dash-kpis">
        <MetricCard
          title="Active projects"
          value={activeProjects.length}
          subtitle={`${projects.length} total`}
          icon={<FolderGit2 size={18} />}
          color="primary"
          onClick={() => navigate('/projects')}
        />
        <MetricCard
          title="Delivery confidence"
          value={summary.delivery_confidence ?? '—'}
          subtitle="Active sprint average"
          icon={<TrendingUp size={18} />}
          color="success"
        />
        <MetricCard
          title="Sprints in progress"
          value={summary.active_sprints ?? '—'}
          subtitle="Active now"
          icon={<Layers size={18} />}
          color="cyan"
          onClick={() => navigate('/sprints')}
        />
        <MetricCard
          title="High and critical risks"
          value={summary.high_risks ?? '—'}
          subtitle="Open"
          icon={<AlertTriangle size={18} />}
          color={summary.high_risks > 0 ? 'warning' : 'success'}
        />
      </div>

      <div className="dash-row dash-row--wide">
        <Card title="Schedule" subtitle="Start to target end">
          <Timeline
            label="Project schedule"
            emptyText="No project dates set."
            items={projects.map((project) => ({
              key: project.id,
              label: project.name,
              start: project.start_date,
              end: project.end_date,
              status: statusLabel(project.status),
              open: OPEN_STATUSES.has(project.status),
            }))}
            onSelect={(row) => navigate(`/projects/${row.key}`)}
          />
        </Card>

        <div className="dash-stack">
          <Card title="Delivery confidence" subtitle="Active sprint average">
            <Meter
              label="Delivery confidence"
              value={confidence}
              emptyText="No sprint data yet."
              caption="On track ≥ 75% · At risk < 50%"
            />
          </Card>
          <Card title="Projects by status">
            <BarList
              label="Projects"
              emptyText="No projects yet."
              items={Object.entries(statusCounts).map(([status, count]) => ({
                key: status,
                label: statusLabel(status === 'none' ? '' : status),
                value: count,
              }))}
            />
          </Card>
        </div>
      </div>

      <Card
        title="Project portfolio"
        action={
          <Button variant="ghost" size="sm" onClick={() => navigate('/projects')}>
            All projects
          </Button>
        }
      >
        <Table
          columns={projectColumns}
          data={projects}
          emptyMessage="No projects yet."
          onRowClick={(p) => navigate(`/projects/${p.id}`)}
        />
      </Card>
    </div>
  );
}
