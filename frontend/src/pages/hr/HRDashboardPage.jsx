import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import {
  Users,
  Building2,
  Award,
  UserPlus,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';

export function HRDashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'hr'],
    queryFn: () => rolesApi.getHRDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading People & HR dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};
  const employees = data?.employees || [];
  const roleDistribution = summary.role_distribution || {};

  const employeeColumns = [
    { key: 'name', header: 'Name', render: (e) => <span style={{ fontWeight: '700' }}>{e.name}</span> },
    { key: 'employee_id', header: 'Employee ID', render: (e) => <span className="font-mono">{e.employee_id}</span> },
    { key: 'role', header: 'Role', render: (e) => e.role },
    { key: 'dept', header: 'Department', render: (e) => e.dept },
    { key: 'team_id', header: 'Team', render: (e) => e.team_id || 'Unassigned' },
    {
      key: 'action',
      header: 'Profile',
      render: (e) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/performance?developer=${e.employee_id}`)}
        >
          Performance
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="People & Organizational Structure Dashboard"
        subtitle="Manage employee records, organizational roles, team capacity, and overall workforce performance."
        actions={
          <Button
            variant="primary"
            leftIcon={<UserPlus size={16} />}
            onClick={() => navigate('/employees')}
          >
            Manage Employees
          </Button>
        }
      />

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <MetricCard
          title="Total Workforce"
          value={summary.total_employees || employees.length || 0}
          subtitle="Active employees"
          icon={<Users size={20} />}
          color="primary"
          onClick={() => navigate('/employees')}
        />
        <MetricCard
          title="Engineering Teams"
          value="4"
          subtitle="Structured teams"
          icon={<Building2 size={20} />}
          color="cyan"
          onClick={() => navigate('/teams')}
        />
        <MetricCard
          title="Performance Average"
          value="84.6%"
          subtitle="Organization wide average"
          icon={<Award size={20} />}
          color="purple"
          onClick={() => navigate('/performance')}
        />
        <MetricCard
          title="Talent Growth Index"
          value="+6.2%"
          subtitle="Quarter-over-quarter trend"
          icon={<TrendingUp size={20} />}
          color="success"
        />
      </div>

      {/* Role Distribution Summary */}
      <Card
        title="Workforce Role Breakdown"
        subtitle="Distribution across organizational responsibilities"
        style={{ marginBottom: '1.75rem' }}
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem' }}>
          {Object.entries(roleDistribution).map(([roleName, count]) => (
            <div
              key={roleName}
              style={{
                padding: '0.75rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-subtle)',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.2rem',
                minWidth: '130px',
              }}
            >
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                {roleName}
              </span>
              <span style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                {count}
              </span>
            </div>
          ))}
        </div>
      </Card>

      {/* Recent Employees Table */}
      <Card
        title="Employee Directory"
        subtitle="Recent active personnel"
        action={
          <Button variant="ghost" size="sm" onClick={() => navigate('/employees')}>
            Full Directory <ArrowRight size={14} />
          </Button>
        }
      >
        <Table
          columns={employeeColumns}
          data={employees.slice(0, 5)}
          emptyMessage="No employees registered yet."
        />
      </Card>
    </div>
  );
}
