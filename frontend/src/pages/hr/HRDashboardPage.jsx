import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { transfersApi } from '../../api/transfers.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { BarList, SegmentedBar } from '../../components/charts/Charts';
import { ROLE_LABELS } from '../../utils/constants';
import '../../components/dashboard/Dashboard.css';
import { UserPlus, ArrowRight } from 'lucide-react';

// CEO and HR work across the organisation and are not placed in a team.
const ORG_WIDE_ROLES = new Set(['CEO', 'HR']);

export function HRDashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'hr'],
    queryFn: () => rolesApi.getHRDashboard(),
  });

  const { data: transfersData } = useQuery({
    queryKey: ['transfers', 'pending'],
    queryFn: () => transfersApi.getTransfers({ status: 'pending' }),
  });

  if (isLoading) return <LoadingState message="Loading the people dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};
  const employees = data?.employees || [];
  const roleDistribution = summary.role_distribution || {};
  const pendingTransfers = Array.isArray(transfersData)
    ? transfersData.length
    : (transfersData?.transfers?.length || 0);

  const departments = employees.reduce((counts, e) => {
    const dept = e.dept || 'No department';
    counts[dept] = (counts[dept] || 0) + 1;
    return counts;
  }, {});
  const teamRoles = employees.filter((e) => !ORG_WIDE_ROLES.has(e.role));
  const inTeam = teamRoles.filter((e) => e.team_id).length;
  const withoutTeam = teamRoles.length - inTeam;

  const employeeColumns = [
    { key: 'name', header: 'Name', render: (e) => <span style={{ fontWeight: '600' }}>{e.name}</span> },
    { key: 'employee_id', header: 'Employee ID', render: (e) => <span className="font-mono" style={{ fontSize: '0.8125rem' }}>{e.employee_id}</span> },
    { key: 'role', header: 'Role', render: (e) => ROLE_LABELS[e.role] || e.role },
    { key: 'dept', header: 'Department', render: (e) => e.dept || '—' },
    { key: 'team_id', header: 'Team', render: (e) => e.team_id || (ORG_WIDE_ROLES.has(e.role) ? '—' : 'Unassigned') },
    {
      key: 'action',
      header: '',
      align: 'right',
      render: (e) => (ORG_WIDE_ROLES.has(e.role) ? null : (
        <Button variant="ghost" size="sm" onClick={() => navigate(`/performance?developer=${e.employee_id}`)}>
          Performance
        </Button>
      )),
    },
  ];

  return (
    <div className="dash">
      <PageHeader
        title="People and organisation"
        subtitle="Workforce, teams and transfers."
        actions={
          <Button variant="primary" leftIcon={<UserPlus size={16} />} onClick={() => navigate('/employees')}>
            Manage employees
          </Button>
        }
      />

      <div className="dash-kpis">
        <MetricCard
          title="Active employees"
          value={summary.total_employees ?? employees.length}
          subtitle={`${Object.keys(roleDistribution).length} roles`}
          onClick={() => navigate('/employees')}
        />
        <MetricCard
          title="Pending transfers"
          value={pendingTransfers}
          subtitle="Awaiting decision"
          onClick={() => navigate('/transfers')}
        />
        <MetricCard
          title="Departments"
          value={Object.keys(departments).length}
          subtitle="With active staff"
        />
        <MetricCard
          title="Not in a team"
          value={withoutTeam}
          subtitle="No team assigned"
        />
      </div>

      <div className="dash-row">
        <Card title="Workforce by role">
          <BarList
            label="Employees"
            emptyText="No employees yet."
            items={Object.entries(roleDistribution).map(([role, count]) => ({
              key: role,
              label: ROLE_LABELS[role] || role,
              value: count,
            }))}
          />
          <h4 className="dash-sub">Team placement</h4>
          <SegmentedBar
            label="Team placement"
            emptyText="No data yet."
            parts={[
              { label: 'In a team', value: inTeam, tone: 'blue' },
              { label: 'Not in a team', value: withoutTeam, tone: 'warning' },
            ]}
          />
        </Card>

        <Card title="Workforce by department">
          <BarList
            label="Employees"
            emptyText="No employees yet."
            items={Object.entries(departments).map(([dept, count]) => ({ key: dept, label: dept, value: count }))}
          />
        </Card>
      </div>

      <Card
        title="Employee directory"
        action={
          <Button variant="ghost" size="sm" rightIcon={<ArrowRight size={14} />} onClick={() => navigate('/employees')}>
            Full directory
          </Button>
        }
      >
        <Table columns={employeeColumns} data={employees.slice(0, 6)} emptyMessage="No employees yet." />
      </Card>
    </div>
  );
}
