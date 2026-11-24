import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { RiskBadge } from '../../components/common/RiskBadge';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { BarList, SegmentedBar } from '../../components/charts/Charts';
import { ROLE_LABELS } from '../../utils/constants';
import '../../components/dashboard/Dashboard.css';
import { AlertTriangle, MessageSquareQuote } from 'lucide-react';

const RISK_LEVELS = [
  { key: 'LOW', label: 'Low', tone: 'good' },
  { key: 'MEDIUM', label: 'Medium', tone: 'warning' },
  { key: 'HIGH', label: 'High', tone: 'serious' },
  { key: 'CRITICAL', label: 'Critical', tone: 'critical' },
];

export function LeadDashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'lead'],
    queryFn: () => rolesApi.getLeadDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading the team dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};
  const teamMembers = data?.team_members || [];
  const reviewQueue = data?.pr_review_queue || [];
  const blockers = data?.blockers || [];
  const nameOf = Object.fromEntries(teamMembers.map((m) => [m.employee_id, m.name]));

  const riskCounts = reviewQueue.reduce((counts, pr) => {
    const level = String(pr.risk_level || 'LOW').toUpperCase();
    counts[level] = (counts[level] || 0) + 1;
    return counts;
  }, {});
  const prsByAuthor = reviewQueue.reduce((counts, pr) => {
    const author = pr.author_id || 'unknown';
    counts[author] = (counts[author] || 0) + 1;
    return counts;
  }, {});
  const queueNote = summary.open_prs > reviewQueue.length
    ? `Latest ${reviewQueue.length} of ${summary.open_prs}`
    : undefined;

  const memberColumns = [
    { key: 'name', header: 'Member', render: (m) => <span style={{ fontWeight: '600' }}>{m.name}</span> },
    { key: 'role', header: 'Role', render: (m) => ROLE_LABELS[m.role] || m.role },
    { key: 'email', header: 'Email', render: (m) => <span style={{ color: 'var(--text-muted)' }}>{m.email}</span> },
  ];

  const prColumns = [
    { key: 'title', header: 'Pull request', render: (pr) => <span style={{ fontWeight: '600' }}>{pr.title || `PR #${pr.pr_number || pr.id}`}</span> },
    { key: 'author_id', header: 'Author', render: (pr) => pr.author_name || nameOf[pr.author_id] || pr.author_id || 'Unknown' },
    { key: 'risk_level', header: 'Risk', render: (pr) => <RiskBadge level={pr.risk_level || 'LOW'} score={pr.risk_score} /> },
  ];

  return (
    <div className="dash">
      <PageHeader
        title={data?.team_id ? `Team overview · ${data.team_id}` : 'Team overview'}
        subtitle="Reviews, risk and blockers."
        actions={
          <Button variant="primary" leftIcon={<MessageSquareQuote size={16} />} onClick={() => navigate('/feedback')}>
            Assigned feedback
          </Button>
        }
      />

      {data?.error && (
        <Card>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Not assigned to a team yet.
          </p>
        </Card>
      )}

      <div className="dash-kpis">
        <MetricCard
          title="Team size"
          value={summary.team_size ?? teamMembers.length}
          subtitle={`${summary.total_active_tasks ?? 0} active tasks`}
          onClick={() => navigate('/teams')}
        />
        <MetricCard
          title="Open pull requests"
          value={summary.open_prs ?? 0}
          subtitle="Waiting for review"
        />
        <MetricCard
          title="High-risk pull requests"
          value={summary.high_risk_prs ?? 0}
          subtitle="AI-rated high or critical"
        />
        <MetricCard
          title="Blocked tasks"
          value={summary.blocked_tasks ?? 0}
          subtitle="Need attention"
          onClick={() => navigate('/board')}
        />
      </div>

      <div className="dash-row">
        <Card title="Review queue by risk" subtitle={queueNote}>
          <SegmentedBar
            label="Review queue by risk"
            emptyText="The review queue is empty."
            parts={RISK_LEVELS.map((level) => ({ label: level.label, value: riskCounts[level.key] || 0, tone: level.tone }))}
          />
        </Card>
        <Card title="Pull requests by author" subtitle={queueNote}>
          <BarList
            label="Open pull requests"
            emptyText="No open pull requests."
            items={Object.entries(prsByAuthor).map(([author, count]) => ({
              key: author,
              label: nameOf[author] || author,
              value: count,
            }))}
          />
        </Card>
      </div>

      {blockers.length > 0 && (
        <Card title="Blocked work">
          <ul className="dash-list">
            {blockers.map((b) => (
              <li key={b.id}>
                <div className="dash-list-main">
                  <div className="dash-list-title">
                    <AlertTriangle size={14} style={{ color: 'var(--viz-critical)', marginRight: '0.4rem', verticalAlign: '-2px' }} aria-hidden="true" />
                    {b.title}
                  </div>
                  <div className="dash-list-meta">
                    {nameOf[b.assignee_id] || b.assignee_id || 'Unassigned'} · Due {b.due_date || 'not set'}
                  </div>
                </div>
                <Button variant="secondary" size="sm" onClick={() => navigate('/board')}>
                  Open board
                </Button>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <div className="dash-row">
        <Card
          title="Team members"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/teams')}>
              Manage team
            </Button>
          }
        >
          <Table columns={memberColumns} data={teamMembers} emptyMessage="No team members assigned yet." />
        </Card>

        <Card
          title="Review queue"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/pull-requests')}>
              All pull requests
            </Button>
          }
        >
          <Table columns={prColumns} data={reviewQueue} emptyMessage="Queue is empty." />
        </Card>
      </div>
    </div>
  );
}
