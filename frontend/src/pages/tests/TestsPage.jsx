import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ProgressBar } from '../../components/common/ProgressBar';
import { Badge } from '../../components/common/Badge';
import { MetricCard } from '../../components/common/MetricCard';
import { FlaskConical, CheckCircle, XCircle, TrendingUp } from 'lucide-react';

export function TestsPage() {
  const { data: testData, isLoading, error, refetch } = useQuery({
    queryKey: ['test-health'],
    queryFn: () => rolesApi.getTestHealth(),
    retry: 1,
  });

  const testSuites = testData?.test_suites || [];
  const passRate = testData?.overall_pass_rate || 0;

  const columns = [
    {
      key: 'name',
      header: 'Test Suite',
      render: (suite) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <FlaskConical size={14} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: '600' }}>{suite.name}</span>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (suite) => (
        <Badge variant={suite.status === 'passed' ? 'success' : suite.status === 'failed' ? 'danger' : 'warning'} size="sm">
          {suite.status?.toUpperCase() || 'PENDING'}
        </Badge>
      ),
    },
    {
      key: 'total',
      header: 'Total',
      render: (suite) => suite.total || 0,
    },
    {
      key: 'passed',
      header: 'Passed',
      render: (suite) => (
        <span style={{ color: 'var(--success)', fontWeight: '600' }}>{suite.passed || 0}</span>
      ),
    },
    {
      key: 'failed',
      header: 'Failed',
      render: (suite) => (
        <span style={{ color: suite.failed > 0 ? 'var(--danger)' : 'var(--text-muted)', fontWeight: '600' }}>
          {suite.failed || 0}
        </span>
      ),
    },
    {
      key: 'skipped',
      header: 'Skipped',
      render: (suite) => (
        <span style={{ color: 'var(--warning)', fontWeight: '600' }}>{suite.skipped || 0}</span>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (suite) => suite.duration ? `${suite.duration}s` : '—',
    },
    {
      key: 'pass_rate',
      header: 'Pass Rate',
      render: (suite) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ProgressBar
            value={suite.pass_rate || 0}
            max={100}
            color={suite.pass_rate >= 90 ? 'success' : suite.pass_rate >= 70 ? 'warning' : 'danger'}
            height="6px"
          />
          <span style={{ fontSize: '0.75rem', fontWeight: '600', minWidth: '40px' }}>
            {(suite.pass_rate || 0).toFixed(1)}%
          </span>
        </div>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading test health data..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Test Health"
        subtitle="Monitor test execution status, pass rates, and regression risks."
      />

      {/* Summary Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <MetricCard
          title="Overall Pass Rate"
          value={`${passRate.toFixed(1)}%`}
          icon={<TrendingUp size={20} />}
          color={passRate >= 90 ? 'success' : passRate >= 70 ? 'warning' : 'danger'}
        />
        <MetricCard
          title="Test Suites"
          value={testSuites.length}
          icon={<FlaskConical size={20} />}
          color="primary"
        />
        <MetricCard
          title="Passing Suites"
          value={testSuites.filter((s) => s.status === 'passed').length}
          icon={<CheckCircle size={20} />}
          color="success"
        />
        <MetricCard
          title="Failing Suites"
          value={testSuites.filter((s) => s.status === 'failed').length}
          icon={<XCircle size={20} />}
          color="danger"
        />
      </div>

      {/* Pass Rate Overview */}
      <Card title="Test Execution Health" subtitle="Pass rate across all test suites" style={{ marginBottom: '1.5rem' }}>
        <div style={{ padding: '1rem 0' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
            <span style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>Overall Pass Rate</span>
            <span style={{ fontSize: '0.875rem', fontWeight: '700', color: passRate >= 90 ? 'var(--success)' : 'var(--warning)' }}>
              {passRate.toFixed(1)}%
            </span>
          </div>
          <ProgressBar
            value={passRate}
            max={100}
            color={passRate >= 90 ? 'success' : passRate >= 70 ? 'warning' : 'danger'}
            height="12px"
          />
        </div>
      </Card>

      {/* Test Suites Table */}
      <Card title="Test Suites" subtitle="Detailed test execution results by suite">
        <Table
          columns={columns}
          data={testSuites}
          emptyMessage="No test suite data available. Connect your test runner to see results."
        />
      </Card>
    </div>
  );
}
