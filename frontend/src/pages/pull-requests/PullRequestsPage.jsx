import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store/useAuthStore';
import { rolesApi } from '../../api/roles.api';
import { githubApi } from '../../api/github.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { GitPullRequest, ExternalLink, RefreshCw, CheckCircle, XCircle, Clock, AlertCircle } from 'lucide-react';
import { ROLES } from '../../utils/constants';
import { formatDate, timeAgo } from '../../utils/dates';

export function PullRequestsPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [isSyncModalOpen, setIsSyncModalOpen] = useState(false);
  const [syncData, setSyncData] = useState({ owner: '', repo: '', pr_number: '' });

  const queryClient = useQueryClient();
  const role = user?.role?.toUpperCase();
  const isLead = role === ROLES.LEAD;
  const isDeveloper = role === ROLES.DEVELOPER;

  const { data: prData, isLoading, error, refetch } = useQuery({
    queryKey: ['pull-requests', role],
    queryFn: () => isLead ? rolesApi.getReviewQueue() : rolesApi.getMyPRs(),
    retry: 1,
  });

  const syncMutation = useMutation({
    mutationFn: (data) => githubApi.syncPullRequest({
      owner: data.owner,
      repo: data.repo,
      pr_number: parseInt(data.pr_number),
    }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pull-requests'] });
      setIsSyncModalOpen(false);
      setSyncData({ owner: '', repo: '', pr_number: '' });
    },
  });

  const prs = isLead
    ? (prData?.pending_review || [])
    : (prData?.pull_requests || []);

  const filteredPrs = prs.filter((pr) => {
    const matchesSearch = !search ||
      pr.title?.toLowerCase().includes(search.toLowerCase()) ||
      pr.pr_number?.toString().includes(search) ||
      pr.author?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || pr.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusIcon = (status) => {
    switch (status) {
      case 'merged': return <CheckCircle size={14} style={{ color: 'var(--success)' }} />;
      case 'closed': return <XCircle size={14} style={{ color: 'var(--danger)' }} />;
      case 'open': return <Clock size={14} style={{ color: 'var(--primary)' }} />;
      default: return <AlertCircle size={14} style={{ color: 'var(--text-muted)' }} />;
    }
  };

  const columns = [
    {
      key: 'pr_number',
      header: 'PR #',
      render: (pr) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700' }}>
          #{pr.pr_number}
        </span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (pr) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <GitPullRequest size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
          <span style={{ fontWeight: '600' }}>{pr.title}</span>
        </div>
      ),
    },
    { key: 'author', header: 'Author', render: (pr) => pr.author || '—' },
    {
      key: 'status',
      header: 'Status',
      render: (pr) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {getStatusIcon(pr.status)}
          <StatusBadge status={pr.status} />
        </div>
      ),
    },
    {
      key: 'review_status',
      header: 'Review',
      render: (pr) => (
        <StatusBadge status={pr.review_status || 'pending'} />
      ),
    },
    {
      key: 'risk_level',
      header: 'Risk',
      render: (pr) => pr.risk_level ? <RiskBadge level={pr.risk_level} size="sm" /> : '—',
    },
    {
      key: 'created_at',
      header: 'Created',
      render: (pr) => (
        <span title={formatDate(pr.created_at)}>
          {timeAgo(pr.created_at)}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (pr) => (
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {pr.html_url && (
            <Button
              variant="ghost"
              size="sm"
              onClick={(e) => {
                e.stopPropagation();
                window.open(pr.html_url, '_blank');
              }}
            >
              <ExternalLink size={14} />
            </Button>
          )}
        </div>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading pull requests..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title={isLead ? 'PR Review Queue' : 'My Pull Requests'}
        subtitle={isLead
          ? 'Review pull requests from your team members.'
          : 'Track your pull requests, reviews, and CI status.'
        }
        actions={
          isDeveloper ? (
            <Button
              variant="primary"
              leftIcon={<RefreshCw size={16} />}
              onClick={() => setIsSyncModalOpen(true)}
            >
              Sync PR
            </Button>
          ) : undefined
        }
      />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Total PRs</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-primary)' }}>{prs.length}</div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Open</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--primary)' }}>
            {prs.filter((pr) => pr.status === 'open').length}
          </div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Pending Review</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--warning)' }}>
            {prs.filter((pr) => pr.review_status === 'pending').length}
          </div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Merged</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--success)' }}>
            {prs.filter((pr) => pr.status === 'merged').length}
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search PRs by title, number, or author..."
          width="320px"
        />
        <div style={{ width: '180px' }}>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            placeholder="All Statuses"
            options={[
              { value: 'open', label: 'Open' },
              { value: 'merged', label: 'Merged' },
              { value: 'closed', label: 'Closed' },
            ]}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredPrs}
        emptyMessage="No pull requests found matching your filters."
      />

      {/* Sync PR Modal */}
      <Modal
        isOpen={isSyncModalOpen}
        onClose={() => setIsSyncModalOpen(false)}
        title="Sync Pull Request"
        subtitle="Fetch a PR from GitHub and run AI analysis"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsSyncModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={() => syncMutation.mutate(syncData)}
              isLoading={syncMutation.isPending}
            >
              Sync PR
            </Button>
          </>
        }
      >
        <form onSubmit={(e) => { e.preventDefault(); syncMutation.mutate(syncData); }} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Repository Owner"
            value={syncData.owner}
            onChange={(e) => setSyncData({ ...syncData, owner: e.target.value })}
            placeholder="e.g. mounesh05"
            required
          />
          <Input
            label="Repository Name"
            value={syncData.repo}
            onChange={(e) => setSyncData({ ...syncData, repo: e.target.value })}
            placeholder="e.g. samanvaya"
            required
          />
          <Input
            label="PR Number"
            type="number"
            value={syncData.pr_number}
            onChange={(e) => setSyncData({ ...syncData, pr_number: e.target.value })}
            placeholder="e.g. 42"
            required
          />
        </form>
      </Modal>
    </div>
  );
}
