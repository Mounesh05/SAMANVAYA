/**
 * Code Quality module — overview, findings, analysis status
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { codeQualityApi } from '../../api/codeQuality.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, RiskBadge } from '../../components/common/Badges';
import { ProgressBar } from '../../components/common/ScoreCard';
import { formatPercent, scoreColor, titleCase } from '../../utils/formatters';
import { formatDate, timeAgo } from '../../utils/dates';
import {
  ShieldCheck, AlertTriangle, Code2, Search, Filter, RefreshCw, Brain,
} from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
} from 'recharts';

const SEVERITY_COLORS = {
  CRITICAL: 'var(--danger)',
  HIGH:     '#f97316',
  MEDIUM:   'var(--warning)',
  LOW:      'var(--success)',
  INFO:     'var(--info)',
};

const TABS = ['Overview', 'Findings', 'History'];

export function CodeQualityPage() {
  const [tab, setTab] = useState('Overview');
  const [severityFilter, setSeverityFilter] = useState('ALL');

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['code-quality'],
    queryFn: () => codeQualityApi.getSummary().then(r => r.data),
  });

  const { data: findingsData } = useQuery({
    queryKey: ['code-quality-findings', severityFilter],
    queryFn: () => codeQualityApi.getFindings(severityFilter !== 'ALL' ? { severity: severityFilter } : {}).then(r => r.data),
    enabled: tab === 'Findings',
  });

  if (isLoading) return <LoadingState message="Loading code quality data…" />;
  if (isError) return <ErrorState description={error?.userMessage} onRetry={refetch} />;

  const summary = data?.summary || data || {};
  const repos = data?.repositories || [];
  const findings = Array.isArray(findingsData) ? findingsData : findingsData?.findings || [];
  const categories = data?.by_category || [];
  const severityDist = data?.by_severity || [];

  const pieData = Object.entries(severityDist).map(([name, value]) => ({ name, value }));
  const pieColors = ['var(--danger)', '#f97316', 'var(--warning)', 'var(--success)', 'var(--info)'];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Code Quality</h1>
          <p className="page-subtitle">
            {summary.overall_score !== undefined
              ? `Overall score: ${formatPercent(summary.overall_score)}`
              : 'Evidence-driven code quality analysis'}
          </p>
        </div>
        <button className="btn btn-secondary btn-sm" onClick={refetch}>
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="tabs">
        {TABS.map(t => (
          <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => setTab(t)}>{t}</button>
        ))}
      </div>

      {/* ── Overview ── */}
      {tab === 'Overview' && (
        <>
          {/* Score cards */}
          <div className="metric-grid" style={{ marginBottom: 'var(--space-6)' }}>
            {[
              { label: 'Overall Score', value: formatPercent(summary.overall_score), icon: ShieldCheck, color: 'var(--brand-400)' },
              { label: 'Security Score', value: formatPercent(summary.security_score), icon: ShieldCheck, color: 'var(--success)' },
              { label: 'Total Findings', value: summary.total_findings ?? '—', icon: AlertTriangle, color: 'var(--warning)' },
              { label: 'Critical Issues', value: summary.critical_count ?? 0, icon: AlertTriangle, color: 'var(--danger)' },
              { label: 'Test Coverage', value: formatPercent(summary.test_coverage), icon: Code2, color: 'var(--info)' },
              { label: 'Repositories', value: repos.length, icon: Code2, color: 'var(--brand-400)' },
            ].map(m => (
              <div key={m.label} className="metric-card">
                <div className="metric-icon" style={{ background: `${m.color}18`, color: m.color }}>
                  <m.icon size={18} />
                </div>
                <div className="metric-label">{m.label}</div>
                <div className="metric-value">{m.value}</div>
              </div>
            ))}
          </div>

          {/* Charts row */}
          <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
            {/* Findings by category */}
            <div className="card">
              <div className="card-header"><div className="card-title">Findings by Category</div></div>
              {categories.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={categories} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" horizontal={false} />
                    <XAxis type="number" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
                    <YAxis dataKey="category" type="category" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} width={110} />
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                    <Bar dataKey="count" fill="var(--brand-500)" radius={[0, 4, 4, 0]} name="Findings" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState title="No category data" description="Run code analysis to see findings" />
              )}
            </div>

            {/* Severity distribution */}
            <div className="card">
              <div className="card-header"><div className="card-title">Severity Distribution</div></div>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie data={pieData} cx="50%" cy="50%" outerRadius={75} dataKey="value" label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} labelLine={false}>
                      {pieData.map((_, i) => (
                        <Cell key={i} fill={pieColors[i % pieColors.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <EmptyState title="No data" />
              )}
            </div>
          </div>

          {/* Repositories */}
          {repos.length > 0 && (
            <div className="card">
              <div className="card-header"><div className="card-title">Repositories</div></div>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Repository</th>
                      <th>Language</th>
                      <th>Quality Score</th>
                      <th>Findings</th>
                      <th>Last Analysis</th>
                    </tr>
                  </thead>
                  <tbody>
                    {repos.map((r, i) => (
                      <tr key={r._id || r.id || i}>
                        <td style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>{r.full_name || r.name}</td>
                        <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{r.language || '—'}</td>
                        <td>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span className={scoreColor(r.quality_score)}>{formatPercent(r.quality_score)}</span>
                            <div style={{ width: 60 }}><ProgressBar value={r.quality_score} /></div>
                          </div>
                        </td>
                        <td>
                          {r.critical_count > 0 && <span className="badge badge-danger" style={{ marginRight: 4 }}>{r.critical_count} crit</span>}
                          {r.total_findings ?? '—'}
                        </td>
                        <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{timeAgo(r.last_analysis_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}

      {/* ── Findings ── */}
      {tab === 'Findings' && (
        <>
          {/* Severity filter */}
          <div className="tabs" style={{ marginBottom: 'var(--space-4)' }}>
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(s => (
              <button key={s} className={`tab-btn${severityFilter === s ? ' active' : ''}`}
                onClick={() => setSeverityFilter(s)}>
                {s}
              </button>
            ))}
          </div>

          {findings.length === 0 ? (
            <EmptyState title="No findings" description={severityFilter !== 'ALL' ? `No ${severityFilter} findings` : 'No findings detected'} />
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {findings.map((f, i) => (
                <div key={f._id || i} className="card" style={{ padding: 'var(--space-4)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                        <span style={{ width: 10, height: 10, borderRadius: '50%', background: SEVERITY_COLORS[f.severity] || 'var(--text-muted)', flexShrink: 0 }} />
                        <span style={{ fontWeight: 600, fontSize: '0.8125rem', color: SEVERITY_COLORS[f.severity] || 'var(--text-primary)' }}>
                          {f.severity}
                        </span>
                        <span className="badge badge-neutral">{f.category || f.type}</span>
                      </div>
                      <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', marginBottom: 4 }}>{f.description || f.message}</div>
                      {f.recommendation && (
                        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', borderLeft: '3px solid var(--brand-500)', paddingLeft: 10, marginTop: 8 }}>
                          <strong>Recommendation:</strong> {f.recommendation}
                        </div>
                      )}
                    </div>
                    <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 16 }}>
                      {f.file_path && (
                        <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginBottom: 2 }}>
                          {f.file_path}{f.line_number ? `:${f.line_number}` : ''}
                        </div>
                      )}
                      {f.tool && <span className="badge badge-neutral">{f.tool}</span>}
                    </div>
                  </div>

                  {/* AI context — clearly labelled */}
                  {f.ai_analysis && (
                    <div style={{ marginTop: 'var(--space-3)', padding: '10px 12px', background: 'rgba(99,102,241,0.06)', border: '1px solid rgba(99,102,241,0.15)', borderRadius: 'var(--radius-md)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontSize: '0.6875rem', color: 'var(--brand-400)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                        <Brain size={12} /> AI Interpretation · requires human review
                      </div>
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{f.ai_analysis}</div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── History ── */}
      {tab === 'History' && (
        <div className="card">
          <div className="card-header"><div className="card-title">Analysis History</div></div>
          <EmptyState title="Analysis runs will appear here" description="Trigger a code quality analysis to see historical runs" />
        </div>
      )}
    </div>
  );
}
