import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useLocation } from 'react-router-dom';
import { codeQualityApi } from '../../api/codeQuality.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Play, ArrowRight, Code2 } from 'lucide-react';
import { formatDate } from '../../utils/dates';
import { getGradeColor } from '../../utils/formatters';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';
import { AlgorithmComparisonPanel } from './AlgorithmComparisonPanel';
import { BehavioralCompatibilityPanel } from './BehavioralCompatibilityPanel';
import { RequirementsPanel } from './RequirementsPanel';
import { PRAlgorithmIntelligencePanel } from './PRAlgorithmIntelligencePanel';
import { qualityStatus } from './qualityStatus';
import './CodeQuality.css';

const LANGUAGES = ['Python', 'JavaScript', 'TypeScript'];

// CQ-01: with a PR number the server resolves the PR's changed files itself.
const canSubmit = (data) => Boolean(
  data.repository_id.trim() && (data.changed_files.trim() || String(data.pr_number || '').trim()),
);

export function CodeQualityPage() {
  const prior = useLocation().state?.reanalysis;
  const [selectedRepo, setSelectedRepo] = useState(prior?.repository_id || '');
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(Boolean(prior));
  const [formData, setFormData] = useState({
    repository_id: prior?.repository_id || '',
    pr_number: prior?.pr_number || '',
    analysis_level: 'standard',
    repository_ref: '',
    changed_files: prior?.changed_files?.join('\n') || '',
    reanalysis_of: prior?.run_id,
    use_ai: true,
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const {
    data: historyData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['code-quality', 'history', selectedRepo],
    queryFn: () => codeQualityApi.getHistory(selectedRepo, 20),
    enabled: Boolean(selectedRepo),
  });

  const analyzeMutation = useMutation({
    mutationFn: (data) =>
      codeQualityApi.startAnalysis({
        ...data,
        repository_ref: data.repository_ref || null,
        pr_number: data.pr_number ? parseInt(data.pr_number, 10) : null,
        changed_files: data.changed_files
          .split('\n')
          .map((f) => f.trim())
          .filter(Boolean),
      }),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['code-quality'] });
      setIsAnalyzeModalOpen(false);
      if (res?.run_id) {
        navigate(`/code-quality/runs/${res.run_id}`);
      }
    },
  });

  const handleStartAnalysis = (e) => {
    e.preventDefault();
    if (!canSubmit(formData)) return;
    analyzeMutation.mutate(formData);
  };

  const runs = historyData?.history || [];
  const statusColor = (status) => ({
    pending: 'var(--warning)',
    running: 'var(--cyan)',
    completed: 'var(--success)',
    failed: 'var(--danger)',
  }[status] || 'var(--text-muted)');

  const columns = [
    { key: 'run_id', header: 'Run ID', render: (r) => <span className="font-mono">{r.run_id}</span> },
    { key: 'language', header: 'Language', render: (r) => <span style={{ textTransform: 'capitalize', fontWeight: '600' }}>{r.language && r.language !== 'unknown' ? r.language : 'Undetermined'}</span> },
    {
      key: 'quality_score',
      header: 'Quality score',
      render: (r) => (
        r.quality_score != null ? (
          <span style={{ fontWeight: '600', color: getGradeColor(r.quality_grade || 'A') }}>
            {r.quality_score}/100
          </span>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
            {['pending', 'running'].includes(r.status) ? 'Pending' : 'Not measured'}
          </span>
        )
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (r) => r.risk_score != null ? <RiskBadge level={r.risk_level} score={r.risk_score} /> : <span>Not measured</span>,
    },
    {
      key: 'status',
      header: 'Status',
      render: (r) => (
        <span style={{ color: statusColor(r.status), fontWeight: '600', fontSize: '0.8125rem' }}>
          {qualityStatus(r)}
        </span>
      ),
    },
    { key: 'created_at', header: 'Date', render: (r) => formatDate(r.created_at) },
    {
      key: 'action',
      header: '',
      render: (r) => (
        <Button variant="secondary" size="sm" onClick={() => navigate(`/code-quality/runs/${r.run_id}`)}>
          {r.status === 'completed' ? 'View findings' : 'View run'} <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  return (
    <div className="cq">
      <PageHeader
        title="Code quality"
        subtitle="Static analysis, security and risk scoring."
        actions={
          <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}>
            <Button
              variant="primary"
              leftIcon={<Play size={16} />}
              onClick={() => { setFormData(data => ({ ...data, reanalysis_of: undefined })); setIsAnalyzeModalOpen(true); }}
            >
              Start analysis
            </Button>
          </PermissionGuard>
        }
      />

      <div className="cq-langs" aria-label="Supported languages">
        <span className="cq-langs-label"><Code2 size={15} aria-hidden="true" /> Auto-detected languages</span>
        {LANGUAGES.map((language) => <span key={language} className="cq-chip">{language}</span>)}
      </div>

      <Card title="Analysis history">
        <div className="cq-filter">
          <Input label="Project ID" value={selectedRepo}
            onChange={(event) => setSelectedRepo(event.target.value.trim())}
            placeholder="Enter a project ID" />
        </div>
        {isLoading ? (
          <LoadingState message="Loading analysis history..." />
        ) : error ? (
          <ErrorState message={error.message} onRetry={refetch} />
        ) : (
          <Table
            columns={columns}
            data={runs}
            emptyMessage={selectedRepo ? 'No analysis runs for this project.' : 'Enter a project ID to view its runs.'}
            onRowClick={(r) => navigate(`/code-quality/runs/${r.run_id}`)}
          />
        )}
      </Card>

      <PRAlgorithmIntelligencePanel />

      <details className="cq-advanced">
        <summary>Advanced tools<span>Benchmarks, compatibility and requirements</span></summary>
        <div className="cq-advanced-body cq-panel">
          <AlgorithmComparisonPanel />
          <BehavioralCompatibilityPanel />
          <RequirementsPanel />
        </div>
      </details>

      {/* Start Analysis Modal */}
      <Modal
        isOpen={isAnalyzeModalOpen}
        onClose={() => setIsAnalyzeModalOpen(false)}
        title="Start analysis"
        subtitle="Static analysis and AI review"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsAnalyzeModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleStartAnalysis}
              isLoading={analyzeMutation.isPending}
            >
              {canSubmit(formData) ? 'Run Analysis' : 'Enter repository and files or a PR number'}
            </Button>
          </>
        }
      >
        {analyzeMutation.error && <p role="alert">{analyzeMutation.error.message}</p>}
        {formData.reanalysis_of && <p>Reanalyzing {formData.reanalysis_of} at its recorded commit.</p>}
        <form onSubmit={handleStartAnalysis} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Repository or Project ID"
            value={formData.repository_id}
            onChange={(e) => setFormData({ ...formData, repository_id: e.target.value })}
            placeholder="e.g. organization/repository"
            required
          />
          <p style={{ marginTop: '-0.65rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Use the connected repository or project ID.
          </p>

          {!formData.pr_number && !formData.reanalysis_of && <Input label="Repository branch or commit (optional)"
            value={formData.repository_ref} placeholder="Default branch"
            onChange={(e) => setFormData({ ...formData, repository_ref: e.target.value })} />}
          <div className="form-columns">
            <Input
              label="PR number (optional)"
              type="number"
              value={formData.pr_number}
              onChange={(e) => setFormData({ ...formData, pr_number: e.target.value, repository_ref: '' })}
              placeholder="e.g. 42"
            />
            <Select
              label="Analysis level"
              value={formData.analysis_level}
              onChange={(e) => setFormData({ ...formData, analysis_level: e.target.value })}
              options={[
                { value: 'purpose_discovery', label: 'Function discovery only' },
                { value: 'quick', label: 'Quick' },
                { value: 'standard', label: 'Standard' },
                { value: 'deep', label: 'Deep (all tools + security)' },
              ]}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
              Changed files (one per line{formData.pr_number ? "; leave empty to use the PR's changed files" : ''})
            </label>
            <textarea
              rows={4}
              value={formData.changed_files}
              onChange={(e) => setFormData({ ...formData, changed_files: e.target.value })}
              placeholder="Paste real changed repository paths, one per line"
              style={{
                width: '100%',
                padding: '0.65rem 0.85rem',
                fontSize: '0.8125rem',
                backgroundColor: 'var(--bg-input)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-default)',
                borderRadius: 'var(--radius-md)',
                fontFamily: 'var(--font-mono)',
                outline: 'none',
                marginTop: '0.35rem',
              }}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
