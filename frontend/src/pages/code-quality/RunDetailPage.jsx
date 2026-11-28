import React, { useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { codeQualityApi } from '../../api/codeQuality.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { RiskBadge } from '../../components/common/RiskBadge';
import { Select } from '../../components/common/Select';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ArrowLeft } from 'lucide-react';
import { getGradeColor } from '../../utils/formatters';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';
import { fileScopeLabel, qualityStatus } from './qualityStatus';
import { DiscoveredFunctions } from './DiscoveredFunctions';
import { AIInterpretation, ReportStatusNotice, ScoreExplanation, dependencyAuditLabel } from './AIInterpretation';

// CQ-02: why a before/after quality change is not shown.
const WITHHELD_REASONS = {
  score_unavailable: 'one revision has no measured score',
  partial_evidence: 'evidence is partial on at least one revision',
  policy_changed: 'quality policy differs between revisions',
  tools_differ: 'different analysis tools ran on each revision',
  dimensions_differ: 'different quality dimensions were measured',
};

const PAGE_SIZE = 25;
const ACTIVE = ['pending', 'running', 'analyzing'];
const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'findings', label: 'Findings' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'evidence', label: 'Evidence' },
];
const SEVERITY_COLOR = { critical: 'var(--danger)', high: '#f97316', medium: 'var(--warning)' };

