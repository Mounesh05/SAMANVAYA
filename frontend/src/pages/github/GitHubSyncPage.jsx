import React, { useEffect, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { githubApi } from '../../api/github.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';

import { GitPullRequest, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react';

export function GitHubSyncPage() {
  const [prForm, setPrForm] = useState({
    owner: '',
    repo: '',
    pr_number: '',
    project_id: '',
    use_ai: true,
  });

  const [syncResult, setSyncResult] = useState(null);
  const [qaForm, setQaForm] = useState({ owner: '', repo: '', project_id: '' });
  const [projectConfigForm, setProjectConfigForm] = useState({
    project_id: 'PRJ-CF0346FA',
    repository_owner: 'Mounesh05',
    repository_name: 'campusconnect-demo',
    repository_url: 'https://github.com/Mounesh05/campusconnect-demo',
    default_branch: 'main',
    employee_id: 'DEMO-MOUNESH',
    github_username: 'Mounesh05',
    branch: 'feature/mounesh-events',
  });

  const projectConfigQuery = useQuery({
    queryKey: ['github', 'project-config', projectConfigForm.project_id],
    queryFn: () => githubApi.getProjectConfig(projectConfigForm.project_id),
    enabled: !!projectConfigForm.project_id,
    retry: false,
  });

  useEffect(() => {
    if (projectConfigQuery.data) {
      const mapping = projectConfigQuery.data.developer_mappings?.[0] || {};
      setProjectConfigForm((current) => ({
        ...current,
        ...projectConfigQuery.data,
        employee_id: mapping.employee_id || current.employee_id,
        github_username: mapping.github_username || current.github_username,
        branch: mapping.branch || current.branch,
      }));
    }
  }, [projectConfigQuery.data]);

  const projectConfigMutation = useMutation({
    mutationFn: (form) =>
      githubApi.saveProjectConfig(form.project_id, {
        project_id: form.project_id,
        repository_owner: form.repository_owner,
        repository_name: form.repository_name,
        repository_url: form.repository_url,
        default_branch: form.default_branch,
        developer_mappings: [{
          employee_id: form.employee_id,
          github_username: form.github_username,
          branch: form.branch,
        }],
      }),
    onSuccess: (data) => {
      projectConfigQuery.refetch();
      setProjectConfigForm((current) => ({
        ...current,
        ...data,
        ...(data.developer_mappings?.[0] || {}),
      }));
    },
  });

  // Health check query
  const { data: health } = useQuery({
    queryKey: ['github', 'health'],
    queryFn: () => githubApi.checkHealth(),
  });

  const syncMutation = useMutation({
    mutationFn: (data) =>
      githubApi.syncPullRequest({
        ...data,
        pr_number: parseInt(data.pr_number, 10),
      }),
    onSuccess: (res) => {
      setSyncResult(res);
    },
  });

  const handleSync = (e) => {
    e.preventDefault();
    syncMutation.mutate(prForm);
  };

  const provisionMutation = useMutation({
    mutationFn: (data) => githubApi.provisionQaWorkflow(data),
  });

  const handleProvision = (e) => {
    e.preventDefault();
    provisionMutation.mutate(qaForm);
  };

  return (
    <div>
      <PageHeader
        title="GitHub Integration & PR Synchronizer"
        subtitle="Connect GitHub repositories, synchronize pull requests, and trigger AI-assisted code reviews."
      />

      {/* Integration Health Card */}
      <div style={{ marginBottom: '1.75rem' }}>
        <Card padding="md">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <div
                style={{
                  width: '40px',
                  height: '40px',
                  borderRadius: 'var(--radius-md)',
                  backgroundColor: health?.status === 'operational' ? 'var(--success-light)' : 'var(--warning-light)',
                  color: health?.status === 'operational' ? 'var(--success)' : 'var(--warning)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <GitPullRequest size={20} />
              </div>

              <Card
                title="Automatic QA Setup"
                subtitle="Install Samanvaya's GitHub Actions test workflow and configure encrypted repository secrets."
                style={{ marginBottom: '1.75rem' }}
              >
                <form onSubmit={handleProvision} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr auto', gap: '1rem', alignItems: 'end' }}>
                  <Input label="Repository Owner" value={qaForm.owner} onChange={(e) => setQaForm({ ...qaForm, owner: e.target.value })} placeholder="Organization or user" required />
                  <Input label="Repository Name" value={qaForm.repo} onChange={(e) => setQaForm({ ...qaForm, repo: e.target.value })} placeholder="Repository name" required />
                  <Input label="Project ID" value={qaForm.project_id} onChange={(e) => setQaForm({ ...qaForm, project_id: e.target.value })} placeholder="e.g. PRJ-001" required />
                  <Button type="submit" variant="primary" isLoading={provisionMutation.isPending} leftIcon={<ShieldCheck size={16} />}>
                    Configure QA Automatically
                  </Button>
                </form>
                {provisionMutation.isSuccess && (
                  <div style={{ marginTop: '1rem', color: 'var(--success)', fontSize: '0.875rem' }}>
                    GitHub Actions QA workflow installed successfully.
                  </div>
                )}
                {provisionMutation.isError && (
                  <div style={{ marginTop: '1rem', color: 'var(--danger)', fontSize: '0.875rem' }}>
                    QA setup failed: {provisionMutation.error?.response?.data?.detail || provisionMutation.error?.message}
                  </div>
                )}
              </Card>
              <div>
                <div style={{ fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  GitHub API Gateway: {health?.status === 'operational' ? 'Operational' : 'Ready'}
                </div>
                <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  {health?.authenticated_as ? `Authenticated as: @${health.authenticated_as}` : 'Configured via backend'}
                </div>
              </div>
            </div>

            <Button variant="ghost" size="sm" leftIcon={<RefreshCw size={14} />} onClick={() => window.location.reload()}>
              Refresh Status
            </Button>
          </div>
        </Card>
      </div>

      {/* Sync PR Form & Result */}
      <Card
        title="Project Repository Configuration"
        subtitle="Validate and persist the repository and verified developer branch mapping."
        style={{ marginBottom: '1.5rem' }}
      >
        <form
          onSubmit={(e) => {
            e.preventDefault();
            projectConfigMutation.mutate(projectConfigForm);
          }}
          style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' }}
        >
          {[
            ['project_id', 'Project ID'],
            ['repository_owner', 'Repository Owner'],
            ['repository_name', 'Repository Name'],
            ['repository_url', 'Repository URL'],
            ['default_branch', 'Default Branch'],
            ['employee_id', 'Employee ID'],
            ['github_username', 'GitHub Username'],
            ['branch', 'Developer Branch'],
          ].map(([field, label]) => (
            <Input
              key={field}
              label={label}
              value={projectConfigForm[field]}
              onChange={(e) => setProjectConfigForm({ ...projectConfigForm, [field]: e.target.value })}
              required
            />
          ))}
          <Button type="submit" variant="primary" isLoading={projectConfigMutation.isPending}>
            Validate & Save Configuration
          </Button>
        </form>
        {projectConfigMutation.isSuccess && (
          <div style={{ marginTop: '1rem', color: 'var(--success)', fontSize: '0.875rem' }}>
            Repository and branch mapping saved.
          </div>
        )}
        {projectConfigMutation.isError && (
          <div style={{ marginTop: '1rem', color: 'var(--danger)', fontSize: '0.875rem' }}>
            Configuration failed: {projectConfigMutation.error?.response?.data?.detail || projectConfigMutation.error?.message}
          </div>
        )}
      </Card>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        <Card title="Synchronize Single PR" subtitle="Fetch PR metadata and analyze risk">
          <form onSubmit={handleSync} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="Repository Owner"
                value={prForm.owner}
                onChange={(e) => setPrForm({ ...prForm, owner: e.target.value })}
                placeholder="e.g. organization"
                required
              />
              <Input
                label="Repository Name"
                value={prForm.repo}
                onChange={(e) => setPrForm({ ...prForm, repo: e.target.value })}
                placeholder="e.g. repository-name"
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="PR Number"
                type="number"
                value={prForm.pr_number}
                onChange={(e) => setPrForm({ ...prForm, pr_number: e.target.value })}
                placeholder="e.g. 42"
                required
              />
              <Input
                label="Target Project ID"
                value={prForm.project_id}
                onChange={(e) => setPrForm({ ...prForm, project_id: e.target.value })}
                placeholder="e.g. PRJ-001"
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              isLoading={syncMutation.isPending}
              leftIcon={<GitPullRequest size={16} />}
              style={{ marginTop: '0.5rem' }}
            >
              Sync & Analyze Pull Request
            </Button>
          </form>
        </Card>

        {/* Sync Result Card */}
        <Card title="Analysis & Sync Results" subtitle="Layer 5 Risk + AI Code Review">
          {syncMutation.isPending ? (
            <LoadingState message="Syncing with GitHub and calculating risk..." />
          ) : syncResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <span style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  {syncResult.message}
                </span>
                <RiskBadge level={syncResult.risk_level || 'LOW'} score={syncResult.risk_score} size="md" />
              </div>

              {syncResult.ai_analysis && (
                <div
                  style={{
                    padding: '0.85rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(59, 130, 246, 0.08)',
                    border: '1px solid rgba(59, 130, 246, 0.2)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: '700', fontSize: '0.8125rem', color: 'var(--cyan)', marginBottom: '0.35rem' }}>
                    <Sparkles size={16} /> AI Code Review
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    {typeof syncResult.ai_analysis === 'string'
                      ? syncResult.ai_analysis
                      : JSON.stringify(syncResult.ai_analysis, null, 2)}
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Enter repository details on the left and submit to view sync results.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
