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
import { ArrowLeft, ShieldCheck, AlertTriangle, FileCode, CheckCircle, Terminal } from 'lucide-react';
import { getGradeColor } from '../../utils/formatters';

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
    refetchInterval: (data) => (data?.state?.data?.status === 'running' || data?.state?.data?.status === 'pending' ? 3000 : false),
  });

  // 2. Fetch Findings
  const { data: findingsData, isLoading: isFindingsLoading } = useQuery({
    queryKey: ['code-quality-findings', runId, { severity: severityFilter, category: categoryFilter }],
    queryFn: () =>
      codeQualityApi.getRunFindings(runId, {
        severity: severityFilter || undefined,
        category: categoryFilter || undefined,
      }),
    enabled: !!runId,
  });

  if (isRunLoading) return <LoadingState message="Loading analysis run details..." />;
  if (runError) return <ErrorState message={runError.message} onRetry={() => window.location.reload()} />;

  const findings = findingsData?.findings || [];
  const qualityGrade = run?.quality_grade || 'A';
  const gradeColor = getGradeColor(qualityGrade);

  const findingColumns = [
    {
      key: 'severity',
      header: 'Severity',
      render: (f) => (
        <span
          style={{
            fontWeight: '700',
            fontSize: '0.75rem',
            color:
              f.severity === 'critical'
                ? 'var(--danger)'
                : f.severity === 'high'
                ? '#f97316'
                : f.severity === 'medium'
                ? 'var(--warning)'
                : 'var(--success)',
            textTransform: 'uppercase',
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
          <span>{f.file}</span>
          {f.line && <span style={{ color: 'var(--text-muted)' }}>:L{f.line}</span>}
        </div>
      ),
    },
    { key: 'description', header: 'Finding Description', render: (f) => f.description },
    {
      key: 'recommendation',
      header: 'Fix Recommendation',
      render: (f) => <span style={{ color: 'var(--cyan)', fontSize: '0.8125rem' }}>{f.recommendation || '—'}</span>,
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
        badge={<RiskBadge level={run?.risk_level || 'LOW'} score={run?.risk_score} size="md" />}
      />

      {/* Overview Score Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Quality Score</span>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.35rem' }}>
            <span style={{ fontSize: '2.25rem', fontWeight: '900', color: gradeColor }}>
              {run?.quality_score !== null ? run.quality_score : '—'}
            </span>
            <span style={{ fontSize: '1rem', color: 'var(--text-muted)' }}>/ 100</span>
            <span style={{ fontSize: '1rem', fontWeight: '700', color: gradeColor, marginLeft: '0.35rem' }}>
              ({qualityGrade})
            </span>
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Risk Assessment</span>
          <div style={{ marginTop: '0.5rem' }}>
            <RiskBadge level={run?.risk_level || 'LOW'} score={run?.risk_score} size="md" />
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Detected Language</span>
          <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--text-primary)', marginTop: '0.35rem', textTransform: 'capitalize' }}>
            {run?.language || 'Multi-language'}
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Total Findings</span>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-primary)', marginTop: '0.35rem' }}>
            {findingsData?.total || 0} issues
          </div>
        </Card>
      </div>

      {/* Findings Table Card */}
      <Card
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

        {isFindingsLoading ? (
          <LoadingState message="Loading findings..." />
        ) : (
          <Table
            columns={findingColumns}
            data={findings}
            emptyMessage="No findings detected. Code passes all quality and security checks!"
          />
        )}
      </Card>
    </div>
  );
}
