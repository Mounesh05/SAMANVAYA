import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Users, Building2, FolderGit2 } from 'lucide-react';

export function CEOOrganizationPage() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'ceo'],
    queryFn: () => rolesApi.getCEODashboard(),
  });

  if (isLoading) return <LoadingState message="Loading organization overview..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Organization Overview"
        subtitle="Executive view of projects, teams, and organizational health."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.25rem', marginBottom: '1.75rem' }}>
        <MetricCard
          title="Total Projects"
          value={data?.organization_health?.total_projects || 0}
          icon={<FolderGit2 size={20} />}
          color="blue"
        />
        <MetricCard
          title="Healthy"
          value={data?.organization_health?.healthy_projects || 0}
          icon={<Building2 size={20} />}
          color="green"
        />
        <MetricCard
          title="At Risk"
          value={data?.organization_health?.at_risk_projects || 0}
          icon={<Users size={20} />}
          color="yellow"
        />
      </div>

      <Card>
        <h3 style={{ fontSize: '1rem', fontWeight: '700', marginBottom: '1rem' }}>Organization Summary</h3>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
          Executive-level view of organizational structure, team health, and project portfolio.
        </p>
      </Card>
    </div>
  );
}
