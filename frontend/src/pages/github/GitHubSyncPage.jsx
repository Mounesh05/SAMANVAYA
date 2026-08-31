import React, { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { githubApi } from '../../api/github.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { GitPullRequest, RefreshCw, CheckCircle, ShieldCheck, Sparkles, AlertCircle } from 'lucide-react';

export function GitHubSyncPage() {
  const [prForm, setPrForm] = useState({
    owner: 'facebook',
    repo: 'react',
    pr_number: '25840',
    project_id: 'PRJ-CORE',
    use_ai: true,
  });

  const [syncResult, setSyncResult] = useState(null);

  // Health check query
  const { data: health, isLoading: isHealthLoading } = useQuery({
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
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        <Card title="Synchronize Single PR" subtitle="Fetch PR metadata and analyze risk">
          <form onSubmit={handleSync} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="Repository Owner"
                value={prForm.owner}
                onChange={(e) => setPrForm({ ...prForm, owner: e.target.value })}
                placeholder="e.g. facebook"
                required
              />
              <Input
                label="Repository Name"
                value={prForm.repo}
                onChange={(e) => setPrForm({ ...prForm, repo: e.target.value })}
                placeholder="e.g. react"
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="PR Number"
                type="number"
                value={prForm.pr_number}
                onChange={(e) => setPrForm({ ...prForm, pr_number: e.target.value })}
                placeholder="e.g. 25840"
                required
              />
              <Input
                label="Target Project ID"
                value={prForm.project_id}
                onChange={(e) => setPrForm({ ...prForm, project_id: e.target.value })}
                placeholder="e.g. PRJ-CORE"
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
