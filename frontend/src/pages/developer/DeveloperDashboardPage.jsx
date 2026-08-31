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
import {
  ListTodo,
  CheckCircle2,
  Clock,
  GitPullRequest,
  Sparkles,
  ArrowRight,
  ShieldCheck,
  AlertTriangle,
  KanbanSquare,
} from 'lucide-react';

export function DeveloperDashboardPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const employeeId = user?.employee_id;

  // Role dashboard data
  const {
    data: dashboardData,
    isLoading: isRoleLoading,
    error: roleError,
    refetch: refetchRole,
  } = useQuery({
    queryKey: ['role-dashboard', 'developer'],
    queryFn: () => rolesApi.getDeveloperDashboard(),
  });

  // Developer Performance data
  const {
    data: perfData,
    isLoading: isPerfLoading,
  } = useQuery({
    queryKey: ['developer-performance', employeeId],
    queryFn: () => performanceApi.getDeveloperDashboard(employeeId),
    retry: 1,
  });

  if (isRoleLoading) {
    return <LoadingState message="Loading your developer dashboard..." />;
  }

  if (roleError) {
    return <ErrorState message={roleError.message} onRetry={refetchRole} />;
  }

  const summary = dashboardData?.summary || {};
  const myTasks = dashboardData?.my_tasks || [];
  const myPrs = dashboardData?.my_prs || [];
  const currPerf = perfData?.current_performance;

  const taskColumns = [
    { key: 'title', header: 'Task', render: (t) => <span style={{ fontWeight: '600' }}>{t.title}</span> },
    { key: 'priority', header: 'Priority', render: (t) => <span style={{ textTransform: 'capitalize' }}>{t.priority}</span> },
    { key: 'status', header: 'Status', render: (t) => <StatusBadge status={t.status} /> },
    { key: 'due_date', header: 'Due Date', render: (t) => t.due_date || '—' },
  ];

  const prColumns = [
    { key: 'title', header: 'Pull Request', render: (pr) => <span style={{ fontWeight: '600' }}>{pr.title || `PR #${pr.pr_number || pr.id}`}</span> },
    { key: 'status', header: 'Status', render: (pr) => <StatusBadge status={pr.status} /> },
    { key: 'risk_level', header: 'Risk', render: (pr) => <RiskBadge level={pr.risk_level || 'LOW'} score={pr.risk_score} /> },
    { key: 'repo', header: 'Repository', render: (pr) => pr.repo || pr.project_id || '—' },
  ];

  return (
    <div>
      <PageHeader
        title={`Welcome back, ${user?.name || 'Developer'}`}
        subtitle="Here is your personal work summary, engineering quality metrics, and performance."
        actions={
          <Button
            variant="primary"
            leftIcon={<KanbanSquare size={16} />}
            onClick={() => navigate('/board')}
          >
            Open Kanban Board
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
          title="Active Tasks"
          value={summary.in_progress_tasks || 0}
          subtitle={`Total assigned: ${summary.total_tasks || 0}`}
          icon={<ListTodo size={20} />}
          color="primary"
          onClick={() => navigate('/tasks')}
        />
        <MetricCard
          title="Completed Tasks"
          value={summary.completed_tasks || 0}
          subtitle="Tasks marked Done"
          icon={<CheckCircle2 size={20} />}
          color="success"
        />
        <MetricCard
          title="Blocked Work"
          value={summary.blocked_tasks || 0}
          subtitle="Requires attention"
          icon={<AlertTriangle size={20} />}
          color={summary.blocked_tasks > 0 ? 'danger' : 'warning'}
        />
        <MetricCard
          title="Open PRs"
          value={summary.open_prs || 0}
          subtitle="In review pipeline"
          icon={<GitPullRequest size={20} />}
          color="purple"
          onClick={() => navigate('/github/sync')}
        />
      </div>

      {/* Performance & AI Recommendations Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        {/* Score Card */}
        <ScoreCard
          title="Personal Engineering Score"
          score={currPerf?.overall_score || 85.0}
          grade={currPerf?.grade || 'A'}
          aiScore={currPerf?.ai_evaluation?.overall_score || 86.5}
          humanScore={80.0}
          confidence={currPerf?.ai_evaluation?.confidence_score || 85}
          period={currPerf?.period || 'Current Quarter'}
        />

        {/* AI Recommendations Card */}
        <Card
          title="AI Engineering Insights"
          subtitle="Real-time feedback generated by Intelligence Engine"
          action={
            <Button
              variant="ghost"
              size="sm"
              rightIcon={<ArrowRight size={14} />}
              onClick={() => navigate('/performance')}
            >
              Full Breakdown
            </Button>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            <div
              style={{
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(59, 130, 246, 0.08)',
                border: '1px solid rgba(59, 130, 246, 0.2)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.65rem',
              }}
            >
              <Sparkles size={18} style={{ color: 'var(--cyan)', flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Code Quality & Test Coverage
                </div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.2rem', lineHeight: '1.4' }}>
                  {currPerf?.ai_evaluation?.evaluation_summary ||
                    'Strong code structure and commit hygiene. Consider adding edge-case unit tests to improve reliability.'}
                </p>
              </div>
            </div>

            {currPerf?.ai_evaluation?.recommendations && currPerf.ai_evaluation.recommendations.length > 0 ? (
              <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                {currPerf.ai_evaluation.recommendations.slice(0, 2).map((rec, idx) => (
                  <li key={idx}>{rec}</li>
                ))}
              </ul>
            ) : null}
          </div>
        </Card>
      </div>

      {/* Tables Row: My Tasks & Open PRs */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(450px, 1fr))',
          gap: '1.5rem',
        }}
      >
        <Card
          title="My Active Tasks"
          subtitle="Tasks currently assigned to you"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/tasks')}>
              View All
            </Button>
          }
        >
          <Table
            columns={taskColumns}
            data={myTasks.slice(0, 5)}
            emptyMessage="No assigned tasks found. Enjoy your day!"
            onRowClick={() => navigate('/tasks')}
          />
        </Card>

        <Card
          title="My Open Pull Requests"
          subtitle="Pull requests undergoing review and risk checks"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/github/sync')}>
              View All
            </Button>
          }
        >
          <Table
            columns={prColumns}
            data={myPrs.slice(0, 5)}
            emptyMessage="No open pull requests found."
            onRowClick={() => navigate('/github/sync')}
          />
        </Card>
      </div>
    </div>
  );
}
