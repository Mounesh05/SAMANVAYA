import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { qaApi } from '../../api/qa.api';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Select } from '../../components/common/Select';
import { Button } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/StatusBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { CIProvisioningModal } from '../../components/qa/CIProvisioningModal';
import { AutomatedTestRunsTable } from '../../components/qa/AutomatedTestRunsTable';
import { Meter, SegmentedBar, StackedColumns } from '../../components/charts/Charts';
import { trendPoints } from '../../components/charts/chartData';
import '../../components/dashboard/Dashboard.css';
import { CheckCircle2, GitBranch, RefreshCw } from 'lucide-react';

const EMPTY_LIST = [];
const when = (value) => {
  const date = value ? new Date(value) : null;
  return date && !Number.isNaN(date.getTime())
    ? date.toLocaleString('en', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })
    : value || 'Date not recorded';
};
const OUTCOME_SERIES = [
  { key: 'passed', label: 'Passed', tone: 'good' },
  { key: 'failed', label: 'Failed', tone: 'critical' },
  { key: 'blocked', label: 'Blocked', tone: 'warning' },
];

export function QADashboardPage() {
  const { user } = useAuthStore();
  // Enable/disable CI is MANAGE_TEST_AUTOMATION (QA, PM, Lead; not the CEO since CR-007), as on the backend.
  const canManageCi = hasPermission(user, PERMISSIONS.MANAGE_TEST_AUTOMATION);
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [isProvisioningModalOpen, setIsProvisioningModalOpen] = useState(false);
  const [testRunsFilter, setTestRunsFilter] = useState('github_actions'); // 'github_actions' | 'all'

  const queryClient = useQueryClient();

  const projectsQuery = useQuery({
    queryKey: ['qa-projects'],
    queryFn: qaApi.getProjects,
  });
  const projects = projectsQuery.data || EMPTY_LIST;
  const projectId = selectedProjectId || projects[0]?.id || '';

  const dashboardQuery = useQuery({
    queryKey: ['qa-dashboard', projectId],
    queryFn: () => qaApi.getDashboard(projectId),
    enabled: Boolean(projectId),
  });

  const ciConfigQuery = useQuery({
    queryKey: ['qa-ci-configs', projectId],
    queryFn: () => qaApi.getCIConfigs(projectId),
    enabled: Boolean(projectId),
  });

  const testRunsQuery = useQuery({
    queryKey: ['qa-test-runs', projectId, testRunsFilter],
    queryFn: () => qaApi.getTestRuns(projectId, {
      source: testRunsFilter === 'all' ? undefined : testRunsFilter,
    }),
    enabled: Boolean(projectId),
  });

  const provisionMutation = useMutation({
    mutationFn: ({ projectId, repository, branch }) =>
      qaApi.enableCIIntegration(projectId, repository, branch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qa-ci-configs', projectId] });
      queryClient.invalidateQueries({ queryKey: ['qa-test-runs', projectId] });
    },
  });

  const disableMutation = useMutation({
    mutationFn: ({ projectId, branch }) =>
      qaApi.disableCIIntegration(projectId, branch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['qa-ci-configs', projectId] });
      queryClient.invalidateQueries({ queryKey: ['qa-test-runs', projectId] });
    },
  });

  if (projectsQuery.isLoading) return <LoadingState message="Loading your QA projects..." />;
  if (projectsQuery.error) {
    return <ErrorState message={projectsQuery.error.message} onRetry={projectsQuery.refetch} />;
  }
  if (dashboardQuery.isLoading && projectId) {
    return <LoadingState message="Loading the quality dashboard..." />;
  }
  if (dashboardQuery.error) {
    return <ErrorState message={dashboardQuery.error.message} onRetry={dashboardQuery.refetch} />;
  }

  const data = dashboardQuery.data || {};
  const ciConfigs = ciConfigQuery.data?.configs || [];
  const testRuns = testRunsQuery.data?.runs || EMPTY_LIST;
  const totalCases = data.total_test_cases ?? 0;
  const notExecuted = data.not_executed ?? 0;
  const trend = trendPoints(data.execution_trend || [], OUTCOME_SERIES.map((s) => s.key));

  // The dialog passes only the branch; the backend uses the project's linked repository.
  const handleProvision = async ({ branch }) => {
    return await provisionMutation.mutateAsync({ projectId, repository: undefined, branch });
  };

  const handleDisable = async (branch) => {
    if (!window.confirm(`Disable CI integration for branch "${branch}"?`)) return;
    await disableMutation.mutateAsync({ projectId, branch });
  };

  return (
    <div className="dash">
      <PageHeader
        title="Quality and testing"
        subtitle="Coverage, results and defects by project."
        actions={
          <div style={{ width: 260, maxWidth: '100%' }}>
            <Select
              aria-label="QA project"
              value={projectId}
              onChange={(event) => setSelectedProjectId(event.target.value)}
              options={projects.map((project) => ({ value: project.id, label: project.name }))}
              placeholder="Select project"
            />
          </div>
        }
      />

      {!projectId ? (
        <Card title="No projects available">
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>No projects available.</p>
        </Card>
      ) : (
        <>
          <div className="dash-kpis">
            <MetricCard title="Test cases" value={totalCases} subtitle={`${notExecuted} not run yet`} />
            <MetricCard title="Executions" value={data.total_executions ?? 0} subtitle="All runs" />
            <MetricCard title="Open defects" value={data.open_defects ?? 0} subtitle="Not closed" />
            <MetricCard title="Awaiting retest" value={data.awaiting_retest ?? 0} subtitle="Ready to verify" />
          </div>

          <div className="dash-row dash-row--wide">
            <Card title="Executions per day" subtitle="Daily, by result">
              <StackedColumns
                label="Executions per day"
                emptyText="No executions yet."
                data={trend}
                series={OUTCOME_SERIES}
              />
            </Card>

            <Card title="Pass rate" subtitle="Blocked runs excluded">
              <Meter
                label="Pass rate"
                value={data.pass_rate}
                thresholds={[70, 90]}
                emptyText="No completed executions yet."
                caption="On track ≥ 90% · At risk < 70%"
              />
              <h4 className="dash-sub">All executions</h4>
              <SegmentedBar
                label="All executions"
                emptyText="No executions yet."
                parts={OUTCOME_SERIES.map((s) => ({ label: s.label, value: data[s.key] ?? 0, tone: s.tone }))}
              />
              <h4 className="dash-sub">Test case coverage</h4>
              <SegmentedBar
                label="Test case coverage"
                emptyText="No test cases yet."
                parts={[
                  { label: 'Run at least once', value: Math.max(totalCases - notExecuted, 0), tone: 'blue' },
                  { label: 'Not run yet', value: notExecuted, tone: 'neutral' },
                ]}
              />
              <div className="dash-links">
                <Link to="/tests">Manage test cases</Link>
                <span style={{ color: 'var(--text-muted)' }}>·</span>
                <Link to="/bugs">Review defects</Link>
              </div>
            </Card>
          </div>

          <Card title="CI integration" subtitle="GitHub Actions">
            {ciConfigs.length > 0 ? (
              <ul className="dash-list">
                {ciConfigs.map((config) => (
                  <li key={config.branch}>
                    <div className="dash-list-main" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                      <span className="viz-state viz-state--good">
                        <CheckCircle2 size={14} aria-hidden="true" /> Enabled
                      </span>
                      <span style={{ color: 'var(--text-secondary)' }}>
                        <GitBranch size={14} style={{ verticalAlign: '-2px', marginRight: '0.3rem' }} aria-hidden="true" />
                        <strong style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{config.repository}</strong>
                        {' / '}
                        <code style={{ padding: '0.1rem 0.4rem', borderRadius: 'var(--radius-sm)', background: 'var(--bg-tertiary)' }}>{config.branch}</code>
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      {config.workflow_url && (
                        <a href={config.workflow_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8125rem' }}>
                          View workflow
                        </a>
                      )}
                      {canManageCi && (
                        <Button variant="danger" size="sm" onClick={() => handleDisable(config.branch)} disabled={disableMutation.isPending}>
                          Disable
                        </Button>
                      )}
                    </div>
                  </li>
                ))}
                {canManageCi && (
                  <li>
                    <Button variant="secondary" size="sm" leftIcon={<GitBranch size={14} />} onClick={() => setIsProvisioningModalOpen(true)}>
                      Enable CI for another branch
                    </Button>
                  </li>
                )}
              </ul>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                  Run tests on every push and pull request.
                </p>
                {canManageCi ? (
                  <Button leftIcon={<GitBranch size={16} />} onClick={() => setIsProvisioningModalOpen(true)}>
                    Enable CI integration
                  </Button>
                ) : (
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>Ask QA or your Lead to enable it.</span>
                )}
              </div>
            )}
          </Card>

          {ciConfigs.length > 0 && (
            <Card
              title="Automated test runs"
              action={
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  <div role="group" aria-label="Run source" style={{ display: 'flex', gap: '0.25rem', padding: '0.2rem', background: 'var(--bg-tertiary)', borderRadius: 'var(--radius-md)' }}>
                    {['github_actions', 'all'].map((filter) => (
                      <button
                        key={filter}
                        type="button"
                        aria-pressed={testRunsFilter === filter}
                        onClick={() => setTestRunsFilter(filter)}
                        style={{
                          padding: '0.3rem 0.7rem',
                          fontSize: '0.8125rem',
                          fontWeight: 500,
                          border: 'none',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          background: testRunsFilter === filter ? 'var(--primary)' : 'transparent',
                          color: testRunsFilter === filter ? '#fff' : 'var(--text-secondary)',
                        }}
                      >
                        {filter === 'all' ? 'All' : 'GitHub Actions'}
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    aria-label="Refresh test runs"
                    onClick={() => testRunsQuery.refetch()}
                    disabled={testRunsQuery.isFetching}
                  >
                    <RefreshCw size={14} className={testRunsQuery.isFetching ? 'animate-spin' : ''} />
                  </Button>
                </div>
              }
            >
              <AutomatedTestRunsTable runs={testRuns} isLoading={testRunsQuery.isLoading} />
            </Card>
          )}

          <Card title="Recent manual executions">
            {data.recent_executions?.length ? (
              <ul className="dash-list">
                {data.recent_executions.map((execution) => (
                  <li key={execution.id}>
                    <div className="dash-list-main">
                      <div className="dash-list-title">{execution.test_case_id}</div>
                      <div className="dash-list-meta">{when(execution.executed_at)} · {execution.executed_by}</div>
                    </div>
                    <StatusBadge status={String(execution.status || '').toLowerCase()} />
                  </li>
                ))}
              </ul>
            ) : (
              <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>No executions yet.</p>
            )}
          </Card>
        </>
      )}

      <CIProvisioningModal
        isOpen={isProvisioningModalOpen}
        onClose={() => setIsProvisioningModalOpen(false)}
        onProvision={handleProvision}
        projectId={projectId}
      />
    </div>
  );
}
