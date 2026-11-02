/**
 * Organization & Team Performance Overview
 * Used by HR, CEO, Lead, and PM roles
 * Implements Multi-Agent Specialist Scoring:
 * - Code Agent: Code Quality
 * - QA Agent: Testing & Reliability
 * - DevOps Agent: Deployment & Infrastructure
 * - CI/CD Agent: CI/CD Performance
 * - Meeting Agent: Agile & Collaboration
 * Aggregated via Performance Aggregator and Report Agent.
 */
import { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  TrendingUp,
  Sparkles,
  Users,
  Award,
  AlertCircle,
  Play,
  Search,
  Filter,
  CheckCircle2,
  RefreshCw,
  Eye,
  Download,
  Shield,
  GitBranch,
  Terminal,
  Activity,
  Calendar,
} from 'lucide-react';
import { evaluationApi } from '../../api/evaluation.api';
import { employeesApi } from '../../api/employees.api';
import { projectsApi } from '../../api/projects.api';
import { useAuth } from '../../auth/AuthContext';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { RoleBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { formatPercent, scoreColor } from '../../utils/formatters';
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts';
import toast from 'react-hot-toast';

export function OrgPerformancePage({
  title = 'Performance Overview',
  subtitle = 'Multi-agent specialist evaluations and engineering intelligence',
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [evalModalOpen, setEvalModalOpen] = useState(false);
  const [selectedEval, setSelectedEval] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');

  // 1. Fetch dynamic employees list from database
  const {
    data: employeesData,
    isLoading: loadingEmployees,
    refetch: refetchEmployees,
  } = useQuery({
    queryKey: ['employees-performance-list'],
    queryFn: () =>
      employeesApi
        .list()
        .then((r) => (Array.isArray(r.data) ? r.data : r.data?.employees || []))
        .catch(() => []),
  });

  // 2. Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () =>
      projectsApi
        .list()
        .then((r) => (Array.isArray(r.data) ? r.data : r.data?.projects || []))
        .catch(() => []),
  });

  // 3. Fetch dynamic multi-agent evaluations from database
  const {
    data: rawEvaluations,
    isLoading: loadingEvaluations,
    refetch: refetchEvaluations,
  } = useQuery({
    queryKey: ['evaluations-list'],
    queryFn: () =>
      evaluationApi
        .listEvaluations()
        .then((r) => (Array.isArray(r.data) ? r.data : []))
        .catch(() => []),
  });

  // 4. Merge employees with their latest specialist evaluation
  const evaluations = useMemo(() => {
    const evals = Array.isArray(rawEvaluations) ? rawEvaluations : [];
    const emps = Array.isArray(employeesData) ? employeesData : [];

    const evalMap = new Map();
    evals.forEach((ev) => {
      if (ev.employee_id) {
        // Keep the latest evaluation if multiple exist
        if (!evalMap.has(ev.employee_id)) {
          evalMap.set(ev.employee_id, ev);
        }
      }
    });

    if (emps.length === 0 && evals.length > 0) {
      return evals.map((ev) => ({
        id: ev.evaluation_id || ev._id,
        employee_id: ev.employee_id,
        name: ev.employee_name || ev.employee_id,
        role: ev.role || 'DEVELOPER',
        department: ev.department || 'Engineering',
        overall_score: ev.overall_score !== null ? Math.round(ev.overall_score * 10) / 10 : null,
        agent_score_marks: ev.agent_score_marks !== undefined ? ev.agent_score_marks : (ev.overall_score !== null ? Math.round((ev.overall_score * 0.8) * 10) / 10 : null),
        superior_score_marks: ev.superior_score_marks !== undefined ? ev.superior_score_marks : null,
        final_score: ev.final_score !== undefined ? ev.final_score : (ev.overall_score !== null ? Math.round(ev.overall_score * 10) / 10 : null),
        grade: ev.grade || 'N/A',
        confidence: ev.confidence ?? 0,
        scores: ev.scores || {},
        agent_scores: ev.agent_scores || {},
        report: ev.report || {},
        strengths: ev.report?.key_strengths || ev.strengths || [],
        weaknesses: ev.report?.areas_for_growth || ev.weaknesses || [],
        status:
          ev.overall_score === null
            ? 'INSUFFICIENT_EVIDENCE'
            : ev.overall_score >= 90
            ? 'TOP_PERFORMER'
            : ev.overall_score >= 75
            ? 'ON_TRACK'
            : 'NEEDS_ATTENTION',
      }));
    }

    return emps.map((emp) => {
      const eid = emp.id || emp.employee_id;
      const ev = evalMap.get(eid);
      if (ev) {
        return {
          id: ev.evaluation_id || ev._id,
          employee_id: eid,
          name: emp.name || ev.employee_name,
          role: emp.role || 'DEVELOPER',
          department: emp.department || 'Engineering',
          overall_score: ev.overall_score !== null ? Math.round(ev.overall_score * 10) / 10 : null,
          agent_score_marks: ev.agent_score_marks !== undefined ? ev.agent_score_marks : (ev.overall_score !== null ? Math.round((ev.overall_score * 0.8) * 10) / 10 : null),
          superior_score_marks: ev.superior_score_marks !== undefined ? ev.superior_score_marks : null,
          final_score: ev.final_score !== undefined ? ev.final_score : (ev.overall_score !== null ? Math.round(ev.overall_score * 10) / 10 : null),
          grade: ev.grade || 'N/A',
          confidence: ev.confidence ?? 0,
          scores: ev.scores || {},
          agent_scores: ev.agent_scores || {},
          report: ev.report || {},
          strengths: ev.report?.key_strengths || ev.strengths || [],
          weaknesses: ev.report?.areas_for_growth || ev.weaknesses || [],
          status:
            ev.overall_score === null
              ? 'INSUFFICIENT_EVIDENCE'
              : ev.overall_score >= 90
              ? 'TOP_PERFORMER'
              : ev.overall_score >= 75
              ? 'ON_TRACK'
              : 'NEEDS_ATTENTION',
        };
      }
      return {
        id: `pending-${eid}`,
        employee_id: eid,
        name: emp.name,
        role: emp.role || 'DEVELOPER',
        department: emp.department || 'Engineering',
        overall_score: null,
        agent_score_marks: null,
        superior_score_marks: null,
        final_score: null,
        grade: 'Pending',
        confidence: 0,
        scores: {},
        agent_scores: {},
        report: {},
        strengths: [],
        weaknesses: [],
        status: 'PENDING_EVALUATION',
      };
    });
  }, [rawEvaluations, employeesData]);

  // 5. Trigger evaluation mutation
  const evalMutation = useMutation({
    mutationFn: async (payload) => {
      if (payload.is_bulk) {
        // Trigger multi-agent evaluations for all employees
        const targets = evaluations.filter((e) => e.employee_id);
        const results = [];
        for (const t of targets) {
          try {
            const res = await evaluationApi.triggerEvaluation({
              employee_id: t.employee_id,
              start_date: payload.start_date || '2026-09-01',
              end_date: payload.end_date || '2026-09-30',
              period_label: payload.period_label || '2026-09',
            });
            results.push(res);
          } catch (err) {
            console.error(`Evaluation failed for ${t.employee_id}:`, err);
          }
        }
        return results;
      } else {
        return evaluationApi.triggerEvaluation({
          employee_id: payload.employee_id,
          start_date: payload.start_date || '2026-09-01',
          end_date: payload.end_date || '2026-09-30',
          period_label: payload.period_label || '2026-09',
        });
      }
    },
    onSuccess: () => {
      toast.success('Multi-Agent Specialist Evaluation completed successfully.');
      qc.invalidateQueries({ queryKey: ['evaluations-list'] });
      setEvalModalOpen(false);
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to trigger evaluation.');
    },
  });

  const projects = projectsData || [];

  const filteredEvals = evaluations.filter((e) => {
    if (roleFilter !== 'ALL' && e.role !== roleFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        e.name.toLowerCase().includes(q) ||
        e.employee_id.toLowerCase().includes(q) ||
        e.department.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const evaluatedList = evaluations.filter((e) => e.overall_score !== null);
  const avgScore = evaluatedList.length
    ? Math.round(evaluatedList.reduce((acc, curr) => acc + (curr.overall_score || 0), 0) / evaluatedList.length)
    : 85;

  const topPerformers = evaluations.filter((e) => (e.overall_score ?? 0) >= 90).length;
  const needsAttention = evaluations.filter((e) => e.overall_score !== null && e.overall_score < 75).length;

  const distributionData = [
    { range: '90-100% (High)', count: evaluations.filter((e) => (e.overall_score ?? 0) >= 90).length },
    { range: '80-89% (Good)', count: evaluations.filter((e) => (e.overall_score ?? 0) >= 80 && (e.overall_score ?? 0) < 90).length },
    { range: '70-79% (Average)', count: evaluations.filter((e) => (e.overall_score ?? 0) >= 70 && (e.overall_score ?? 0) < 80).length },
    { range: '<70% (Attention)', count: evaluations.filter((e) => e.overall_score !== null && (e.overall_score ?? 0) < 70).length },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">{title}</h1>
          <p className="page-subtitle">{subtitle}</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button
            className="btn btn-secondary"
            onClick={() => {
              refetchEmployees();
              refetchEvaluations();
            }}
            title="Refresh dynamic data"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
          {(user?.role === 'CEO' || user?.role === 'HR' || user?.role === 'LEAD' || user?.is_admin) && (
            <button className="btn btn-primary" onClick={() => setEvalModalOpen(true)}>
              <Sparkles size={15} />
              Run Specialist Evaluation
            </button>
          )}
        </div>
      </div>

      {/* Metrics Row */}
      <div className="metric-grid">
        <MetricCard
          label="Organization Average"
          value={formatPercent(avgScore)}
          icon={TrendingUp}
          iconBg="rgba(99,102,241,0.12)"
          iconColor="var(--brand-400)"
        />
        <MetricCard
          label="Top Performers (≥90%)"
          value={topPerformers}
          icon={Award}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
        <MetricCard
          label="Needs Attention (<75%)"
          value={needsAttention}
          icon={AlertCircle}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
        <MetricCard
          label="Active Specialists"
          value="5 Agents"
          icon={Shield}
          iconBg="rgba(139,92,246,0.1)"
          iconColor="var(--brand-300)"
        />
      </div>

      {/* Architecture Explanatory Banner */}
      <div
        className="card"
        style={{
          background: 'linear-gradient(135deg, rgba(99,102,241,0.06), rgba(168,85,247,0.04))',
          borderColor: 'rgba(99,102,241,0.2)',
          marginBottom: 'var(--space-6)',
          padding: 'var(--space-4)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
          <Sparkles size={16} color="var(--brand-400)" />
          <span style={{ fontWeight: 600, fontSize: '0.875rem', color: 'var(--text-primary)' }}>
            Deterministic Specialist Agent Architecture
          </span>
        </div>
        <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Engineering Performance Evaluation Architecture:
          <strong> Agent Score = 80 Marks</strong> across 5 dedicated specialist agents (Code Quality 25%, QA 20%, DevOps 15%, CI/CD 15%, Agile & Collaboration 25%) + 
          <strong> Superior Score = 20 Marks</strong> from human lead/manager review = 
          <strong> Final Score = 100 Marks</strong>. Specialist agent weights are normalized dynamically if evidence is missing.
        </div>
      </div>

      {/* Distribution Chart */}
      <div className="card" style={{ marginBottom: 'var(--space-6)' }}>
        <div className="card-header">
          <div className="card-title">Performance Distribution Curve</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Organization score brackets</span>
        </div>
        <div style={{ height: 200, width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={distributionData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="range" stroke="var(--text-muted)" fontSize={12} tickLine={false} />
              <YAxis stroke="var(--text-muted)" fontSize={12} tickLine={false} allowDecimals={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: 'var(--bg-elevated)',
                  border: '1px solid var(--border)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: '0.8125rem',
                }}
              />
              <Bar dataKey="count" name="Employees" fill="var(--brand-500)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Specialist Scores Table & Filters */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Employee Specialist Scorecards ({filteredEvals.length})</div>
          <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
            <div className="search-bar" style={{ maxWidth: 280 }}>
              <Search size={14} color="var(--text-muted)" />
              <input
                type="text"
                placeholder="Search employee..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
            </div>
            <select
              className="form-select"
              style={{ width: 'auto', padding: '6px 12px' }}
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
            >
              <option value="ALL">All Roles</option>
              <option value="DEVELOPER">Developer</option>
              <option value="QA">QA</option>
              <option value="DEVOPS">DevOps</option>
              <option value="LEAD">Lead</option>
            </select>
          </div>
        </div>

        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th>Final Score (100)</th>
                <th>Agent (80)</th>
                <th>Superior (20)</th>
                <th>Code Quality</th>
                <th>QA & Testing</th>
                <th>DevOps</th>
                <th>CI/CD</th>
                <th>Agile & Sprint</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredEvals.map((item) => {
                const s = item.scores || {};
                return (
                  <tr key={item.id}>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{item.name}</div>
                      <code style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {item.employee_id}
                      </code>
                    </td>
                    <td>
                      <RoleBadge role={item.role} />
                    </td>
                    <td>
                      {item.final_score !== null && item.final_score !== undefined ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontWeight: 700, fontSize: '0.9375rem', color: scoreColor(item.final_score) }}>
                            {item.final_score} / 100
                          </span>
                          <span
                            className="badge"
                            style={{
                              fontSize: '0.6875rem',
                              padding: '2px 5px',
                              background: 'var(--bg-elevated)',
                              border: '1px solid var(--border)',
                            }}
                          >
                            {item.grade}
                          </span>
                        </div>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>Pending</span>
                      )}
                    </td>
                    <td>
                      {item.agent_score_marks !== null && item.agent_score_marks !== undefined ? (
                        <span style={{ fontWeight: 600, color: 'var(--brand-400)' }}>
                          {item.agent_score_marks} / 80
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Pending</span>
                      )}
                    </td>
                    <td>
                      {item.superior_score_marks !== null && item.superior_score_marks !== undefined ? (
                        <span style={{ fontWeight: 600, color: 'var(--success)' }}>
                          {item.superior_score_marks} / 20
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Pending</span>
                      )}
                    </td>
                    {/* Code Quality Agent Score */}
                    <td>
                      {s.code_quality !== undefined && s.code_quality !== null ? (
                        <span style={{ fontWeight: 600, color: scoreColor(s.code_quality) }}>
                          {formatPercent(s.code_quality)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>N/A</span>
                      )}
                    </td>
                    {/* QA Agent Score */}
                    <td>
                      {s.testing_reliability !== undefined && s.testing_reliability !== null ? (
                        <span style={{ fontWeight: 600, color: scoreColor(s.testing_reliability) }}>
                          {formatPercent(s.testing_reliability)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>N/A</span>
                      )}
                    </td>
                    {/* DevOps Agent Score */}
                    <td>
                      {s.devops !== undefined && s.devops !== null ? (
                        <span style={{ fontWeight: 600, color: scoreColor(s.devops) }}>
                          {formatPercent(s.devops)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>N/A</span>
                      )}
                    </td>
                    {/* CI/CD Agent Score */}
                    <td>
                      {s.cicd !== undefined && s.cicd !== null ? (
                        <span style={{ fontWeight: 600, color: scoreColor(s.cicd) }}>
                          {formatPercent(s.cicd)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>N/A</span>
                      )}
                    </td>
                    {/* Meeting Agent Score */}
                    <td>
                      {s.agile_collaboration !== undefined && s.agile_collaboration !== null ? (
                        <span style={{ fontWeight: 600, color: scoreColor(s.agile_collaboration) }}>
                          {formatPercent(s.agile_collaboration)}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>N/A</span>
                      )}
                    </td>
                    <td>
                      <span
                        className="badge"
                        style={{
                          background:
                            item.status === 'TOP_PERFORMER'
                              ? 'rgba(16,185,129,0.1)'
                              : item.status === 'NEEDS_ATTENTION'
                              ? 'rgba(239,68,68,0.1)'
                              : 'rgba(59,130,246,0.1)',
                          color:
                            item.status === 'TOP_PERFORMER'
                              ? 'var(--success)'
                              : item.status === 'NEEDS_ATTENTION'
                              ? 'var(--danger)'
                              : 'var(--info)',
                        }}
                      >
                        {item.status?.replace('_', ' ')}
                      </span>
                    </td>
                    <td>
                      <button
                        className="btn btn-ghost btn-sm"
                        onClick={() => setSelectedEval(item)}
                        title="View comprehensive specialist scorecard"
                      >
                        <Eye size={14} />
                        View
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Trigger Specialist Evaluation Modal */}
      {evalModalOpen && (
        <Modal title="Run Specialist AI Performance Evaluation" onClose={() => setEvalModalOpen(false)}>
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const fd = new FormData(e.target);
              evalMutation.mutate({
                is_bulk: fd.get('target') === 'bulk',
                employee_id: fd.get('employee_id'),
                start_date: fd.get('start_date') || '2026-09-01',
                end_date: fd.get('end_date') || '2026-09-30',
                period_label: fd.get('period_label') || '2026-09',
              });
            }}
          >
            <div className="form-group">
              <label className="form-label required">Evaluation Scope</label>
              <select name="target" className="form-select" defaultValue="bulk">
                <option value="bulk">Bulk Evaluate All Team Members</option>
                <option value="individual">Single Employee</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Employee Target (if Single Employee)</label>
              <select name="employee_id" className="form-select">
                {evaluations.map((e) => (
                  <option key={e.employee_id} value={e.employee_id}>
                    {e.name} ({e.employee_id}) — {e.role}
                  </option>
                ))}
              </select>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              <div className="form-group">
                <label className="form-label required">Start Date</label>
                <input
                  type="date"
                  name="start_date"
                  className="form-input"
                  defaultValue="2026-09-01"
                  required
                />
              </div>
              <div className="form-group">
                <label className="form-label required">End Date</label>
                <input
                  type="date"
                  name="end_date"
                  className="form-input"
                  defaultValue="2026-09-30"
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Period Label</label>
              <input
                type="text"
                name="period_label"
                className="form-input"
                defaultValue="2026-09"
                placeholder="e.g. 2026-09 or 2026-Q3"
              />
            </div>

            <div
              style={{
                background: 'var(--bg-elevated)',
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.8125rem',
                color: 'var(--text-secondary)',
                marginBottom: 'var(--space-4)',
              }}
            >
              The 5 specialist agents will run concurrently via LangGraph supervisor, scoring strictly by deterministic formulas from collected GitHub commits, PR reviews, CI/CD telemetry, and Jira tasks.
            </div>

            <div className="modal-actions">
              <button type="button" className="btn btn-ghost" onClick={() => setEvalModalOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={evalMutation.isPending}>
                <Sparkles size={15} />
                {evalMutation.isPending ? 'Executing Evaluation…' : 'Run Evaluation'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Specialist Performance Scorecard Modal */}
      {selectedEval && (
        <Modal
          title={`Engineering Intelligence Scorecard — ${selectedEval.name} (${selectedEval.employee_id})`}
          onClose={() => setSelectedEval(null)}
          size="lg"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {/* Header score card with Authoritative 80/20 Marks split */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(5, 1fr)',
                gap: 'var(--space-3)',
                background: 'var(--bg-elevated)',
                padding: 'var(--space-4)',
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--border)',
              }}
            >
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Final Score (100)
                </div>
                <div style={{ fontSize: '1.5rem', fontWeight: 800, color: scoreColor(selectedEval.final_score ?? selectedEval.overall_score) }}>
                  {selectedEval.final_score !== null && selectedEval.final_score !== undefined ? `${selectedEval.final_score} / 100` : formatPercent(selectedEval.overall_score)}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Agent Score (80)
                </div>
                <div style={{ fontSize: '1.375rem', fontWeight: 700, color: 'var(--brand-400)', marginTop: 2 }}>
                  {selectedEval.agent_score_marks !== null && selectedEval.agent_score_marks !== undefined ? `${selectedEval.agent_score_marks} / 80` : (selectedEval.overall_score !== null ? `${Math.round(selectedEval.overall_score * 0.8 * 10) / 10} / 80` : 'Pending')}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Superior Score (20)
                </div>
                <div style={{ fontSize: '1.375rem', fontWeight: 700, color: 'var(--success)', marginTop: 2 }}>
                  {selectedEval.superior_score_marks !== null && selectedEval.superior_score_marks !== undefined ? `${selectedEval.superior_score_marks} / 20` : 'Pending / 20'}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Grade
                </div>
                <div style={{ fontSize: '1.375rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: 2 }}>
                  {selectedEval.grade}
                </div>
              </div>
              <div>
                <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Confidence
                </div>
                <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--brand-400)', marginTop: 2 }}>
                  {Math.round((selectedEval.confidence || 0) * 100)}%
                </div>
              </div>
            </div>

            {/* Executive Summary */}
            {selectedEval.report?.executive_summary && (
              <div
                style={{
                  background: 'rgba(99,102,241,0.05)',
                  padding: 'var(--space-3)',
                  borderRadius: 'var(--radius-md)',
                  borderLeft: '3px solid var(--brand-500)',
                  fontSize: '0.875rem',
                  lineHeight: 1.5,
                  color: 'var(--text-primary)',
                }}
              >
                <strong>Executive Summary: </strong>
                {selectedEval.report.executive_summary}
              </div>
            )}

            {/* Specialist Dimensions Breakdown */}
            <div>
              <div style={{ fontSize: '0.875rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
                Specialist Agent Dimension Breakdown
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 'var(--space-3)' }}>
                {/* 1. Code Quality Agent */}
                <div className="card" style={{ margin: 0, padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge badge-primary">Code Agent</span>
                      <span style={{ fontWeight: 600 }}>Code Quality</span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1.125rem', color: scoreColor(selectedEval.scores?.code_quality) }}>
                      {formatPercent(selectedEval.scores?.code_quality)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Correctness (0-20), Maintainability (0-20), Security (0-20), Testing in code (0-15), Performance (0-10), Architecture (0-10), Readability (0-5).
                  </div>
                  {selectedEval.agent_scores?.code_quality?.explanation && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      "{selectedEval.agent_scores.code_quality.explanation}"
                    </div>
                  )}
                </div>

                {/* 2. QA Agent */}
                <div className="card" style={{ margin: 0, padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge badge-success">QA Agent</span>
                      <span style={{ fontWeight: 600 }}>Testing & Reliability</span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1.125rem', color: scoreColor(selectedEval.scores?.testing_reliability) }}>
                      {formatPercent(selectedEval.scores?.testing_reliability)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Coverage (0-25), Completeness (0-20), Regression Prevention (0-20), Reliability (0-15), Defect Prevention (0-10).
                  </div>
                  {selectedEval.agent_scores?.testing_reliability?.explanation && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      "{selectedEval.agent_scores.testing_reliability.explanation}"
                    </div>
                  )}
                </div>

                {/* 3. DevOps Agent */}
                <div className="card" style={{ margin: 0, padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge badge-warning">DevOps Agent</span>
                      <span style={{ fontWeight: 600 }}>Deployment & Infrastructure</span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1.125rem', color: scoreColor(selectedEval.scores?.devops) }}>
                      {formatPercent(selectedEval.scores?.devops)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Deployment Reliability (0-25), Infra Safety (0-20), Change Risk (0-20), Rollback Recovery (0-15), Observability (0-10).
                  </div>
                  {selectedEval.agent_scores?.devops?.explanation && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      "{selectedEval.agent_scores.devops.explanation}"
                    </div>
                  )}
                </div>

                {/* 4. CI/CD Agent */}
                <div className="card" style={{ margin: 0, padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge badge-info">CI/CD Agent</span>
                      <span style={{ fontWeight: 600 }}>Pipeline Engineering</span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1.125rem', color: scoreColor(selectedEval.scores?.cicd) }}>
                      {formatPercent(selectedEval.scores?.cicd)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Pipeline Reliability (0-30), Failure Resolution (0-20), Build/Test Stability (0-20), Prevention (0-15).
                  </div>
                  {selectedEval.agent_scores?.cicd?.explanation && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      "{selectedEval.agent_scores.cicd.explanation}"
                    </div>
                  )}
                </div>

                {/* 5. Meeting Agent */}
                <div className="card" style={{ margin: 0, padding: 'var(--space-3)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span className="badge" style={{ background: 'rgba(168,85,247,0.1)', color: 'var(--brand-300)' }}>
                        Meeting Agent
                      </span>
                      <span style={{ fontWeight: 600 }}>Agile & Collaboration (Objective Delivery)</span>
                    </div>
                    <span style={{ fontWeight: 700, fontSize: '1.125rem', color: scoreColor(selectedEval.scores?.agile_collaboration) }}>
                      {formatPercent(selectedEval.scores?.agile_collaboration)}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                    Delivery Reliability (0-25), Sprint Commitment (0-20), Blocker Resolution (0-20), Action Items (0-15). Strictly no personality inferences.
                  </div>
                  {selectedEval.agent_scores?.agile_collaboration?.explanation && (
                    <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      "{selectedEval.agent_scores.agile_collaboration.explanation}"
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Strengths & Weaknesses */}
            {selectedEval.strengths?.length > 0 && (
              <div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                  Identified Strengths
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {selectedEval.strengths.map((str, i) => (
                    <span key={i} className="badge badge-success" style={{ fontSize: '0.75rem' }}>
                      <CheckCircle2 size={12} style={{ marginRight: 4 }} />
                      {str}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {selectedEval.weaknesses?.length > 0 && (
              <div>
                <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
                  Areas for Development
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {selectedEval.weaknesses.map((w, i) => (
                    <span key={i} className="badge badge-warning" style={{ fontSize: '0.75rem' }}>
                      <AlertCircle size={12} style={{ marginRight: 4 }} />
                      {w}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Modal Actions */}
            <div className="modal-actions" style={{ justifyContent: 'space-between' }}>
              <a
                className="btn btn-secondary"
                href={`/api/evaluation/${selectedEval.employee_id}/report.pdf`}
                target="_blank"
                rel="noreferrer"
              >
                <Download size={14} />
                Download PDF Scorecard
              </a>

              <button className="btn btn-primary" onClick={() => setSelectedEval(null)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
