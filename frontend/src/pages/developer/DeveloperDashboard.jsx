/**
 * Developer Dashboard — "What should I work on and how am I improving?"
 */
import { useQuery } from '@tanstack/react-query';
import { CheckSquare, GitPullRequest, ShieldCheck, TrendingUp, Zap, AlertCircle, Code2 } from 'lucide-react';
import { performanceApi } from '../../api/performance.api';
import { useAuth } from '../../auth/AuthContext';
import { MetricCard } from '../../components/common/ScoreCard';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, PriorityBadge, RiskBadge } from '../../components/common/Badges';
import { formatPercent, scoreColor } from '../../utils/formatters';
import { formatDate, timeAgo } from '../../utils/dates';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export function DeveloperDashboard() {
  const { user } = useAuth();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['developer-dashboard'],
    queryFn: () => performanceApi.getDeveloperDashboard().then((r) => r.data),
  });

  if (isLoading) return <LoadingState message="Loading your dashboard…" />;
  if (isError) return <ErrorState description={error.userMessage} onRetry={refetch} />;

  const perf = data?.performance || {};
  const tasks = data?.tasks || {};
  const sprint = data?.current_sprint || {};
  const prs = data?.pull_requests || {};
  const codeQuality = data?.code_quality || {};
  const risks = data?.risks || [];
  const recommendations = data?.recommendations || [];
  const activity = data?.recent_activity || [];
  const trends = data?.performance_trend || [];

  const overallScore = perf.overall_score ?? perf.score;
  const aiScore = perf.ai_score ?? perf.ai_evaluation_score;
  const humanScore = perf.human_score ?? perf.human_evaluation_score;

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div>
          <h1 className="page-title">My Dashboard</h1>
          <p className="page-subtitle">Welcome back, {user?.name?.split(' ')[0] || 'Developer'}</p>
        </div>
      </div>

      {/* Metrics row */}
      <div className="metric-grid">
        <MetricCard
          label="Overall Performance"
          value={formatPercent(overallScore)}
          icon={TrendingUp}
          iconBg="rgba(99,102,241,0.12)"
          iconColor="var(--brand-400)"
        />
        <MetricCard
          label="AI Evaluation"
          value={formatPercent(aiScore)}
          icon={Code2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Tasks Completed"
          value={`${tasks.completed ?? 0}/${tasks.total ?? 0}`}
          icon={CheckSquare}
          iconBg="rgba(59,130,246,0.1)"
          iconColor="var(--info)"
        />
        <MetricCard
          label="Open PRs"
          value={prs.open ?? 0}
          icon={GitPullRequest}
          iconBg="rgba(245,158,11,0.1)"
          iconColor="var(--warning)"
        />
        <MetricCard
          label="Code Quality"
          value={formatPercent(codeQuality.score)}
          icon={ShieldCheck}
          iconBg="rgba(99,102,241,0.1)"
          iconColor="var(--brand-400)"
        />
        <MetricCard
          label="Sprint Progress"
          value={formatPercent(sprint.completion_percentage)}
          icon={Zap}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
      </div>

      {/* Row: Performance trend + Current sprint */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
        {/* Trend chart */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Performance Trend</div>
              <div className="card-subtitle">Last 30 days</div>
            </div>
          </div>
          {trends.length > 0 ? (
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={trends} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
                <defs>
                  <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--brand-500)" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="var(--brand-500)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="date" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: 'var(--text-secondary)' }}
                  itemStyle={{ color: 'var(--brand-400)' }}
                />
                <Area type="monotone" dataKey="score" stroke="var(--brand-500)" fill="url(#scoreGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="No trend data yet" description="Performance trends will appear as evaluations run" />
          )}
        </div>

        {/* Current Sprint */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">Current Sprint</div>
              <div className="card-subtitle">{sprint.name || 'No active sprint'}</div>
            </div>
            {sprint.status && <StatusBadge status={sprint.status} />}
          </div>
          {sprint.name ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                  <span>Sprint completion</span>
                  <span className={scoreColor(sprint.completion_percentage)}>{formatPercent(sprint.completion_percentage)}</span>
                </div>
                <div className="progress-bar">
                  <div className="progress-fill" style={{ width: `${sprint.completion_percentage || 0}%` }} />
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
                {[
                  { label: 'Stories', value: sprint.story_count ?? '—' },
                  { label: 'Tasks', value: sprint.task_count ?? '—' },
                  { label: 'Done', value: sprint.completed_tasks ?? '—' },
                  { label: 'End Date', value: formatDate(sprint.end_date) },
                ].map((item) => (
                  <div key={item.label} style={{ background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)', padding: '10px 12px' }}>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>{item.label}</div>
                    <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <EmptyState title="No active sprint" description="You're not assigned to any active sprint" />
          )}
        </div>
      </div>

      {/* Row: Risks + Recommendations */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
        {/* Risks */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Risk Indicators</div>
          </div>
          {risks.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {risks.slice(0, 5).map((r, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', background: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
                  <AlertCircle size={16} style={{ color: r.level === 'HIGH' || r.level === 'CRITICAL' ? 'var(--danger)' : 'var(--warning)', flexShrink: 0, marginTop: 2 }} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', marginBottom: 2 }}>{r.description || r.title}</div>
                    <RiskBadge risk={r.level} />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No risks detected" description="Keep up the great work!" />
          )}
        </div>

        {/* AI Recommendations */}
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">AI Recommendations</div>
              <div className="card-subtitle" style={{ color: 'var(--text-muted)', fontSize: '0.6875rem' }}>
                AI-generated · requires human review
              </div>
            </div>
          </div>
          {recommendations.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {recommendations.slice(0, 4).map((rec, i) => (
                <div key={i} style={{ borderLeft: '3px solid var(--brand-500)', paddingLeft: 12, paddingTop: 4, paddingBottom: 4 }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', marginBottom: 4 }}>
                    {rec.recommendation || rec.text || rec.description}
                  </div>
                  {rec.category && (
                    <span className="badge badge-brand">{rec.category}</span>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No recommendations yet" description="Recommendations will appear after evaluation runs" />
          )}
        </div>
      </div>

      {/* Recent Activity */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Recent Activity</div>
        </div>
        {activity.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {activity.slice(0, 8).map((item, i) => (
              <div
                key={i}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: 12,
                  padding: '10px 0',
                  borderBottom: i < activity.length - 1 ? '1px solid var(--border)' : 'none',
                }}
              >
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--brand-500)', marginTop: 5, flexShrink: 0 }} />
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)' }}>{item.description || item.action}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>{timeAgo(item.timestamp || item.created_at)}</div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState title="No recent activity" />
        )}
      </div>
    </div>
  );
}
