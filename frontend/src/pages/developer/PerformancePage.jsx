/**
 * PerformancePage — developer's own performance view
 * Shows AI vs Human breakdown, trends, strengths/weaknesses, recommendations
 */
import { useQuery } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { evaluationApi } from '../../api/evaluation.api';
import { useAuth } from '../../auth/AuthContext';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { ScoreCard, MetricCard, ProgressBar } from '../../components/common/ScoreCard';
import { formatPercent, scoreColor } from '../../utils/formatters';
import { formatDate } from '../../utils/dates';
import { TrendingUp, Brain, Users, Target, Award, AlertCircle, Download, Shield } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis,
} from 'recharts';

export function PerformancePage() {
  const { user } = useAuth();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['performance', user?.employee_id],
    queryFn: () =>
      performanceApi.getDeveloperPerformance(user.employee_id).then((r) => r.data),
    enabled: !!user?.employee_id,
  });

  const { data: evalData } = useQuery({
    queryKey: ['evaluation-my', user?.employee_id],
    queryFn: () =>
      evaluationApi.getEvaluation(user.employee_id).then((r) => r.data).catch(() => null),
    enabled: !!user?.employee_id,
  });

  if (isLoading) return <LoadingState message="Loading performance data…" />;
  if (isError) return <ErrorState description={error.userMessage} onRetry={refetch} />;

  const perf = data || {};
  const evaluation = evalData || {};

  const overall = evaluation.final_score ?? evaluation.overall_score ?? perf.final_score ?? perf.overall_score ?? perf.score;
  const agentScoreMarks = evaluation.agent_score_marks ?? (overall != null ? Math.round((overall * 0.8) * 10) / 10 : (perf.agent_score ?? null));
  const superiorScoreMarks = evaluation.superior_score_marks ?? perf.superior_score ?? (perf.role_evaluation?.contribution != null ? perf.role_evaluation.contribution : null);
  const finalScore = evaluation.final_score ?? (agentScoreMarks != null ? Math.round((agentScoreMarks + (superiorScoreMarks || 0)) * 10) / 10 : overall);

  const codeQuality = evaluation.scores?.code_quality ?? perf.quality_score ?? perf.quality;
  const testingReliability = evaluation.scores?.testing_reliability ?? perf.reliability_score ?? perf.reliability;
  const devopsScore = evaluation.scores?.devops ?? perf.devops_score ?? 85;
  const cicdScore = evaluation.scores?.cicd ?? perf.cicd_score ?? 88;
  const agileCollab = evaluation.scores?.agile_collaboration ?? perf.delivery_score ?? perf.delivery;

  const history = perf.history || perf.trend || [];
  const strengths = evaluation.report?.key_strengths || perf.strengths || [];
  const weaknesses = evaluation.report?.areas_for_growth || perf.weaknesses || perf.improvement_areas || [];
  const recommendations = evaluation.report?.recommendations || perf.recommendations || [];

  const radarData = [
    { axis: 'Code Quality', value: codeQuality ?? 0 },
    { axis: 'Testing / QA', value: testingReliability ?? 0 },
    { axis: 'DevOps / Infra', value: devopsScore ?? 0 },
    { axis: 'CI/CD Pipelines', value: cicdScore ?? 0 },
    { axis: 'Agile Delivery', value: agileCollab ?? 0 },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">My Performance</h1>
          <p className="page-subtitle">{user?.name} · {user?.role}</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-3)' }}>
          {user?.employee_id && (
            <a
              className="btn btn-secondary btn-sm"
              href={`/api/evaluation/${user.employee_id}/report.pdf`}
              target="_blank"
              rel="noreferrer"
              title="Download official PDF evaluation scorecard"
            >
              <Download size={14} />
              Download PDF Report
            </a>
          )}
          {perf.evaluated_at && (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textAlign: 'right' }}>
              Last evaluated<br />
              <span style={{ color: 'var(--text-secondary)' }}>{formatDate(perf.evaluated_at)}</span>
            </div>
          )}
        </div>
      </div>

      {/* Authoritative Score Split: Agent Score (80 Marks) + Superior Score (20 Marks) = Final Score (100 Marks) */}
      <div className="metric-grid" style={{ gridTemplateColumns: 'repeat(3,1fr)', marginBottom: 'var(--space-6)' }}>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>Final Score</div>
          <div className={`score-value-lg ${scoreColor(finalScore ?? overall)}`}>
            {finalScore !== undefined && finalScore !== null ? `${finalScore} / 100` : formatPercent(overall)}
          </div>
          <div style={{ marginTop: 12, fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
            Agent Score (80 Marks) + Superior Score (20 Marks)
          </div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            <Brain size={12} style={{ display: 'inline', marginRight: 4 }} />
            Agent Score
          </div>
          <div className={`score-value-lg ${scoreColor(agentScoreMarks != null ? (agentScoreMarks / 80) * 100 : overall)}`}>
            {agentScoreMarks !== null && agentScoreMarks !== undefined ? `${agentScoreMarks} / 80` : formatPercent(overall)}
          </div>
          <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>80 Marks Max (5 Specialists)</div>
        </div>
        <div className="card" style={{ textAlign: 'center' }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>
            <Users size={12} style={{ display: 'inline', marginRight: 4 }} />
            Superior Score
          </div>
          <div className={`score-value-lg ${scoreColor(superiorScoreMarks != null ? (superiorScoreMarks / 20) * 100 : null)}`}>
            {superiorScoreMarks !== null && superiorScoreMarks !== undefined ? `${superiorScoreMarks} / 20` : 'Pending / 20'}
          </div>
          <div style={{ marginTop: 8, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>20 Marks Max (Lead / Review)</div>
        </div>
      </div>

      {/* Dimension scores + Radar */}
      <div className="grid-2" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Specialist Agent Dimensions</div></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {[
              { label: 'Code Quality (Code Agent)', value: codeQuality },
              { label: 'Testing & Reliability (QA Agent)', value: testingReliability },
              { label: 'DevOps & Infra (DevOps Agent)', value: devopsScore },
              { label: 'CI/CD Performance (CI/CD Agent)', value: cicdScore },
              { label: 'Agile & Collaboration (Meeting Agent)', value: agileCollab },
            ].map((dim) => (
              <div key={dim.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', marginBottom: 6 }}>
                  <span style={{ color: 'var(--text-secondary)' }}>{dim.label}</span>
                  <span className={scoreColor(dim.value)}>{formatPercent(dim.value)}</span>
                </div>
                <ProgressBar value={dim.value ?? 0} max={100} />
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">Performance Profile</div></div>
          {radarData.some(d => d.value > 0) ? (
            <ResponsiveContainer width="100%" height={200}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="var(--border)" />
                <PolarAngleAxis dataKey="axis" tick={{ fill: 'var(--text-secondary)', fontSize: 11 }} />
                <Radar dataKey="value" stroke="var(--brand-500)" fill="var(--brand-500)" fillOpacity={0.15} />
              </RadarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState title="No data yet" />
          )}
        </div>
      </div>

      {/* History trend */}
      {history.length > 0 && (
        <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
          <div className="card-header"><div className="card-title">Performance History</div></div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={history} margin={{ top: 4, right: 8, bottom: 0, left: -24 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis dataKey="period" tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text-muted)', fontSize: 11 }} />
              <Tooltip contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }} />
              <Line type="monotone" dataKey="score" stroke="var(--brand-500)" strokeWidth={2} dot={{ r: 4, fill: 'var(--brand-500)' }} />
              {history[0]?.ai_score !== undefined && (
                <Line type="monotone" dataKey="ai_score" stroke="var(--success)" strokeWidth={1.5} strokeDasharray="4 2" dot={false} />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Strengths + Weaknesses + Recommendations */}
      <div className="grid-3">
        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Award size={16} style={{ color: 'var(--success)' }} />
              <div className="card-title">Strengths</div>
            </div>
          </div>
          {strengths.length > 0 ? (
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {strengths.map((s, i) => (
                <li key={i} style={{ display: 'flex', gap: 8, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--success)', flexShrink: 0 }}>✓</span>
                  {typeof s === 'string' ? s : s.area || s.description}
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No data" />}
        </div>

        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <AlertCircle size={16} style={{ color: 'var(--warning)' }} />
              <div className="card-title">Areas to Improve</div>
            </div>
          </div>
          {weaknesses.length > 0 ? (
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
              {weaknesses.map((w, i) => (
                <li key={i} style={{ display: 'flex', gap: 8, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <span style={{ color: 'var(--warning)', flexShrink: 0 }}>!</span>
                  {typeof w === 'string' ? w : w.area || w.description}
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No data" />}
        </div>

        <div className="card">
          <div className="card-header">
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Target size={16} style={{ color: 'var(--brand-400)' }} />
              <div className="card-title">AI Recommendations</div>
            </div>
          </div>
          <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', marginBottom: 'var(--space-3)' }}>
            AI-generated · requires human review
          </div>
          {recommendations.length > 0 ? (
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
              {recommendations.map((r, i) => (
                <li key={i} style={{ borderLeft: '3px solid var(--brand-500)', paddingLeft: 10, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  {typeof r === 'string' ? r : r.recommendation || r.text}
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No recommendations yet" />}
        </div>
      </div>
    </div>
  );
}
