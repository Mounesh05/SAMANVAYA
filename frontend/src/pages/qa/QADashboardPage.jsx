import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { qaApi } from '../../api/qa.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Select } from '../../components/common/Select';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { CIProvisioningModal } from '../../components/qa/CIProvisioningModal';
import { AutomatedTestRunsTable } from '../../components/qa/AutomatedTestRunsTable';
import { CheckCircle2, Bug, FlaskConical, Clock3, XCircle, CircleSlash, GitBranch, RefreshCw } from 'lucide-react';

const EMPTY_LIST = [];

export function QADashboardPage() {
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [isProvisioningModalOpen, setIsProvisioningModalOpen] = useState(false);
  const [testRunsFilter, setTestRunsFilter] = useState('github_actions'); // 'manual', 'github_actions', 'all'
  
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

  // CI Configuration
  const ciConfigQuery = useQuery({
    queryKey: ['qa-ci-configs', projectId],
    queryFn: () => qaApi.getCIConfigs(projectId),
    enabled: Boolean(projectId),
  });

  // Test Runs
  const testRunsQuery = useQuery({
    queryKey: ['qa-test-runs', projectId, testRunsFilter],
    queryFn: () => qaApi.getTestRuns(projectId, { 
      source: testRunsFilter === 'all' ? undefined : testRunsFilter 
    }),
    enabled: Boolean(projectId),
  });

  // Provision CI Mutation
  const provisionMutation = useMutation({
    mutationFn: ({ projectId, repository, branch }) =>
      qaApi.enableCIIntegration(projectId, repository, branch),
    onSuccess: () => {
      queryClient.invalidateQueries(['qa-ci-configs', projectId]);
      queryClient.invalidateQueries(['qa-test-runs', projectId]);
    },
  });

  // Disable CI Mutation
  const disableMutation = useMutation({
    mutationFn: ({ projectId, branch }) =>
      qaApi.disableCIIntegration(projectId, branch),
    onSuccess: () => {
      queryClient.invalidateQueries(['qa-ci-configs', projectId]);
      queryClient.invalidateQueries(['qa-test-runs', projectId]);
    },
  });

  if (projectsQuery.isLoading) return <LoadingState message="Loading authorized QA projects..." />;
  if (projectsQuery.error) {
    return <ErrorState message={projectsQuery.error.message} onRetry={projectsQuery.refetch} />;
  }
  if (dashboardQuery.isLoading && projectId) {
    return <LoadingState message="Loading QA dashboard..." />;
  }
  if (dashboardQuery.error) {
    return <ErrorState message={dashboardQuery.error.message} onRetry={dashboardQuery.refetch} />;
  }

  const data = dashboardQuery.data || {};
  const ciConfigs = ciConfigQuery.data?.configs || [];
  const testRuns = testRunsQuery.data?.runs || EMPTY_LIST;

  const metrics = [
    { title: 'Test Cases', value: data.total_test_cases ?? 0, icon: <FlaskConical size={20} />, color: 'primary' },
    { title: 'Executions', value: data.total_executions ?? 0, icon: <Clock3 size={20} />, color: 'cyan' },
    { title: 'Passed', value: data.passed ?? 0, icon: <CheckCircle2 size={20} />, color: 'success' },
    { title: 'Failed', value: data.failed ?? 0, icon: <XCircle size={20} />, color: 'danger' },
    { title: 'Blocked', value: data.blocked ?? 0, icon: <CircleSlash size={20} />, color: 'warning' },
    { title: 'Not Executed', value: data.not_executed ?? 0, icon: <FlaskConical size={20} />, color: 'primary' },
    { title: 'Open Defects', value: data.open_defects ?? 0, icon: <Bug size={20} />, color: 'danger' },
    { title: 'Awaiting Retest', value: data.awaiting_retest ?? 0, icon: <Clock3 size={20} />, color: 'warning' },
  ];

  const handleProvision = async (projectId, repository, branch) => {
    return await provisionMutation.mutateAsync({ projectId, repository, branch });
  };

  const handleDisable = async (branch) => {
    if (!window.confirm(`Disable CI integration for branch "${branch}"?`)) return;
    await disableMutation.mutateAsync({ projectId, branch });
  };

  return (
    <div>
      <PageHeader
        title="Quality & Test Engineering"
        subtitle="Track project test coverage, manual execution outcomes, and defect retesting."
        actions={
          <div style={{ width: 260 }}>
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
        <Card title="No authorized projects">
          <p>No projects are available to your account.</p>
        </Card>
      ) : (
        <>
          {/* CI Integration Card */}
          <Card 
            title="CI Integration" 
            subtitle="Enable automated testing via GitHub Actions for different branches"
            style={{ marginBottom: '1.5rem' }}
          >
            {ciConfigs.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                {/* Existing Branch Configurations */}
                {ciConfigs.map((config) => (
                  <div 
                    key={config.branch}
                    style={{ 
                      display: 'flex', 
                      alignItems: 'center', 
                      justifyContent: 'space-between', 
                      flexWrap: 'wrap', 
                      gap: '1rem',
                      padding: '0.75rem',
                      backgroundColor: 'var(--bg-subtle)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1 }}>
                      <div
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          padding: '0.5rem 0.75rem',
                          backgroundColor: 'rgba(16, 185, 129, 0.1)',
                          border: '1px solid rgba(16, 185, 129, 0.3)',
                          borderRadius: 'var(--radius-md)',
                          color: '#10b981',
                          fontSize: '0.875rem',
                          fontWeight: '500',
                        }}
                      >
                        <CheckCircle2 size={16} />
                        Enabled
                      </div>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                        <GitBranch size={14} style={{ display: 'inline', marginRight: '0.25rem', verticalAlign: 'middle' }} />
                        <strong>{config.repository}</strong>
                        {' / '}
                        <span style={{ 
                          padding: '0.125rem 0.5rem',
                          backgroundColor: 'var(--bg-primary)',
                          borderRadius: 'var(--radius-sm)',
                          fontFamily: 'monospace'
                        }}>
                          {config.branch}
                        </span>
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                      {config.workflow_url && (
                        <a
                          href={config.workflow_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ color: 'var(--color-primary)', fontSize: '0.875rem' }}
                        >
                          View Workflow →
                        </a>
                      )}
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={() => handleDisable(config.branch)}
                        disabled={disableMutation.isPending}
                      >
                        Disable
                      </Button>
                    </div>
                  </div>
                ))}
                
                {/* Add Another Branch Button */}
                <Button 
                  variant="secondary"
                  onClick={() => setIsProvisioningModalOpen(true)}
                  style={{ alignSelf: 'flex-start' }}
                >
                  <GitBranch size={16} />
                  Enable CI for Another Branch
                </Button>
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
                <p style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                  Enable CI integration to automatically run tests on every push and pull request.
                </p>
                <Button onClick={() => setIsProvisioningModalOpen(true)}>
                  <GitBranch size={16} />
                  Enable CI Integration
                </Button>
              </div>
            )}
          </Card>

          {/* Manual Test Metrics */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(190px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
            {metrics.map((metric) => (
              <MetricCard key={metric.title} {...metric} />
            ))}
          </div>

          <Card
            title={data.pass_rate == null ? 'No completed executions yet' : `Pass rate: ${data.pass_rate}%`}
            subtitle="Pass rate is Passed / (Passed + Failed); blocked executions are excluded."
            style={{ marginBottom: '1.5rem' }}
          >
            <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
              <Link to="/tests">Manage test cases</Link>
              <Link to="/bugs">Review defects</Link>
            </div>
          </Card>

          {/* Automated Test Runs Section */}
          {ciConfigs.length > 0 && (
            <div style={{ marginBottom: '1.5rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <h2 style={{ fontSize: '1.25rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <GitBranch size={20} />
                  Automated Test Runs
                </h2>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                  <div
                    style={{
                      display: 'flex',
                      gap: '0.25rem',
                      padding: '0.25rem',
                      backgroundColor: 'var(--bg-subtle)',
                      borderRadius: 'var(--radius-md)',
                    }}
                  >
                    {['github_actions', 'all'].map((filter) => (
                      <button
                        key={filter}
                        onClick={() => setTestRunsFilter(filter)}
                        style={{
                          padding: '0.375rem 0.75rem',
                          fontSize: '0.875rem',
                          fontWeight: '500',
                          border: 'none',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          backgroundColor: testRunsFilter === filter ? 'var(--color-primary)' : 'transparent',
                          color: testRunsFilter === filter ? '#fff' : 'var(--text-muted)',
                        }}
                      >
                        {filter === 'all' ? 'All' : 'GitHub Actions'}
                      </button>
                    ))}
                  </div>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => testRunsQuery.refetch()}
                    disabled={testRunsQuery.isFetching}
                  >
                    <RefreshCw size={14} className={testRunsQuery.isFetching ? 'animate-spin' : ''} />
                  </Button>
                </div>
              </div>
              <AutomatedTestRunsTable runs={testRuns} isLoading={testRunsQuery.isLoading} />
            </div>
          )}

          {/* Manual Executions */}
          <Card title="Recent manual executions" subtitle="Execution history is append-only; reruns do not replace earlier results.">
            {data.recent_executions?.length ? (
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {data.recent_executions.map((execution) => (
                  <div key={execution.id} style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', padding: '0.75rem', borderBottom: '1px solid var(--border-subtle)' }}>
                    <div>
                      <strong>{execution.test_case_id}</strong>
                      <span style={{ marginLeft: '0.75rem' }}>{execution.status}</span>
                      <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem' }}>{execution.executed_at}</div>
                    </div>
                    <span>{execution.executed_by}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p style={{ color: 'var(--text-muted)' }}>No test executions recorded for this project.</p>
            )}
          </Card>
        </>
      )}

      {/* CI Provisioning Modal */}
      <CIProvisioningModal
        isOpen={isProvisioningModalOpen}
        onClose={() => setIsProvisioningModalOpen(false)}
        onProvision={handleProvision}
        projectId={projectId}
      />
    </div>
  );
}
