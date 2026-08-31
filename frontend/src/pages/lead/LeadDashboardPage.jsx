import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import {
  Users,
  GitPullRequest,
  AlertTriangle,
  Layers,
  MessageSquareQuote,
  ShieldAlert,
  ArrowRight,
} from 'lucide-react';

export function LeadDashboardPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'lead'],
    queryFn: () => rolesApi.getLeadDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading Tech Lead dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};
  const teamMembers = data?.team_members || [];
  const reviewQueue = data?.pr_review_queue || [];
  const blockers = data?.blockers || [];

  const memberColumns = [
    { key: 'name', header: 'Member', render: (m) => <span style={{ fontWeight: '700' }}>{m.name}</span> },
    { key: 'role', header: 'Role', render: (m) => m.role },
    { key: 'email', header: 'Email', render: (m) => <span style={{ color: 'var(--text-muted)' }}>{m.email}</span> },
    {
      key: 'actions',
      header: 'Actions',
      render: (m) => (
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            navigate(`/feedback?target=${m.employee_id}`);
          }}
        >
          Give Feedback
        </Button>
      ),
    },
  ];

  const prColumns = [
    { key: 'title', header: 'PR Title', render: (pr) => <span style={{ fontWeight: '600' }}>{pr.title || `PR #${pr.pr_number || pr.id}`}</span> },
    { key: 'author_id', header: 'Author', render: (pr) => pr.author_name || pr.author_id || 'Unknown' },
    { key: 'risk_level', header: 'Risk', render: (pr) => <RiskBadge level={pr.risk_level || 'LOW'} score={pr.risk_score} /> },
    {
      key: 'action',
      header: 'Review',
      render: () => <Button variant="secondary" size="sm">Inspect</Button>,
    },
  ];

  return (
    <div>
      <PageHeader
        title={`Tech Lead Dashboard — ${data?.team_id || 'Team Overview'}`}
        subtitle="Monitor team execution, review pipeline, high-risk PRs, and team impediments."
        actions={
          <Button
            variant="primary"
            leftIcon={<MessageSquareQuote size={16} />}
            onClick={() => navigate('/feedback')}
          >
            Submit Lead Feedback
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
          title="Team Size"
          value={summary.team_size || teamMembers.length || 0}
          subtitle="Active engineers"
          icon={<Users size={20} />}
          color="primary"
          onClick={() => navigate('/teams')}
        />
        <MetricCard
          title="PR Review Queue"
          value={summary.open_prs || 0}
          subtitle="Waiting for team review"
          icon={<GitPullRequest size={20} />}
          color="purple"
        />
        <MetricCard
          title="High Risk PRs"
          value={summary.high_risk_prs || 0}
          subtitle="Detected by Layer 5 engine"
          icon={<ShieldAlert size={20} />}
          color={summary.high_risk_prs > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          title="Blocked Tasks"
          value={summary.blocked_tasks || 0}
          subtitle="Impediments blocking progress"
          icon={<AlertTriangle size={20} />}
          color={summary.blocked_tasks > 0 ? 'warning' : 'success'}
          onClick={() => navigate('/board')}
        />
      </div>

      {/* Tables Row: Team Members & Review Queue */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(460px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card
          title="Team Members & Workload"
          subtitle="Engineers in your assigned team"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/teams')}>
              Manage Team
            </Button>
          }
        >
          <Table
            columns={memberColumns}
            data={teamMembers}
            emptyMessage="No team members assigned yet."
          />
        </Card>

        <Card
          title="PR Review Queue"
          subtitle="Open pull requests needing attention"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/github/sync')}>
              View All PRs
            </Button>
          }
        >
          <Table
            columns={prColumns}
            data={reviewQueue}
            emptyMessage="No pending PRs in the review queue."
          />
        </Card>
      </div>

      {/* Blockers alert list if any */}
      {blockers.length > 0 && (
        <Card title="Active Team Blockers" subtitle="Tasks flagged as blocked">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            {blockers.map((b) => (
              <div
                key={b.id}
                style={{
                  padding: '0.85rem 1rem',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: 'var(--danger-light)',
                  border: '1px solid var(--danger-border)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div>
                  <div style={{ fontWeight: '700', fontSize: '0.875rem', color: 'var(--danger)' }}>
                    {b.title}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    Assignee: {b.assignee_id || 'Unassigned'} • Due: {b.due_date || 'N/A'}
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => navigate('/board')}>
                  Resolve on Board
                </Button>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  );
}