// CQ-03: findings matched across the PR's base and head revisions. Identity
// ignores line numbers and follows renamed files.
function FindingList({ title, items }) {
  if (!items?.length) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => (
          <li key={item.fingerprint}>
            <strong>{item.severity}</strong> · {item.rule_id} ({item.source_tool}) ·{' '}
            <code style={{ overflowWrap: 'anywhere' }}>{item.file_path}{item.line_number ? `:${item.line_number}` : ''}</code> — {item.message}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function FindingChanges({ changes }) {
  if (changes.status !== 'available') {
    return (
      <Card title="Findings since base" style={{ marginBottom: 24 }}>
        <p>Not compared: evidence is partial on at least one revision, so findings could look new or resolved only because they were not measured.</p>
      </Card>
    );
  }
  const { counts } = changes;
  return (
    <Card title="Findings since base" style={{ marginBottom: 24 }}>
      <p>
        <strong>{counts.new}</strong> new · <strong>{counts.existing}</strong> still present ·{' '}
        <strong>{counts.resolved}</strong> resolved
      </p>
      <FindingList title="New in this PR" items={changes.new} />
      <FindingList title="Resolved by this PR" items={changes.resolved} />
      {changes.truncated && <p>Only the first 100 of each are listed.</p>}
    </Card>
  );
}

function Severity({ value }) {
  return (
    <span style={{ fontWeight: 600, fontSize: '0.75rem', textTransform: 'capitalize',
      color: SEVERITY_COLOR[value] || 'var(--success)' }}>{value}</span>
  );
}

function Location({ finding }) {
  const line = finding.line_number || finding.line;
  return (
    <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem', overflowWrap: 'anywhere' }}>
      <span>{finding.file_path || finding.file}</span>{line && <span style={{ color: 'var(--text-muted)' }}>:L{line}</span>}
    </span>
  );
}

const FINDING_COLUMNS = [
  { key: 'severity', header: 'Severity', render: (f) => <Severity value={f.severity} /> },
  { key: 'file', header: 'Location', render: (f) => <Location finding={f} /> },
  { key: 'rule', header: 'Rule', render: (f) => <span style={{ fontSize: '0.8125rem' }}>{f.rule_id}{f.source_tool && <small style={{ color: 'var(--text-muted)' }}> ({f.source_tool})</small>}</span> },
  { key: 'description', header: 'Finding', render: (f) => <>{f.message || f.description}{f.scope === 'project_context' && <small> (project context)</small>}{f.comparison_status && <small> · {f.comparison_status}</small>}</> },
  // The analyzer's own fix, when it provides one. AI advice is shown separately and never presented as a fix.
  { key: 'fix', header: 'Analyzer fix', render: (f) => <span style={{ fontSize: '0.8125rem' }}>{f.suggested_fix || f.recommendation || 'None provided'}</span> },
];

/** Accessible tab list: arrow keys move between tabs (WAI-ARIA tabs pattern). */
function Tabs({ active, onChange }) {
  const refs = useRef({});
  const onKeyDown = (event) => {
    const index = TABS.findIndex((tab) => tab.id === active);
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const next = TABS[(index + step + TABS.length) % TABS.length].id;
    onChange(next);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" aria-label="Report sections" onKeyDown={onKeyDown}
      style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap', borderBottom: '1px solid var(--border)', marginBottom: 24 }}>
      {TABS.map((tab) => (
        <button key={tab.id} type="button" role="tab" id={`tab-${tab.id}`} aria-controls={`panel-${tab.id}`}
          aria-selected={active === tab.id} tabIndex={active === tab.id ? 0 : -1}
          ref={(node) => { refs.current[tab.id] = node; }} onClick={() => onChange(tab.id)}
          style={{ padding: '0.5rem 0.9rem', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-primary)',
            fontWeight: active === tab.id ? 600 : 400,
            borderBottom: active === tab.id ? '2px solid var(--primary, currentColor)' : '2px solid transparent' }}>
          {tab.label}
        </button>
      ))}
    </div>
  );
}

function ScoreCards({ run, findingsTotal, qualityRan, findingsError }) {
  const isCompleted = run?.status === 'completed';
  const qualityGrade = isCompleted ? (run?.quality_grade || '—') : '—';
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: '1.25rem', marginBottom: 24 }}>
      <Card padding="md">
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>Quality score</span>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.35rem' }}>
          <span style={{ fontSize: '2.25rem', fontWeight: 600, color: 'var(--text-primary)' }}>
            {run?.quality_score != null ? run.quality_score : '—'}
          </span>
          <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ 100</span>
          <span style={{ fontSize: '1rem', fontWeight: 600, color: getGradeColor(qualityGrade), marginLeft: '0.35rem' }}>
            {isCompleted && run?.quality_grade && `(${qualityGrade})`}
          </span>
        </div>
        {run?.quality_score == null && <p>Quality score unavailable</p>}
        {run?.quality_comparison && <p style={{ margin: 0, color: 'var(--text-muted)', fontSize: '0.8125rem' }}>Head revision</p>}
      </Card>
      <Card padding="md">
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>Risk (separate from quality)</span>
        <div style={{ marginTop: '0.5rem' }}>
          {isCompleted && run?.risk_score != null ? <RiskBadge level={run?.risk_level} score={run?.risk_score} size="md" /> : (
            <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              {ACTIVE.includes(run?.status) ? 'Available after analysis completes' : 'Not measured in this run'}
            </span>
          )}
        </div>
      </Card>
      <Card padding="md">
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>Detected language</span>
        <div style={{ fontSize: '1.25rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.35rem', textTransform: 'capitalize' }}>
          {run?.language && run.language !== 'unknown' ? run.language : 'Undetermined'}
        </div>
      </Card>
      {!run?.quality_comparison && <Card padding="md">
        <span style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-muted)' }}>Total findings</span>
        <div style={{ fontSize: '1.5rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.35rem' }}>
          {findingsError ? 'Retrieval failed' : qualityRan && isCompleted && findingsTotal != null ? `${findingsTotal} recorded findings` : 'Quality checks not established'}
        </div>
      </Card>}
    </div>
  );
}

function RevisionComparison({ run, navigate }) {
  const comparison = run.quality_comparison;
  return (
    <Card title="Revision comparison" style={{ marginBottom: 24 }}>
      {Object.entries(run.child_run_ids || {}).map(([side, id]) => <p key={id}>
        <Button variant="ghost" onClick={() => navigate('/code-quality/runs/' + id)}>{side} {run[side + '_sha']?.slice(0, 12)}</Button>
        {comparison[side + '_score'] ?? 'Not measured'} ({comparison[side + '_status']})
      </p>)}
      <p>Displayed quality and risk scores use the head revision.</p>
      <p>Quality score change: {comparison.delta ?? 'Not comparable'}
        {comparison.delta == null && WITHHELD_REASONS[comparison.delta_withheld_reason]
          ? ` (${WITHHELD_REASONS[comparison.delta_withheld_reason]})` : ''}</p>
      {run.dependency_audit && Object.entries(run.dependency_audit).map(([side, status]) =>
        <p key={side}>Dependency vulnerabilities ({side}): {dependencyAuditLabel(status)}</p>)}
    </Card>
  );
}

