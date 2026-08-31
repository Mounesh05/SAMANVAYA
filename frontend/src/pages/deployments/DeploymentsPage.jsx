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
import { Rocket, CheckCircle, XCircle, Clock } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';

export function DeploymentsPage() {
  const { data: deploymentData, isLoading, error, refetch } = useQuery({
    queryKey: ['deployments'],
    queryFn: () => rolesApi.getDeployments(),
    retry: 1,
  });

  const deployments = deploymentData?.deployments || [];

  const columns = [
    {
      key: 'id',
      header: 'Deployment ID',
      render: (d) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700' }}>{d.id}</span>
      ),
    },
    {
      key: 'service',
      header: 'Service',
      render: (d) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Rocket size={14} style={{ color: 'var(--primary)' }} />
          <span style={{ fontWeight: '600' }}>{d.service}</span>
        </div>
      ),
    },
    {
      key: 'environment',
      header: 'Environment',
      render: (d) => (
        <Badge variant={d.environment === 'production' ? 'danger' : d.environment === 'staging' ? 'warning' : 'info'} size="sm">
          {d.environment?.toUpperCase() || 'DEV'}
        </Badge>
      ),
    },
    {
      key: 'version',
      header: 'Version',
      render: (d) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
          {d.version || '—'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (d) => {
        const statusVariant = {
          success: 'success',
          failed: 'danger',
          rolling_back: 'warning',
          pending: 'info',
        };
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            {d.status === 'success' && <CheckCircle size={14} style={{ color: 'var(--success)' }} />}
            {d.status === 'failed' && <XCircle size={14} style={{ color: 'var(--danger)' }} />}
            {d.status === 'pending' && <Clock size={14} style={{ color: 'var(--warning)' }} />}
            <Badge variant={statusVariant[d.status] || 'default'} size="sm">
              {d.status?.toUpperCase() || 'UNKNOWN'}
            </Badge>
          </div>
        );
      },
    },
    { key: 'deployed_by', header: 'Deployed By', render: (d) => d.deployed_by || '—' },
    {
      key: 'deployed_at',
      header: 'Deployed At',
      render: (d) => (
        <span title={formatDate(d.deployed_at)}>
          {timeAgo(d.deployed_at)}
        </span>
      ),
    },
    {
      key: 'rollback',
      header: 'Rollback',
      render: (d) => d.rollback_available ? (
        <Badge variant="warning" size="sm">Available</Badge>
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>—</span>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading deployments..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Deployments"
        subtitle="Track deployment history, status, and rollback availability."
      />

      {/* Summary Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <MetricCard
          title="Total Deployments"
          value={deployments.length}
          icon={<Rocket size={20} />}
          color="primary"
        />
        <MetricCard
          title="Successful"
          value={deployments.filter((d) => d.status === 'success').length}
          icon={<CheckCircle size={20} />}
          color="success"
        />
        <MetricCard
          title="Failed"
          value={deployments.filter((d) => d.status === 'failed').length}
          icon={<XCircle size={20} />}
          color="danger"
        />
        <MetricCard
          title="Pending"
          value={deployments.filter((d) => d.status === 'pending').length}
          icon={<Clock size={20} />}
          color="warning"
        />
      </div>

      {/* Deployments Table */}
      <Card title="Deployment History" subtitle="Recent deployments across services and environments">
        <Table
          columns={columns}
          data={deployments}
          emptyMessage="No deployment data available. Connect your deployment system to see history."
        />
      </Card>
    </div>
  );
}
