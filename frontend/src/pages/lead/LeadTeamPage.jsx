/**
 * Lead Team page — team member workload + PR review queue
 */
import { useQuery } from '@tanstack/react-query';
import apiClient from '../../api/client';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, RiskBadge } from '../../components/common/Badges';
import { formatDate, timeAgo } from '../../utils/dates';
import { GitPullRequest, User, CheckSquare, AlertTriangle } from 'lucide-react';

export function LeadTeamPage() {
  const { data: teamData, isLoading: teamLoading, isError: teamError, refetch } = useQuery({
    queryKey: ['lead-team'],
    queryFn: () => apiClient.get('/api/role/lead/team').then(r => r.data),
  });

  const { data: prData } = useQuery({
    queryKey: ['lead-review-queue'],
    queryFn: () => apiClient.get('/api/role/lead/review-queue').then(r => r.data),
  });

  const members = teamData?.team_members || [];
  const prs = prData?.pending_review || [];

  if (teamLoading) return <LoadingState message="Loading team data…" />;
  if (teamError) return <ErrorState onRetry={refetch} />;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">My Team</h1>
          <p className="page-subtitle">{members.length} member{members.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      <div className="grid-2">
        {/* Workload cards */}
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <User size={16} style={{ color: 'var(--brand-400)' }} />
              <div className="card-title">Team Workload</div>
            </div>
          </div>
          {members.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {members.map((m) => (
                <div key={m.employee_id} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
                  <div className="avatar avatar-sm">{m.name?.charAt(0)}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.875rem' }}>{m.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {m.in_progress} in progress · {m.blocked} blocked
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)' }}>{m.total_tasks}</div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>tasks</div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No team members" description="You are not assigned to a team" />
          )}
        </div>

        {/* PR review queue */}
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <GitPullRequest size={16} style={{ color: 'var(--brand-400)' }} />
              <div className="card-title">PR Review Queue</div>
            </div>
            <span className="badge badge-warning">{prs.length} pending</span>
          </div>
          {prs.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {prs.slice(0, 8).map((pr, i) => (
                <div key={pr._id || pr.pr_id || i} style={{ padding: '8px 12px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                    <div style={{ fontWeight: 500, fontSize: '0.8125rem', flex: 1, marginRight: 8 }}>
                      {pr.title || `PR #${pr.pr_number || i + 1}`}
                    </div>
                    {pr.risk_level && <RiskBadge risk={pr.risk_level} />}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {pr.author_name || pr.author} · {timeAgo(pr.created_at)}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No PRs pending review" description="All team PRs are reviewed!" />
          )}
        </div>
      </div>
    </div>
  );
}