function AnalysisScope({ run, discoveryOnly }) {
  return (
    <Card title="Analysis scope" style={{ marginBottom: 24 }}>
      <p>Source scope: {fileScopeLabel(run)}</p>
      {(run?.quality_unavailable_reason || discoveryOnly || run?.error) && <p>
        {run?.quality_unavailable_reason || (discoveryOnly ? 'Static function discovery only. Quality and risk were not measured.' : run?.error)}
      </p>}
      <p>Tools executed: {run?.tools_executed?.join(', ') || 'None recorded'}</p>
      <p>Tools skipped or unavailable: {run?.tools_skipped?.join(', ') || 'None recorded'}</p>
      <p>Test coverage: {run?.testing?.coverage_percentage != null ? `${run.testing.coverage_percentage}%` : 'Not measured'}</p>
      {run?.testing?.coverage_percentage == null && run?.execution_provenance?.method === 'quality-snapshot-v1' &&
        <p>The static worker does not run repository tests. Measuring coverage requires a coverage report for this revision.</p>}
      {run?.tools_skipped?.includes('dependency-advisories-offline') &&
        <p>Dependency vulnerabilities were not checked because the isolated worker cannot reach advisory databases.</p>}
      {run?.is_truncated && <p>Analysis was limited to {run.changed_files?.length ?? 0} of {run.source_selection_count} selected files.</p>}
    </Card>
  );
}

function AIProvenance({ run }) {
  const provenance = run?.ai_provenance;
  if (!run?.ai_required && !run?.ai_analysis) {
    return <Card title="AI interpretation record" style={{ marginBottom: 24 }}>
      <p>{run?.status === 'completed' ? 'Legacy run: no AI interpretation was recorded.' : 'Not recorded yet.'}</p>
    </Card>;
  }
  return (
    <Card title="AI interpretation record" style={{ marginBottom: 24 }}>
      <p>Status: {run.ai_status || 'Not recorded'}{run.ai_attempts ? ` · attempts ${run.ai_attempts}` : ''}</p>
      {provenance?.model && <p>Model: {provenance.model}</p>}
      {provenance?.policy_version && <p>Contract: {provenance.policy_version}</p>}
      {provenance?.latency_ms != null && <p>Latency: {provenance.latency_ms} ms</p>}
      {provenance?.evidence_digest && <p style={{ overflowWrap: 'anywhere' }}>Evidence digest: <code>{provenance.evidence_digest}</code></p>}
      {run.use_ai_requested === false && <p>The request asked for no AI; AI interpretation is required for quality reports, so it ran.</p>}
    </Card>
  );
}

