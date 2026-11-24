import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';


export function CEOQualityPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'ceo'],
    queryFn: () => rolesApi.getCEODashboard(),
  });

  if (isLoading) return <LoadingState message="Loading quality overview..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Organization Quality"
        subtitle="High-level code quality and risk summary across all projects."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))', gap: '1.25rem', marginBottom: '1.75rem' }}>
        <MetricCard
          title="Total Projects"
          value={data?.organization_health?.total_projects || 0}
        />
        <MetricCard
          title="Healthy Projects"
          value={data?.organization_health?.healthy_projects || 0}
        />
        <MetricCard
          title="At Risk"
          value={data?.organization_health?.at_risk_projects || 0}
        />
        <MetricCard
          title="Critical"
          value={data?.organization_health?.critical_projects || 0}
        />
      </div>

      <Card>
        <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>Quality Summary</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Organization-wide quality metrics aggregated from all project code quality analyses.
          Delivery confidence: {data?.delivery_confidence || 'N/A'}.
        </p>
      </Card>
    </div>
  );
}
