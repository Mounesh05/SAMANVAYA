import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ShieldAlert, AlertTriangle, Activity } from 'lucide-react';

export function CEORiskPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'ceo'],
    queryFn: () => rolesApi.getCEODashboard(),
  });

  if (isLoading) return <LoadingState message="Loading risk overview..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Organization Risk"
        subtitle="Critical risks and incident overview across all projects."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.75rem' }}>
        <MetricCard
          title="Critical Risks"
          value={data?.critical_risks || 0}
          icon={<ShieldAlert size={20} />}
          color="red"
        />
        <MetricCard
          title="Active Incidents"
          value={data?.active_incidents || 0}
          icon={<AlertTriangle size={20} />}
          color="orange"
        />
        <MetricCard
          title="Delivery Confidence"
          value={data?.delivery_confidence || 'N/A'}
          icon={<Activity size={20} />}
          color="blue"
        />
      </div>

      <Card>
        <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '1rem' }}>Risk Summary</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Aggregated risk view from all project risk engines. Critical risks require immediate executive attention.
        </p>
      </Card>
    </div>
  );
}