export function RunDetailPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [tab, setTab] = useState('overview');
  const [filters, setFilters] = useState({ severity: '', category: '', file: '', search: '', comparison_status: '' });
  const [page, setPage] = useState(0);

  const { data: run, isLoading: isRunLoading, error: runError } = useQuery({
    queryKey: ['code-quality-run', runId],
    queryFn: () => codeQualityApi.getRun(runId),
    refetchInterval: (query) => ACTIVE.includes(query.state.data?.status) ? 3000 : false,
  });

  const discoveryOnly = run?.analysis_scope === 'purpose_discovery' || run?.analysis_level === 'purpose_discovery';
  const findingsEnabled = Boolean(run) && !run.quality_comparison && !ACTIVE.includes(run.status) && !discoveryOnly;
  const params = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
  const { data: findingsData, isLoading: isFindingsLoading, error: findingsError } = useQuery({
    queryKey: ['code-quality-findings', runId, params, page],
    queryFn: () => codeQualityApi.getRunFindings(runId, { ...params, limit: PAGE_SIZE, skip: page * PAGE_SIZE }),
    enabled: findingsEnabled,
  });
  // Overview: the highest-priority findings (the API orders by severity, path and line).
  const { data: topData, error: topError } = useQuery({
    queryKey: ['code-quality-findings', runId, 'top'],
    queryFn: () => codeQualityApi.getRunFindings(runId, { limit: 5 }),
    enabled: findingsEnabled,
  });

  if (isRunLoading) return <LoadingState message="Loading analysis run details..." />;
  if (runError) return <ErrorState message={runError.message} onRetry={() => window.location.reload()} />;

  const isCompleted = run?.status === 'completed';
  const qualityRan = !discoveryOnly && (['available', 'partial'].includes(run?.quality_analysis_status) || run?.tools_executed?.length > 0);
  const total = findingsData?.total ?? 0;
  const setFilter = (key) => (event) => { setFilters((current) => ({ ...current, [key]: event.target.value })); setPage(0); };
  const emptyMessage = qualityRan
    ? 'No findings recorded by the checks that ran. This is not proof the code is defect-free; see the Evidence tab.'
    : 'Quality checks were not run or their evidence is unavailable. No clean-code conclusion can be made.';

  const header = (
    <>
      <div style={{ marginBottom: '1rem' }}>
        <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/code-quality')}>
          Back to Code Quality
        </Button>
      </div>
      <PageHeader
        title={`Analysis Run: ${run?.run_id}`}
        subtitle={`Repository: ${run?.repository_id} ${run?.pr_number ? `• PR #${run.pr_number}` : ''}`}
        badge={<span style={{ color: isCompleted ? 'var(--success)' : 'var(--warning)', fontWeight: 600 }}>{qualityStatus(run)}</span>}
      />
      <ReportStatusNotice run={run} />
    </>
  );

  if (discoveryOnly) {
    // A discovery-only run is not a quality report: no tabs, scores or AI.
    return (
      <div>
        {header}
        <AnalysisScope run={run} discoveryOnly />
        <DiscoveredFunctions key={runId} runId={runId} pending={ACTIVE.includes(run?.status)} />
      </div>
    );
  }

  return (
    <div>
      {header}
      <p style={{ marginTop: 0 }}>
        Scope: {fileScopeLabel(run)}
        {run?.commit_sha && <> · Revision <code style={{ overflowWrap: 'anywhere' }}>{run.commit_sha}</code></>}
      </p>
      <Tabs active={tab} onChange={setTab} />

      {tab === 'overview' && <div role="tabpanel" id="panel-overview" aria-labelledby="tab-overview">
        <ScoreCards run={run} findingsTotal={findingsData?.total ?? topData?.total} qualityRan={qualityRan} findingsError={findingsError} />
        {run?.quality_comparison && <RevisionComparison run={run} navigate={navigate} />}
        {run?.finding_changes && <FindingChanges changes={run.finding_changes} />}
        {findingsEnabled && <Card title="Highest-priority findings" style={{ marginBottom: 24 }}>
          {topError ? <ErrorState message={topError.message} /> : topData?.findings?.length ? <ol style={{ paddingLeft: '1.25rem', lineHeight: 1.6, marginTop: 0 }}>
            {topData.findings.map((f) => <li key={f.id || `${f.file_path}:${f.line_number}:${f.rule_id}`}>
              <Severity value={f.severity} /> · <Location finding={f} /> · {f.message}
            </li>)}
          </ol> : <p>{emptyMessage}</p>}
          {topData?.total > (topData?.findings?.length || 0) &&
            <Button variant="secondary" size="sm" onClick={() => setTab('findings')}>View all {topData.total} findings</Button>}
        </Card>}
        <AIInterpretation ai={run?.ai_analysis} runId={runId} attempts={run?.ai_attempts} />
        {isCompleted && !run?.ai_analysis && !run?.ai_required && <p>AI interpretation: legacy run, not recorded.</p>}
        {run?.commit_sha && !ACTIVE.includes(run.status) &&
          <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}><Button variant="secondary"
            onClick={() => navigate('/code-quality', {state: {reanalysis: {
              run_id: runId, repository_id: run.repository_id, pr_number: run.pr_number, changed_files: run.changed_files,
              file_scope: run.file_scope, selected_scope: run.selected_scope
            }}})}>Reanalyze revision</Button></PermissionGuard>}
      </div>}

      {tab === 'findings' && <div role="tabpanel" id="panel-findings" aria-labelledby="tab-findings">
        {run?.quality_comparison ? <>
          {run?.finding_changes && <FindingChanges changes={run.finding_changes} />}
          <p>Each revision's complete findings are in its own report: use the base and head links in the Overview tab.</p>
        </> : <Card title="Quality & security findings" subtitle="Ordered by severity, then file and line">
          <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
            <div style={{ width: 170 }}>
              <Select aria-label="Severity" value={filters.severity} onChange={setFilter('severity')} placeholder="All severities"
                options={['critical', 'high', 'medium', 'low', 'info'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} />
            </div>
            <div style={{ width: 170 }}>
              <Select aria-label="Category" value={filters.category} onChange={setFilter('category')} placeholder="All categories"
                options={['security', 'syntax', 'type', 'maintainability', 'architecture'].map((v) => ({ value: v, label: v[0].toUpperCase() + v.slice(1) }))} />
            </div>
            {run?.parent_run_id && <div style={{ width: 170 }}>
              <Select aria-label="Change in this PR" value={filters.comparison_status} onChange={setFilter('comparison_status')} placeholder="All PR changes"
                options={[{ value: 'new', label: 'New' }, { value: 'existing', label: 'Still present' }, { value: 'resolved', label: 'Resolved' }]} />
            </div>}
            <input aria-label="File or folder" placeholder="File or folder" value={filters.file} onChange={setFilter('file')} maxLength={500}
              style={{ minWidth: 160, flex: '1 1 160px', padding: '0.4rem 0.6rem' }} />
            <input aria-label="Search findings" placeholder="Search message or rule" value={filters.search} onChange={setFilter('search')} maxLength={100}
              style={{ minWidth: 160, flex: '1 1 160px', padding: '0.4rem 0.6rem' }} />
          </div>
          {findingsError ? <ErrorState message={findingsError.message} /> : isFindingsLoading
            ? <LoadingState message="Loading findings..." />
            : <Table columns={FINDING_COLUMNS} data={findingsData?.findings || []} emptyMessage={emptyMessage} />}
          {total > 0 && <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
            <span aria-live="polite">Showing {page * PAGE_SIZE + 1}–{Math.min(total, (page + 1) * PAGE_SIZE)} of {total}</span>
            <Button variant="secondary" size="sm" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button>
            <Button variant="secondary" size="sm" disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage(page + 1)}>Next</Button>
          </div>}
        </Card>}
      </div>}

      {tab === 'metrics' && <div role="tabpanel" id="panel-metrics" aria-labelledby="tab-metrics">
        {run?.complexity ? <Card title="Source metrics" style={{ marginBottom: 24 }}>
          <p>Average cyclomatic complexity: {run.complexity.average_complexity ?? 'Not measured'}</p>
          <p>Maximum cyclomatic complexity: {run.complexity.max_complexity ?? 'Not measured'}</p>
          <p>Maintainability index: {run.complexity.maintainability_index ?? 'Not measured'}</p>
          <p>Duplicated lines: {run.duplication?.duplicated_lines_count ?? 'Not measured'}</p>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>Cyclomatic complexity is not algorithmic (Big-O) complexity.</p>
        </Card> : <p>No source metrics were recorded for this run.</p>}
        <p>Test coverage: {run?.testing?.coverage_percentage != null ? `${run.testing.coverage_percentage}%` : 'Not measured'}</p>
        <ScoreExplanation explanation={run?.score_explanation} policyDigest={run?.policy_digest} />
      </div>}

      {tab === 'evidence' && <div role="tabpanel" id="panel-evidence" aria-labelledby="tab-evidence">
        {!run?.quality_comparison && <AnalysisScope run={run} />}
        {run?.quality_comparison && <RevisionComparison run={run} navigate={navigate} />}
        <AIProvenance run={run} />
        {/* Function discovery is separate from the quality report: secondary and collapsed (Phase 1 UI spec). */}
        {!run?.quality_comparison && <details>
          <summary style={{ cursor: 'pointer', fontWeight: 600 }}>Function discovery (not part of the quality score)</summary>
          <DiscoveredFunctions key={runId} runId={runId} pending={ACTIVE.includes(run?.status)} />
        </details>}
      </div>}
    </div>
  );
}
