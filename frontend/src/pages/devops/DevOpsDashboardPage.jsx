import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/StatusBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { SegmentedBar, StackedColumns } from '../../components/charts/Charts';
import { dailyPoints } from '../../components/charts/chartData';
import '../../components/dashboard/Dashboard.css';
import { Terminal, Activity, Server, XCircle, MessageSquareQuote, ArrowRight, ShieldCheck } from 'lucide-react';

const SUCCESS = new Set(['success', 'successful', 'passed']);
const FAILURE = new Set(['failure', 'failed', 'cancelled', 'error']);

/* Same reading of an event's result as the backend summary uses. */
function eventOutcome(event) {
  const payload = event?.payload || {};
  const status = String(
    payload.workflow_run?.conclusion || payload.deployment_status?.state || payload.check_run?.conclusion || ''
  ).toLowerCase();
  if (SUCCESS.has(status)) return 'success';
  if (FAILURE.has(status)) return 'failed';
  return 'other';
}

const eventName = (event) => {
  const payload = event?.payload || {};
  return (
    payload.workflow_run?.name
    || payload.check_run?.name
    || (payload.deployment?.environment && `Deploy to ${payload.deployment.environment}`)
    || event.event_type
  );
};

const SERIES = [
  { key: 'success', label: 'Succeeded', tone: 'good' },
  { key: 'failed', label: 'Failed', tone: 'critical' },
  { key: 'other', label: 'In progress or other', tone: 'neutral' },
];

export function DevOpsDashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'devops'],
    queryFn: () => rolesApi.getDevOpsDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading the DevOps dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};
  const pipelines = data?.pipelines || [];
  const deployments = data?.deployments || [];
  const events = [...pipelines, ...deployments];
  const counts = events.reduce((acc, event) => {
    const outcome = eventOutcome(event);
    acc[outcome] = (acc[outcome] || 0) + 1;
    return acc;
  }, {});
  const daily = dailyPoints(events, { days: 14, dateOf: (event) => event.created_at, bucketOf: eventOutcome });
  const recent = [...events].sort((a, b) => String(b.created_at || '').localeCompare(String(a.created_at || ''))).slice(0, 8);
  const health = summary.system_health;

  return (
    <div className="dash">
      <PageHeader
        title="Pipelines and deployments"
        subtitle="CI/CD results from linked repositories."
        actions={
          <Button variant="primary" leftIcon={<MessageSquareQuote size={16} />} onClick={() => navigate('/feedback')}>
            Give feedback
          </Button>
        }
      />

      <div className="dash-kpis">
        <MetricCard
          title="Success rate"
          value={summary.build_success_rate != null ? `${summary.build_success_rate}%` : '—'}
          subtitle="Finished runs"
          icon={<Activity size={18} />}
          color="success"
        />
        <MetricCard
          title="Pipeline runs"
          value={summary.active_pipelines ?? 0}
          subtitle="Recent"
          icon={<Terminal size={18} />}
          color="primary"
        />
        <MetricCard
          title="Deployments"
          value={summary.deployments_today ?? 0}
          subtitle="Recent"
          icon={<Server size={18} />}
          color="cyan"
        />
        <MetricCard
          title="Failed runs"
          value={summary.active_incidents ?? 0}
          subtitle={health ? `System health: ${health.toLowerCase()}` : 'No results yet'}
          icon={health === 'HEALTHY' ? <ShieldCheck size={18} /> : <XCircle size={18} />}
          color={summary.active_incidents > 0 ? 'danger' : 'success'}
        />
      </div>

      <div className="dash-row dash-row--wide">
        <Card title="Runs per day" subtitle="Last 14 days">
          <StackedColumns
            label="Runs per day"
            emptyText="No runs in the last 14 days."
            data={daily}
            series={SERIES}
          />
        </Card>

        <Card title="Results">
          <SegmentedBar
            label="Run results"
            emptyText="No runs reported yet."
            parts={SERIES.map((s) => ({ label: s.label, value: counts[s.key] || 0, tone: s.tone }))}
          />
          <h4 className="dash-sub">Latest</h4>
          {recent.length ? (
            <ul className="dash-list">
              {recent.map((event, index) => (
                <li key={`${event.created_at}-${index}`}>
                  <div className="dash-list-main">
                    <div className="dash-list-title">{eventName(event)}</div>
                    <div className="dash-list-meta">
                      {event.payload?.repository?.full_name || 'Repository not named'}
                      {event.created_at ? ` · ${new Date(event.created_at).toLocaleString()}` : ''}
                    </div>
                  </div>
                  <StatusBadge status={eventOutcome(event) === 'other' ? 'pending' : eventOutcome(event)} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="viz-empty">Nothing to show yet.</p>
          )}
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
            Paste a build or deployment log. AI finds the cause and suggests fixes.
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
