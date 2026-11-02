import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { qaApi } from '../../api/qa.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Select } from '../../components/common/Select';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { CheckCircle2, Bug, FlaskConical, Clock3, XCircle, CircleSlash } from 'lucide-react';

const EMPTY_LIST = [];

export function QADashboardPage() {
  const [selectedProjectId, setSelectedProjectId] = useState('');
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
    </div>
  );
}
