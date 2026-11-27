import React, { useState } from 'react';
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
import { qualityStatus } from './qualityStatus';
import { DiscoveredFunctions } from './DiscoveredFunctions';

// CQ-02: why a before/after quality change is not shown.
const WITHHELD_REASONS = {
  score_unavailable: 'one revision has no measured score',
  partial_evidence: 'evidence is partial on at least one revision',
  policy_changed: 'quality policy differs between revisions',
  tools_differ: 'different analysis tools ran on each revision',
  dimensions_differ: 'different quality dimensions were measured',
};

export function RunDetailPage() {
  const { runId } = useParams();
  const navigate = useNavigate();
  const [severityFilter, setSeverityFilter] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  // 1. Fetch Run details (poll if still running)
  const {
    data: run,
    isLoading: isRunLoading,
    error: runError,
  } = useQuery({
    queryKey: ['code-quality-run', runId],
    queryFn: () => codeQualityApi.getRun(runId),
    refetchInterval: (query) => ['pending', 'running', 'analyzing'].includes(query.state.data?.status) ? 3000 : false,
  });

  // 2. Fetch Findings
  const { data: findingsData, isLoading: isFindingsLoading, error: findingsError } = useQuery({
    queryKey: ['code-quality-findings', runId, { severity: severityFilter, category: categoryFilter }],
    queryFn: () =>
      codeQualityApi.getRunFindings(runId, {
        severity: severityFilter || undefined,
        category: categoryFilter || undefined,
      }),
    enabled: Boolean(run) && !run.quality_comparison && !['pending', 'running', 'analyzing'].includes(run.status) &&
      run.analysis_level !== 'purpose_discovery' && run.analysis_scope !== 'purpose_discovery',
  });

  if (isRunLoading) return <LoadingState message="Loading analysis run details..." />;
  if (runError) return <ErrorState message={runError.message} onRetry={() => window.location.reload()} />;

  const findings = findingsData?.findings || [];
  const isCompleted = run?.status === 'completed';
  const discoveryOnly = run?.analysis_scope === 'purpose_discovery' || run?.analysis_level === 'purpose_discovery';
  const qualityRan = !discoveryOnly && (['available', 'partial'].includes(run?.quality_analysis_status) || run?.tools_executed?.length > 0);
  const qualityGrade = isCompleted ? (run?.quality_grade || '—') : '—';
  const gradeColor = getGradeColor(qualityGrade);
  const completionLabel = qualityStatus(run);

  const findingColumns = [
    {
      key: 'severity',
      header: 'Severity',
      render: (f) => (
        <span
          style={{
            fontWeight: '600',
            fontSize: '0.75rem',
            color:
              f.severity === 'critical'
                ? 'var(--danger)'
                : f.severity === 'high'
                ? '#f97316'
                : f.severity === 'medium'
                ? 'var(--warning)'
                : 'var(--success)',
            textTransform: 'capitalize',
          }}
        >
          {f.severity}
        </span>
      ),
    },
    { key: 'category', header: 'Category', render: (f) => <span style={{ textTransform: 'capitalize' }}>{f.category}</span> },
    {
      key: 'file',
      header: 'Location',
      render: (f) => (
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>
          <span>{f.file_path || f.file}</span>
          {(f.line_number || f.line) && <span style={{ color: 'var(--text-muted)' }}>:L{f.line_number || f.line}</span>}
        </div>
      ),
    },
    { key: 'description', header: 'Finding Description', render: (f) => <>{f.message || f.description}{f.scope === 'project_context' && <small> (project context)</small>}</> },
    {
      key: 'recommendation',
      header: 'Fix Recommendation',
      render: (f) => <span style={{ color: 'var(--cyan)', fontSize: '0.8125rem' }}>{f.suggested_fix || f.recommendation || '—'}</span>,
    },
  ];

  return (
    <div>
      <div style={{ marginBottom: '1rem' }}>
        <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/code-quality')}>
          Back to Code Quality
        </Button>
      </div>

      <PageHeader
        title={`Analysis Run: ${run?.run_id}`}
        subtitle={`Repository: ${run?.repository_id} ${run?.pr_number ? `• PR #${run.pr_number}` : ''}`}
        badge={
          <span style={{ color: isCompleted ? 'var(--success)' : 'var(--warning)', fontWeight: '600' }}>
            {completionLabel}
          </span>
        }
      />

      {!run?.quality_comparison && (discoveryOnly || run?.quality_analysis_status === 'partial' || run?.quality_unavailable_reason || run?.error) && <Card title="Analysis scope" style={{ marginBottom: 24 }}>
        <p>{run?.quality_unavailable_reason || (discoveryOnly ? 'Static function discovery only. Quality and risk were not measured.' : run?.error)}</p>
        <p>Tools executed: {run?.tools_executed?.join(', ') || 'None recorded'}</p>
        <p>Tools skipped or unavailable: {run?.tools_skipped?.join(', ') || 'None recorded'}</p>
        <p>Test coverage: {run?.testing?.coverage_percentage != null ? `${run.testing.coverage_percentage}%` : 'Not measured'}</p>
        {run?.testing?.coverage_percentage == null && run?.execution_provenance?.method === 'quality-snapshot-v1' &&
          <p>The static worker does not run repository tests. Measuring coverage requires a coverage report for this revision.</p>}
        {run?.tools_skipped?.includes('dependency-advisories-offline') &&
          <p>Dependency vulnerabilities were not checked because the isolated worker cannot reach advisory databases.</p>}
      </Card>}

      {run?.quality_comparison && <Card title="Revision comparison">
        {Object.entries(run.child_run_ids).map(([side, id]) => <p key={id}>
          <Button variant="ghost" onClick={() => navigate('/code-quality/runs/' + id)}>{side} {run[side + '_sha']?.slice(0, 12)}</Button>
          {run.quality_comparison[side + '_score'] ?? 'Not measured'} ({run.quality_comparison[side + '_status']})
        </p>)}
        <p>Displayed quality and risk scores use the head revision.</p>
        <p>Quality score change: {run.quality_comparison.delta ?? 'Not comparable'}
          {run.quality_comparison.delta == null && WITHHELD_REASONS[run.quality_comparison.delta_withheld_reason]
            ? ` (${WITHHELD_REASONS[run.quality_comparison.delta_withheld_reason]})` : ''}</p>
      </Card>}
      {run?.commit_sha && <p>Revision <code>{run.commit_sha}</code></p>}
      {run?.commit_sha && !['running', 'pending', 'analyzing'].includes(run.status) &&
        <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}><Button variant="secondary"
          onClick={() => navigate('/code-quality', {state: {reanalysis: {
            run_id: runId, repository_id: run.repository_id, pr_number: run.pr_number, changed_files: run.changed_files
          }}})}>Reanalyze revision</Button></PermissionGuard>}
      {run?.complexity && <Card title="Source metrics">
        <p>Average cyclomatic complexity: {run.complexity.average_complexity ?? 'Not measured'}</p>
        <p>Maximum cyclomatic complexity: {run.complexity.max_complexity ?? 'Not measured'}</p>
        <p>Maintainability index: {run.complexity.maintainability_index ?? 'Not measured'}</p>
        <p>Duplicated lines: {run.duplication?.duplicated_lines_count ?? 'Not measured'}</p>
      </Card>}
      {run?.ai_analysis?.recommendations?.length > 0 && <Card title="AI review suggestions">
        <ul>{run.ai_analysis.recommendations.map((suggestion, index) => <li key={index}>{suggestion}</li>)}</ul>
      </Card>}
      {/* Overview Score Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 220px), 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Quality Score</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.35rem' }}>
            <span style={{ fontSize: '2.25rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              {run?.quality_score != null ? run.quality_score : '—'}
            </span>
            <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ 100</span>
            <span style={{ fontSize: '1rem', fontWeight: '600', color: gradeColor, marginLeft: '0.35rem' }}>
              {isCompleted && run?.quality_grade && `(${qualityGrade})`}
            </span>
          </div>
          {run?.quality_score == null && <p>Quality score unavailable</p>}
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Risk Assessment</span>
          <div style={{ marginTop: '0.5rem' }}>
            {isCompleted && run?.risk_score != null ? (
              <RiskBadge level={run?.risk_level} score={run?.risk_score} size="md" />
            ) : (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                {['pending', 'running', 'analyzing'].includes(run?.status) ? 'Available after analysis completes' : 'Not measured in this run'}
              </span>
            )}
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Detected Language</span>
          <div style={{ fontSize: '1.25rem', fontWeight: '600', color: 'var(--text-primary)', marginTop: '0.35rem', textTransform: 'capitalize' }}>
            {run?.language && run.language !== 'unknown' ? run.language : 'Undetermined'}
          </div>
        </Card>

        {!run?.quality_comparison && <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Total Findings</span>
          <div style={{ fontSize: '1.5rem', fontWeight: '600', color: 'var(--text-primary)', marginTop: '0.35rem' }}>
            {findingsError ? 'Retrieval failed' : qualityRan && isCompleted && findingsData ? `${findingsData.total} recorded findings` : 'Quality checks not established'}
          </div>
        </Card>}
      </div>

      {/* Findings Table Card */}
      {!run?.quality_comparison && <DiscoveredFunctions key={runId} runId={runId} pending={['pending', 'running', 'analyzing'].includes(run?.status)} />}

      {!run?.quality_comparison && <Card
        title="Quality & Security Findings"
        subtitle="Individual line-by-line evidence and fix recommendations"
      >
        {/* Filters */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
          <div style={{ width: '180px' }}>
            <Select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              placeholder="All Severities"
              options={[
                { value: 'critical', label: 'Critical' },
                { value: 'high', label: 'High' },
                { value: 'medium', label: 'Medium' },
                { value: 'low', label: 'Low' },
              ]}
            />
          </div>
          <div style={{ width: '180px' }}>
            <Select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              placeholder="All Categories"
              options={[
                { value: 'security', label: 'Security' },
                { value: 'syntax', label: 'Syntax' },
                { value: 'type', label: 'Type' },
                { value: 'maintainability', label: 'Maintainability' },
              ]}
            />
          </div>
        </div>

        {findingsError ? <ErrorState message={findingsError.message} /> : isFindingsLoading ? (
          <LoadingState message="Loading findings..." />
        ) : (
          <Table
            columns={findingColumns}
            data={findings}
            emptyMessage={qualityRan ? 'No findings recorded by the checks that ran. See tool availability and analysis limitations.' : 'Quality checks were not run or their evidence is unavailable. No clean-code conclusion can be made.'}
          />
        )}
      </Card>}
    </div>
  );
}
