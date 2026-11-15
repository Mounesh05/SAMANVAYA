import React, { useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { employeesApi } from '../../api/employees.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { ScoreCard } from '../../components/common/ScoreCard';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { ReadinessPanel } from '../../components/performance/ReadinessPanel';
import { AssessmentHistory } from '../../components/performance/AssessmentHistory';
import { requestError } from '../../utils/performanceScoring';
import { hasAnyPermission, hasPermission, PERMISSIONS } from '../../auth/permissions';
import '../../components/performance/scoring.css';

const SUBJECT_ROLES = ['DEVELOPER', 'QA', 'DEVOPS', 'LEAD', 'PM'];

export function GovernedPerformancePage() {
  const user = useAuthStore((s) => s.user);
  const [params] = useSearchParams();
  const [choice, setChoice] = useState('');
  const seesEveryone = hasAnyPermission(user, [PERMISSIONS.VIEW_ORGANIZATION_PERFORMANCE, PERMISSIONS.VIEW_PERFORMANCE_OUTCOMES]);
  const seesTeam = hasPermission(user, PERMISSIONS.VIEW_TEAM_PERFORMANCE);
  const employees = useQuery({ queryKey: ['performance-employees', user?.employee_id, user?.role],
    queryFn: () => employeesApi.list(), retry: false });
  const visible = useMemo(() => (employees.data || []).filter((employee) => {
    if (!SUBJECT_ROLES.includes(employee.role?.toUpperCase())) return false;
    if (seesEveryone) return true;
    if (employee.employee_id === user?.employee_id) return true;
    return seesTeam && Boolean(user.team_id && employee.team_id === user.team_id);
  }), [employees.data, user, seesEveryone, seesTeam]);
  const requested = choice || params.get('developer') || user?.employee_id;
  const selected = visible.some((e) => e.employee_id === requested) ? requested : visible[0]?.employee_id;
  const dashboard = useQuery({ queryKey: ['developer-performance', user?.employee_id, user?.role, selected],
    queryFn: () => performanceApi.getDeveloperDashboard(selected), enabled: Boolean(selected), retry: false });
  const current = dashboard.data?.current_performance;
  const columns = [
    { key: 'period', header: 'Historical period' },
    { key: 'score', header: 'Historical value (0–100)', render: (r) => typeof r.score === 'number' ? r.score.toFixed(1) : 'Not assessed' },
    { key: 'grade', header: 'Historical grade', render: (r) => r.grade || 'Not established' },
    { key: 'status', header: 'Comparability', render: () => 'Legacy — methodology and coverage unverified' },
  ];
  return <div className="scoring-stack">
    <PageHeader title="Performance records" subtitle="Historical values, evidence limits and immutable assessment decisions. AI explanations do not award points." />
    <ReadinessPanel />
    {employees.isPending ? <p role="status">Loading performance evaluation data...</p> : employees.isError ?
      <div role="alert"><p>{requestError(employees.error)}</p><Button onClick={() => employees.refetch()}>Retry employee list</Button></div> :
      !visible.length ? <Card title="No engineering history available in this scope"><p>No eligible employee is available. HR and CEO are not routine numerical subjects.</p></Card> : <>
        <Select label="Employee" value={selected || ''} placeholder={null} onChange={(e) => setChoice(e.target.value)}
          options={visible.map((e) => ({ value: e.employee_id, label: `${e.name} (${e.role}) — ${e.employee_id}` }))} />
        {dashboard.isPending ? <p role="status">Loading performance evaluation data...</p> : dashboard.isError ?
          <div role="alert"><p>{requestError(dashboard.error)}</p><Button onClick={() => dashboard.refetch()}>Retry performance history</Button></div> : current ?
            <ScoreCard title={`${current.developer_name || selected} — performance record`} score={current.overall_score ?? current.final_score ?? null}
              grade={current.grade} period={current.period || current.period_label} scoring={current.scoring} /> :
            <Card title="No historical numerical record"><p>Missing or unapproved evidence does not create a zero score or a grade.</p></Card>}
        <AssessmentHistory key={`${user?.employee_id}:${selected}`} employeeId={selected} />
        {dashboard.data?.historical_trend?.length > 0 && <Card title="Historical records" subtitle="No cross-methodology performance trend is established.">
          <Table columns={columns} data={dashboard.data.historical_trend} />
        </Card>}
      </>}
  </div>;
}
