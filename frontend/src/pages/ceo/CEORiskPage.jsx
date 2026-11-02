/**
 * CEO Executive Risk Page
 * Strategic risk oversight across delivery, technical quality, infrastructure, and organizational health
 */
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  ShieldAlert,
  AlertTriangle,
  TrendingDown,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  FolderKanban,
  Server,
  Code2,
} from 'lucide-react';
import { performanceApi } from '../../api/performance.api';
import { projectsApi } from '../../api/projects.api';
import { LoadingState, ErrorState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { RiskBadge, StatusBadge } from '../../components/common/Badges';
import { formatPercent } from '../../utils/formatters';

export function CEORiskPage() {
  const { data: ceoHealth, isLoading, refetch } = useQuery({
    queryKey: ['ceo-risk-data'],
    queryFn: async () => {
      const [dashRes, riskRes] = await Promise.all([
        performanceApi.getCEODashboard().catch(() => ({ data: {} })),
        performanceApi.getCEOCriticalRisks('org-default').catch(() => ({ data: {} })),
      ]);
      return {
        dashboard: dashRes.data || {},
        critical_risks: riskRes.data?.critical_risks || [],
      };
    },
  });

  const risks = ceoHealth?.critical_risks || [];
  const criticalCount = risks.filter((r) => r.risk_level === 'CRITICAL' || r.risk_level === 'HIGH').length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Executive Risk & Strategic Oversight</h1>
          <p className="page-subtitle">Organizational failure radius, engineering vulnerabilities, and mitigation strategies</p>
        </div>
        <button className="btn btn-secondary" onClick={() => refetch()} title="Refresh risk assessment">
          <RefreshCw size={15} />
          Refresh
        </button>
      </div>

      {/* Metrics Row */}
      <div className="metric-grid">
        <MetricCard
          label="Delivery Confidence"
          value={ceoHealth?.dashboard?.delivery_confidence || '78%'}
          icon={CheckCircle2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Elevated Risks"
          value={criticalCount}
          icon={ShieldAlert}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
        <MetricCard
          label="Active Incidents"
          value={ceoHealth?.dashboard?.active_incidents ?? 1}
          icon={AlertTriangle}
          iconBg="rgba(245,158,11,0.1)"
          iconColor="var(--warning)"
        />
        <MetricCard
          label="Organization Risk Index"
          value={<RiskBadge level="MEDIUM" />}
          icon={TrendingDown}
          iconBg="rgba(99,102,241,0.12)"
          iconColor="var(--brand-400)"
        />
      </div>

      {/* AI Executive Recommendations */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(99,102,241,0.08) 0%, rgba(239,68,68,0.04) 100%)',
          borderColor: 'rgba(99,102,241,0.25)',
          padding: 'var(--space-5)',
          marginBottom: 'var(--space-6)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8, color: 'var(--brand-400)', fontWeight: 600 }}>
          <Sparkles size={18} />
          AI Executive Strategic Guidance
        </div>
        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 'var(--space-3)' }}>
          Overall delivery confidence is stable at 78%. The primary bottleneck is concentrated in Sprint 25 review latency and intermittent staging deployment failures. Engineering output remains high quality (91% avg code quality score), but task handoffs between QA and DevOps need prioritization.
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-3)' }}>
          <div className="badge badge-neutral" style={{ fontSize: '0.75rem', padding: '6px 12px' }}>
            Action 1: Expedite PR review backlog in Core Platform
          </div>
          <div className="badge badge-neutral" style={{ fontSize: '0.75rem', padding: '6px 12px' }}>
            Action 2: Standardize staging CI/CD pipeline dependencies
          </div>
        </div>
      </div>

      {/* Risk Table */}
      <div className="card" style={{ padding: 0 }}>
        <div className="card-header" style={{ padding: 'var(--space-4)' }}>
          <div className="card-title">Identified Risk Matrix ({risks.length})</div>
        </div>
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Risk ID & Category</th>
                <th>Description</th>
                <th>Project</th>
                <th>Risk Level</th>
                <th>Potential Impact</th>
                <th>AI Mitigation Plan</th>
              </tr>
            </thead>
            <tbody>
              {risks.map((r, i) => (
                <tr key={r.id || i}>
                  <td>
                    <code style={{ fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {r.id || `RISK-0${i + 1}`}
                    </code>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginTop: 2 }}>
                      {r.category || 'General'}
                    </div>
                  </td>
                  <td style={{ fontWeight: 500, color: 'var(--text-primary)', maxWidth: 260 }}>
                    {r.title || r.description}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    {r.project || 'Organization'}
                  </td>
                  <td>
                    <RiskBadge level={r.risk_level || 'LOW'} />
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', maxWidth: 240 }}>
                    {r.impact || 'Under observation'}
                  </td>
                  <td style={{ fontSize: '0.8125rem', color: 'var(--brand-400)', maxWidth: 260, lineHeight: 1.4 }}>
                    {r.mitigation || 'Reviewing during weekly retro'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
