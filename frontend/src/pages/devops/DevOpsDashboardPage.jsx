import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { StackedColumns, BarList } from '../../components/charts/Charts';
import { trendPoints } from '../../components/charts/chartData';
import { useSessionScope } from '../../store/useSessionScope';
import { AttemptLink, DeploymentLink } from './OperationsHistory';
import '../../components/dashboard/Dashboard.css';
import { Terminal, MessageSquareQuote, ArrowRight } from 'lucide-react';

const SERIES = [
  { key: 'success', label: 'Succeeded', tone: 'good' },
  { key: 'failed', label: 'Failed', tone: 'critical' },
  { key: 'cancelled', label: 'Cancelled', tone: 'warning' },
  { key: 'other', label: 'In progress or other', tone: 'neutral' },
];

export function DevOpsDashboardPage() {
  const navigate = useNavigate();
  const scope = useSessionScope();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'devops', scope], queryFn: rolesApi.getDevOpsDashboard,
  });
  if (isLoading) return <LoadingState message="Loading the DevOps dashboard…" />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;
  const summary = data.summary || {};
  const daily = trendPoints(data.daily || [], SERIES.map((s) => s.key));
  return (
    <div className="dash">
      <PageHeader title="Pipelines and deployments" subtitle="GitHub activity in your projects over the last 14 UTC dates."
        actions={<Button variant="secondary" leftIcon={<MessageSquareQuote size={16} />} onClick={() => navigate('/feedback')}>Assigned feedback</Button>} />
      <div className="dash-kpis">
        <MetricCard title="Workflow success rate" value={summary.build_success_rate != null ? `${summary.build_success_rate}%` : '—'}
          subtitle="Of attempts that succeeded or failed" onClick={() => navigate('/pipelines?outcome=decided')} />
        <MetricCard title="Workflow attempts" value={summary.workflow_attempts} subtitle="Updated in reporting window" onClick={() => navigate('/pipelines')} />
        <MetricCard title="Deployments today" value={summary.deployments_today} subtitle="Created since midnight UTC" onClick={() => navigate('/deployments?today=true')} />
        <MetricCard title="Open incidents" value={summary.active_incidents} subtitle="Open or investigating" onClick={() => navigate('/incidents?status=unresolved')} />
      </div>
      <div className="dash-row dash-row--wide">
        <Card title="Workflow attempts by day" subtitle="By latest GitHub update · UTC">
          <StackedColumns label="Workflow attempts by day" emptyText="No reported workflow attempts in this window." data={daily} series={SERIES}
            onSelect={(point) => navigate(`/pipelines?day=${point.key}`)} />
        </Card>
        <Card title="Workflow results">
          <BarList label="Workflow results" emptyText="No reported results." items={SERIES.map((s) => ({ ...s, value: data.outcomes?.[s.key] || 0 }))}
            onSelect={(row) => navigate(`/pipelines?outcome=${row.key}`)} />
        </Card>
      </div>
      <div className="dash-row">
        <Card title="Latest attempts" action={<Link to="/pipelines">All attempts</Link>}>
          {data.pipelines?.length ? <ul className="dash-list">{data.pipelines.map((run) => (
            <li key={`${run.repository}/${run.id}/${run.attempt}`}><AttemptLink run={run} /><span>{run.conclusion || run.status || 'Unconfirmed'}</span></li>
          ))}</ul> : <p>No workflow attempts reported.</p>}
        </Card>
        <Card title="Latest deployments" action={<Link to="/deployments">All deployments</Link>}>
          {data.deployments?.length ? <ul className="dash-list">{data.deployments.map((d) => (
            <li key={`${d.repository}/${d.id}`}><DeploymentLink row={d}>{d.repository} #{d.id} · {d.environment || 'Environment unreported'}</DeploymentLink><span>{d.status}</span></li>
          ))}</ul> : <p>No deployments reported.</p>}
        </Card>
      </div>
      <div className="dash-row">
        <Card
          title="AI CI/CD log analyser"
          subtitle="AI-assisted failure diagnosis"
          action={
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight size={14} />} onClick={() => navigate('/cicd-logs')}>
              Open
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Paste a build or deployment log. Review the suggested causes and fixes alongside the log.
          </p>
          <div style={{ marginTop: '1.1rem' }}>
            <Button variant="secondary" size="sm" leftIcon={<Terminal size={16} />} onClick={() => navigate('/cicd-logs')}>
              Analyse a log
            </Button>
          </div>
        </Card>

        <Card
          title="Code security"
          subtitle="Static analysis"
          action={
            <Button variant="ghost" size="sm" rightIcon={<ArrowRight size={14} />} onClick={() => navigate('/code-quality')}>
              Open
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Security findings and dependency risks across repositories.
          </p>
          <div style={{ marginTop: '1.1rem' }}>
            <Button variant="secondary" size="sm" onClick={() => navigate('/code-quality')}>
              View findings
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
