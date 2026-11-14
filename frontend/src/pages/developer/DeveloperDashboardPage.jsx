import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { performanceApi } from '../../api/performance.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { ScoreCard } from '../../components/common/ScoreCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { SegmentedBar } from '../../components/charts/Charts';
import '../../components/dashboard/Dashboard.css';
import { ListTodo, CheckCircle2, GitPullRequest, Sparkles, ArrowRight, AlertTriangle, KanbanSquare } from 'lucide-react';

const RISK_LEVELS = [
  { key: 'LOW', label: 'Low', tone: 'good' },
  { key: 'MEDIUM', label: 'Medium', tone: 'warning' },
  { key: 'HIGH', label: 'High', tone: 'serious' },
  { key: 'CRITICAL', label: 'Critical', tone: 'critical' },
];

export function DeveloperDashboardPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const employeeId = user?.employee_id;

  const {
    data: dashboardData,
    isLoading: isRoleLoading,
    error: roleError,
    refetch: refetchRole,
  } = useQuery({
    queryKey: ['role-dashboard', 'developer'],
    queryFn: () => rolesApi.getDeveloperDashboard(),
  });

  const { data: perfData } = useQuery({
    queryKey: ['developer-performance', employeeId],
    queryFn: () => performanceApi.getDeveloperDashboard(employeeId),
    retry: 1,
  });

  if (isRoleLoading) return <LoadingState message="Loading your dashboard..." />;
  if (roleError) return <ErrorState message={roleError.message} onRetry={refetchRole} />;

  const summary = dashboardData?.summary || {};
  const myTasks = dashboardData?.my_tasks || [];
  const myPrs = dashboardData?.my_prs || [];
  const currPerf = perfData?.current_performance;
  const total = summary.total_tasks || 0;
  const done = summary.completed_tasks || 0;
  const inProgress = summary.in_progress_tasks || 0;
  const blocked = summary.blocked_tasks || 0;
  const otherTasks = Math.max(total - done - inProgress - blocked, 0);
  const prRisk = myPrs.reduce((counts, pr) => {
    const level = String(pr.risk_level || 'LOW').toUpperCase();
    counts[level] = (counts[level] || 0) + 1;
    return counts;
  }, {});
  const recommendations = currPerf?.ai_evaluation?.recommendations || [];

  const taskColumns = [
    { key: 'title', header: 'Task', render: (t) => <span style={{ fontWeight: '600' }}>{t.title}</span> },
    { key: 'priority', header: 'Priority', render: (t) => <span style={{ textTransform: 'capitalize' }}>{t.priority || '—'}</span> },
    { key: 'status', header: 'Status', render: (t) => <StatusBadge status={t.status} /> },
    { key: 'due_date', header: 'Due', render: (t) => t.due_date || '—' },
  ];

  const prColumns = [
    { key: 'title', header: 'Pull request', render: (pr) => <span style={{ fontWeight: '600' }}>{pr.title || `PR #${pr.pr_number || pr.id}`}</span> },
    { key: 'risk_level', header: 'Risk', render: (pr) => <RiskBadge level={pr.risk_level || 'LOW'} score={pr.risk_score} /> },
    { key: 'repo', header: 'Repository', render: (pr) => pr.repo || pr.project_id || '—' },
  ];

  return (
    <div className="dash">
      <PageHeader
        title={`Welcome back, ${user?.name || 'there'}`}
        subtitle="Your tasks, pull requests and evaluation."
        actions={
          <Button variant="primary" leftIcon={<KanbanSquare size={16} />} onClick={() => navigate('/board')}>
            Open board
          </Button>
        }
      />

      <div className="dash-kpis">
        <MetricCard
          title="In progress"
          value={inProgress}
          subtitle={`${total} assigned`}
          icon={<ListTodo size={18} />}
          color="primary"
          onClick={() => navigate('/tasks')}
        />
        <MetricCard
          title="Completed"
          value={done}
          subtitle={total ? `${Math.round((done / total) * 100)}% complete` : 'No tasks yet'}
          icon={<CheckCircle2 size={18} />}
          color="success"
        />
        <MetricCard
          title="Blocked"
          value={blocked}
          subtitle={blocked ? 'Needs attention' : 'None blocked'}
          icon={<AlertTriangle size={18} />}
          color={blocked > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          title="Open pull requests"
          value={summary.open_prs ?? 0}
          subtitle="In review"
          icon={<GitPullRequest size={18} />}
          color="purple"
          onClick={() => navigate('/pull-requests')}
        />
      </div>

      <div className="dash-row">
        <Card title="My tasks by status">
          <SegmentedBar
            label="My tasks by status"
            emptyText="No tasks yet."
            parts={[
              { label: 'Done', value: done, tone: 'good' },
              { label: 'In progress', value: inProgress, tone: 'blue' },
              { label: 'Blocked', value: blocked, tone: 'critical' },
              { label: 'To do and other', value: otherTasks, tone: 'neutral' },
            ]}
          />
          <h4 className="dash-sub">Pull requests by risk</h4>
          <SegmentedBar
            label="My open pull requests by risk"
            emptyText="No open pull requests."
            parts={RISK_LEVELS.map((level) => ({ label: level.label, value: prRisk[level.key] || 0, tone: level.tone }))}
          />
        </Card>

        <ScoreCard
          title="Engineering score"
          score={currPerf?.overall_score ?? currPerf?.final_score ?? null}
          grade={currPerf?.grade || 'N/A'}
          aiScore={currPerf?.ai_evaluation?.overall_score ?? currPerf?.ai_evaluation?.score ?? null}
          humanScore={currPerf?.role_evaluation?.average_score ?? null}
          confidence={currPerf?.ai_evaluation?.confidence_score ?? null}
          period={currPerf?.period || currPerf?.period_label || 'No evaluation period'}
        />
      </div>

      <Card
        title="AI evaluation insights"
        action={
          <Button variant="ghost" size="sm" rightIcon={<ArrowRight size={14} />} onClick={() => navigate('/performance')}>
            Full breakdown
          </Button>
        }
      >
        <div className="dash-note">
          <Sparkles size={18} aria-hidden="true" />
          <div>
            {currPerf?.ai_evaluation?.evaluation_summary || currPerf?.ai_evaluation?.reasoning || 'No AI evaluation is available yet.'}
            {recommendations.length > 0 && (
              <ul style={{ paddingLeft: '1.1rem', marginTop: '0.5rem', display: 'grid', gap: '0.3rem' }}>
                {recommendations.slice(0, 3).map((rec, idx) => <li key={idx}>{rec}</li>)}
              </ul>
            )}
          </div>
        </div>
      </Card>

      <div className="dash-row">
        <Card
          title="My active tasks"
          action={<Button variant="ghost" size="sm" onClick={() => navigate('/tasks')}>View all</Button>}
        >
          <Table
            columns={taskColumns}
            data={myTasks.slice(0, 5)}
            emptyMessage="No tasks yet."
            onRowClick={() => navigate('/tasks')}
          />
        </Card>

        <Card
          title="My open pull requests"
          action={<Button variant="ghost" size="sm" onClick={() => navigate('/pull-requests')}>View all</Button>}
        >
          <Table
            columns={prColumns}
            data={myPrs.slice(0, 5)}
            emptyMessage="No open pull requests."
            onRowClick={() => navigate('/pull-requests')}
          />
        </Card>
      </div>
    </div>
  );
}
