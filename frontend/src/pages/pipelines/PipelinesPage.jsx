import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { MetricCard } from '../../components/common/MetricCard';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ProgressBar } from '../../components/common/ProgressBar';
import { GitBranch, CheckCircle, XCircle, Clock, RefreshCw } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';

export function PipelinesPage() {
  const { data: pipelineData, isLoading, error, refetch } = useQuery({
    queryKey: ['pipelines'],
    queryFn: () => rolesApi.getPipelines(),
    retry: 1,
  });

  const pipelines = pipelineData?.pipelines || [];

  const columns = [
    {
      key: 'name',
      header: 'Pipeline',
      render: (pipeline) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitBranch size={14} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: '600' }}>{pipeline.name}</span>
        </div>
      ),
    },
    {
      key: 'repository',
      header: 'Repository',
      render: (pipeline) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
          {pipeline.repository || '—'}
        </span>
      ),
    },
    {
      key: 'branch',
      header: 'Branch',
      render: (pipeline) => (
        <Badge variant="primary" size="sm">{pipeline.branch || 'main'}</Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (pipeline) => {
        const statusVariant = {
          success: 'success',
          failed: 'danger',
          running: 'info',
          pending: 'warning',
          cancelled: 'default',
        };
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            {pipeline.status === 'success' && <CheckCircle size={14} style={{ color: 'var(--success)' }} />}
            {pipeline.status === 'failed' && <XCircle size={14} style={{ color: 'var(--danger)' }} />}
            {pipeline.status === 'running' && <RefreshCw size={14} style={{ color: 'var(--primary)' }} />}
            {pipeline.status === 'pending' && <Clock size={14} style={{ color: 'var(--warning)' }} />}
            <Badge variant={statusVariant[pipeline.status] || 'default'} size="sm">
              {pipeline.status?.toUpperCase() || 'UNKNOWN'}
            </Badge>
          </div>
        );
      },
    },
    {
      key: 'success_rate',
      header: 'Success Rate',
      render: (pipeline) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <ProgressBar
            value={pipeline.success_rate || 0}
            max={100}
            color={pipeline.success_rate >= 90 ? 'success' : pipeline.success_rate >= 70 ? 'warning' : 'danger'}
            height="6px"
          />
          <span style={{ fontSize: '0.75rem', fontWeight: '600', minWidth: '40px' }}>
            {(pipeline.success_rate || 0).toFixed(1)}%
          </span>
        </div>
      ),
    },
    {
      key: 'last_run',
      header: 'Last Run',
      render: (pipeline) => (
        <span title={formatDate(pipeline.last_run)}>
          {timeAgo(pipeline.last_run)}
        </span>
      ),
    },
    {
      key: 'duration',
      header: 'Duration',
      render: (pipeline) => pipeline.duration ? `${pipeline.duration}s` : '—',
    },
  ];

  if (isLoading) return <LoadingState message="Loading pipelines..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="CI/CD Pipelines"
        subtitle="Monitor pipeline health, build status, and deployment readiness."
      />

      {/* Summary Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <MetricCard
          title="Total Pipelines"
          value={pipelines.length}
          icon={<GitBranch size={20} />}
          color="primary"
        />
        <MetricCard
          title="Passing"
          value={pipelines.filter((p) => p.status === 'success').length}
          icon={<CheckCircle size={20} />}
          color="success"
        />
        <MetricCard
          title="Failing"
          value={pipelines.filter((p) => p.status === 'failed').length}
          icon={<XCircle size={20} />}
          color="danger"
        />
        <MetricCard
          title="Running"
          value={pipelines.filter((p) => p.status === 'running').length}
          icon={<RefreshCw size={20} />}
          color="cyan"
        />
      </div>

      {/* Pipelines Table */}
      <Card title="Pipelines" subtitle="CI/CD pipeline status across repositories">
        <Table
          columns={columns}
          data={pipelines}
          emptyMessage="No pipeline data available. Connect your CI/CD system to see pipeline status."
        />
      </Card>
    </div>
  );
}
