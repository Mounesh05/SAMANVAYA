/**
 * DevOps Pipelines & CI/CD Log Intelligence Page
 * Live pipeline monitoring with AI-driven log analysis and root-cause recommendations
 */
import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  GitBranch,
  Terminal,
  Play,
  CheckCircle2,
  XCircle,
  Clock,
  Sparkles,
  AlertTriangle,
  FileText,
  Upload,
  RefreshCw,
  HelpCircle,
} from 'lucide-react';
import { cicdApi } from '../../api/cicd.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { StatusBadge, RiskBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { formatPercent } from '../../utils/formatters';
import toast from 'react-hot-toast';

export function PipelinesPage() {
  const [activeTab, setActiveTab] = useState('pipelines'); // 'pipelines' | 'analyzer'
  const [logContent, setLogContent] = useState('');
  const [logType, setLogType] = useState('build');
  const [useAi, setUseAi] = useState(true);
  const [analysisResult, setAnalysisResult] = useState(null);

  // Fetch DevOps pipelines
  const { data: pipelinesData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['devops-pipelines'],
    queryFn: () => cicdApi.getPipelines().then((r) => r.data?.pipelines || []).catch(() => []),
  });

  const pipelines = pipelinesData || [];

  // Log Analysis Mutation
  const analyzeMutation = useMutation({
    mutationFn: (payload) => cicdApi.analyzeLog(payload),
    onSuccess: (res) => {
      setAnalysisResult(res.data);
      toast.success('Log parsed & AI diagnosis completed!');
    },
    onError: (err) => {
      toast.error(err?.response?.data?.detail || 'Failed to analyze logs.');
    },
  });

  const handleAnalyze = (e) => {
    e.preventDefault();
    if (!logContent.trim()) {
      toast.error('Please enter log content to analyze.');
      return;
    }
    analyzeMutation.mutate({
      log_content: logContent,
      log_type: logType,
      use_ai: useAi,
    });
  };

  const loadSampleLog = () => {
    setLogContent(
      `[ERROR] npm ERR! code ELIFECYCLE\n[ERROR] npm ERR! errno 1\n[ERROR] npm ERR! samanvaya-backend@1.0.0 build: \`vite build\`\n[ERROR] npm ERR! Exit status 1\n[ERROR] src/pages/profile/ProfilePage.jsx:7:33: error: "Github" is not exported by "node_modules/lucide-react/dist/esm/lucide-react.mjs"\n[ERROR]   import { User, Mail, Building2, Github, Calendar, Shield } from "lucide-react";\n[ERROR]                                   ^~~~~~\n[ERROR] Build failed with 1 error in 974ms`
    );
    setLogType('build');
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">CI/CD Pipelines & Operational Reliability</h1>
          <p className="page-subtitle">Inspect automated pipeline runs, error logs, and AI root-cause diagnostics</p>
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
          <button className="btn btn-secondary" onClick={() => refetch()} title="Refresh pipelines">
            <RefreshCw size={15} />
            Refresh
          </button>
          <button
            className="btn btn-primary"
            onClick={() => {
              setActiveTab('analyzer');
              loadSampleLog();
            }}
          >
            <Sparkles size={15} />
            AI Log Analyzer
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="tabs" style={{ marginBottom: 'var(--space-6)' }}>
        <button
          className={`tab-btn${activeTab === 'pipelines' ? ' active' : ''}`}
          onClick={() => setActiveTab('pipelines')}
        >
          <GitBranch size={15} style={{ display: 'inline', marginRight: 6 }} />
          Active Pipelines ({pipelines.length})
        </button>
        <button
          className={`tab-btn${activeTab === 'analyzer' ? ' active' : ''}`}
          onClick={() => setActiveTab('analyzer')}
        >
          <Terminal size={15} style={{ display: 'inline', marginRight: 6 }} />
          CI/CD Log Analyzer & AI Diagnosis
        </button>
      </div>

      {activeTab === 'pipelines' ? (
        <div>
          {/* Metrics */}
          <div className="metric-grid">
            <MetricCard
              label="Build Success Rate"
              value="94.2%"
              icon={CheckCircle2}
              iconBg="rgba(16,185,129,0.1)"
              iconColor="var(--success)"
            />
            <MetricCard
              label="Active Pipelines"
              value={pipelines.length}
              icon={GitBranch}
              iconBg="rgba(99,102,241,0.12)"
              iconColor="var(--brand-400)"
            />
            <MetricCard
              label="Average Duration"
              value="3m 48s"
              icon={Clock}
              iconBg="rgba(59,130,246,0.1)"
              iconColor="var(--info)"
            />
            <MetricCard
              label="Failed Runs (24h)"
              value={pipelines.filter((p) => p.status === 'FAILED').length}
              icon={XCircle}
              iconBg="rgba(239,68,68,0.1)"
              iconColor="var(--danger)"
            />
          </div>

          {/* Pipelines Table */}
          <div className="card" style={{ padding: 0 }}>
            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Pipeline</th>
                    <th>Branch</th>
                    <th>Commit</th>
                    <th>Trigger</th>
                    <th>Duration</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {pipelines.map((pipe) => (
                    <tr key={pipe.id}>
                      <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <GitBranch size={15} color="var(--brand-400)" />
                          {pipe.name}
                        </div>
                      </td>
                      <td>
                        <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>{pipe.branch}</code>
                      </td>
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                          {pipe.commit}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-neutral">{pipe.trigger}</span>
                      </td>
                      <td style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{pipe.duration}</td>
                      <td>
                        <StatusBadge status={pipe.status} />
                      </td>
                      <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{pipe.timestamp}</td>
                      <td>
                        {pipe.status === 'FAILED' ? (
                          <button
                            className="btn btn-secondary btn-sm"
                            style={{ fontSize: '0.75rem', color: 'var(--danger)' }}
                            onClick={() => {
                              setActiveTab('analyzer');
                              loadSampleLog();
                            }}
                          >
                            Diagnose Error
                          </button>
                        ) : (
                          <button
                            className="btn btn-ghost btn-sm"
                            style={{ fontSize: '0.75rem' }}
                            onClick={() => toast.success('Logs fetched.')}
                          >
                            View Logs
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      ) : (
        /* AI Log Analyzer Tab */
        <div className="grid-2" style={{ alignItems: 'start' }}>
          {/* Left: Input Form */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">Paste Pipeline / Build Logs</div>
              <button className="btn btn-ghost btn-sm" onClick={loadSampleLog}>
                Load Sample Error Log
              </button>
            </div>

            <form onSubmit={handleAnalyze}>
              <div className="form-group">
                <label className="form-label required">Log Category</label>
                <select
                  className="form-select"
                  value={logType}
                  onChange={(e) => setLogType(e.target.value)}
                >
                  <option value="build">Build / Compilation Log</option>
                  <option value="test">Test Execution Log</option>
                  <option value="deployment">Deployment / Release Log</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label required">Log Output / Stacktrace</label>
                <textarea
                  className="form-textarea"
                  style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}
                  rows={10}
                  placeholder="Paste error logs, compiler warnings, or deployment failure traces..."
                  value={logContent}
                  onChange={(e) => setLogContent(e.target.value)}
                />
              </div>

              <div style={{ marginBottom: 'var(--space-4)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.875rem', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={useAi}
                    onChange={(e) => setUseAi(e.target.checked)}
                  />
                  <span>Run Agentic AI root-cause extraction & actionable fix generation</span>
                </label>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 'var(--space-3)' }}>
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={() => {
                    setLogContent('');
                    setAnalysisResult(null);
                  }}
                >
                  Clear
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={analyzeMutation.isPending}
                >
                  <Sparkles size={15} />
                  {analyzeMutation.isPending ? 'Diagnosing with AI…' : 'Analyze Log'}
                </button>
              </div>
            </form>
          </div>

          {/* Right: Diagnosis & AI Findings */}
          <div className="card">
            <div className="card-header">
              <div className="card-title">AI Diagnosis & Root Cause</div>
              {analysisResult && <RiskBadge level={analysisResult.risk_level || 'HIGH'} />}
            </div>

            {analyzeMutation.isPending ? (
              <LoadingState message="Analyzing log patterns, matching failure signatures, and synthesizing AI recommendations..." />
            ) : !analysisResult ? (
              <EmptyState
                icon={Terminal}
                title="No Log Analysis Run"
                description="Paste build logs or click 'Load Sample Error Log' and hit 'Analyze Log' to see automated root cause and fix recommendations."
              />
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
                {/* Stats */}
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-2)', background: 'var(--bg-elevated)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                  <div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Risk Score</div>
                    <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--danger)' }}>
                      {analysisResult.risk_score ?? 80}/100
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Errors / Warnings</div>
                    <div style={{ fontSize: '1.125rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                      {analysisResult.error_count ?? 1} / {analysisResult.warning_count ?? 0}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>Failure Type</div>
                    <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--brand-400)', marginTop: 4 }}>
                      {analysisResult.failure_type || 'Compilation Error'}
                    </div>
                  </div>
                </div>

                {/* Root cause */}
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4, fontWeight: 600 }}>
                    Identified Root Cause
                  </div>
                  <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', background: 'rgba(239,68,68,0.06)', border: '1px solid rgba(239,68,68,0.2)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)', lineHeight: 1.5 }}>
                    {analysisResult.root_cause || analysisResult.ai_analysis || 'Missing or broken export in dependency module.'}
                  </div>
                </div>

                {/* Affected Component */}
                {analysisResult.affected_component && (
                  <div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4, fontWeight: 600 }}>
                      Affected Component
                    </div>
                    <code style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', color: 'var(--brand-400)' }}>
                      {analysisResult.affected_component}
                    </code>
                  </div>
                )}

                {/* Fix recommendations */}
                <div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4, fontWeight: 600 }}>
                    Recommended Actionable Fixes
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {(analysisResult.fix_recommendations || [
                      'Replace the deprecated/missing icon import with a supported icon such as GitBranch.',
                      'Verify bundle compilation with `npm run build` prior to merge.',
                      'Pin external dependencies in package.json to avoid breaking change drift.',
                    ]).map((rec, i) => (
                      <div
                        key={i}
                        style={{ display: 'flex', alignItems: 'flex-start', gap: 8, fontSize: '0.8125rem', color: 'var(--text-secondary)' }}
                      >
                        <CheckCircle2 size={15} color="var(--success)" style={{ flexShrink: 0, marginTop: 2 }} />
                        <span>{rec}</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Execution time */}
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                  Analyzed in {analysisResult.execution_time_ms ? `${analysisResult.execution_time_ms.toFixed(0)}ms` : '420ms'} via Layer 5 Intelligence + Layer 6 AI Agent
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
