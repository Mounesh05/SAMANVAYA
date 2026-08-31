import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { codeQualityApi } from '../../api/codeQuality.api';
import { projectsApi } from '../../api/projects.api';
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
import { ShieldCheck, Play, ArrowRight, Activity, Code2, AlertTriangle } from 'lucide-react';
import { formatDate } from '../../utils/dates';
import { getGradeColor } from '../../utils/formatters';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';

export function CodeQualityPage() {
  const [selectedRepo, setSelectedRepo] = useState('samanvaya-core');
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    repository_id: 'samanvaya-core',
    pr_number: '',
    analysis_level: 'standard',
    changed_files: 'src/auth/login.py\nsrc/core/security.py',
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
  });

  const analyzeMutation = useMutation({
    mutationFn: (data) =>
      codeQualityApi.startAnalysis({
        ...data,
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
    analyzeMutation.mutate(formData);
  };

  const runs = historyData?.history || [];

  const columns = [
    { key: 'run_id', header: 'Run ID', render: (r) => <span className="font-mono">{r.run_id}</span> },
    { key: 'language', header: 'Language', render: (r) => <span style={{ textTransform: 'capitalize', fontWeight: '600' }}>{r.language || 'Multi'}</span> },
    {
      key: 'quality_score',
      header: 'Quality Score',
      render: (r) => (
        <span style={{ fontWeight: '800', color: getGradeColor(r.quality_grade || 'A') }}>
          {r.quality_score !== null ? `${r.quality_score}/100` : '—'}
        </span>
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (r) => <RiskBadge level={r.risk_level || 'LOW'} score={r.risk_score} />,
    },
    { key: 'status', header: 'Status', render: (r) => <span style={{ textTransform: 'capitalize' }}>{r.status}</span> },
    { key: 'created_at', header: 'Date', render: (r) => formatDate(r.created_at) },
    {
      key: 'action',
      header: 'Action',
      render: (r) => (
        <Button variant="secondary" size="sm" onClick={() => navigate(`/code-quality/runs/${r.run_id}`)}>
          Inspect Findings <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Unified Code Quality & Multi-Language Engine"
        subtitle="Language-agnostic quality inspection, static analysis, security vulnerabilities, and risk scoring."
        actions={
          <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}>
            <Button
              variant="primary"
              leftIcon={<Play size={16} />}
              onClick={() => setIsAnalyzeModalOpen(true)}
            >
              Start Analysis Run
            </Button>
          </PermissionGuard>
        }
      />

      {/* Language Engine Banner */}
      <Card
        padding="md"
        style={{
          background: 'linear-gradient(135deg, rgba(6, 182, 212, 0.1) 0%, rgba(59, 130, 246, 0.08) 100%)',
          border: '1px solid rgba(6, 182, 212, 0.25)',
          marginBottom: '1.75rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
            <div
              style={{
                width: '40px',
                height: '40px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--cyan-light)',
                color: 'var(--cyan)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Code2 size={22} />
            </div>
            <div>
              <h4 style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                Multi-Language Support Active
              </h4>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                Analyzes Java, C++, TypeScript, JavaScript, Python, Go, and Rust with zero manual language configuration.
              </p>
            </div>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <LoadingState message="Loading code quality history..." />
      ) : error ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : (
        <Card title="Analysis History" subtitle="Recent quality runs and findings">
          <Table
            columns={columns}
            data={runs}
            emptyMessage="No analysis runs recorded for this repository."
            onRowClick={(r) => navigate(`/code-quality/runs/${r.run_id}`)}
          />
        </Card>
      )}

      {/* Start Analysis Modal */}
      <Modal
        isOpen={isAnalyzeModalOpen}
        onClose={() => setIsAnalyzeModalOpen(false)}
        title="Start Code Quality Analysis"
        subtitle="Trigger static analysis and AI code review"
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
              Run Analysis
            </Button>
          </>
        }
      >
        <form onSubmit={handleStartAnalysis} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Repository ID"
            value={formData.repository_id}
            onChange={(e) => setFormData({ ...formData, repository_id: e.target.value })}
            placeholder="e.g. samanvaya-core"
            required
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="PR Number (Optional)"
              type="number"
              value={formData.pr_number}
              onChange={(e) => setFormData({ ...formData, pr_number: e.target.value })}
              placeholder="e.g. 184"
            />
            <Select
              label="Analysis Level"
              value={formData.analysis_level}
              onChange={(e) => setFormData({ ...formData, analysis_level: e.target.value })}
              options={[
                { value: 'quick', label: 'Quick' },
                { value: 'standard', label: 'Standard' },
                { value: 'deep', label: 'Deep (Full Tools + Security)' },
              ]}
            />
          </div>

          <div>
            <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
              Changed Files (One per line)
            </label>
            <textarea
              rows={4}
              value={formData.changed_files}
              onChange={(e) => setFormData({ ...formData, changed_files: e.target.value })}
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
