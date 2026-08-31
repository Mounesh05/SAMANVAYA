import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Bug, Plus, AlertTriangle, CheckCircle, Clock, XCircle } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';

const BUG_STATUS = {
  OPEN: 'open',
  IN_PROGRESS: 'in_progress',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
};

const BUG_SEVERITY = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

const SEVERITY_COLORS = {
  low: 'default',
  medium: 'warning',
  high: 'danger',
  critical: 'danger',
};

export function BugsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'medium',
    priority: 'medium',
    assignee_id: '',
    steps_to_reproduce: '',
  });

  const { data: bugData, isLoading, error, refetch } = useQuery({
    queryKey: ['bugs'],
    queryFn: () => rolesApi.getBugs(),
    retry: 1,
  });

  const bugs = bugData?.bugs || [];

  const filteredBugs = bugs.filter((bug) => {
    const matchesSearch = !search ||
      bug.title?.toLowerCase().includes(search.toLowerCase()) ||
      bug.id?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || bug.status === statusFilter;
    const matchesSeverity = !severityFilter || bug.severity === severityFilter;
    return matchesSearch && matchesStatus && matchesSeverity;
  });

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <XCircle size={14} style={{ color: 'var(--danger)' }} />;
      case 'high': return <AlertTriangle size={14} style={{ color: 'var(--warning)' }} />;
      case 'medium': return <Clock size={14} style={{ color: 'var(--primary)' }} />;
      default: return <CheckCircle size={14} style={{ color: 'var(--success)' }} />;
    }
  };

  const columns = [
    {
      key: 'id',
      header: 'Bug ID',
      render: (bug) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700' }}>
          {bug.id}
        </span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (bug) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <Bug size={14} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <span style={{ fontWeight: '600' }}>{bug.title}</span>
        </div>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (bug) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {getSeverityIcon(bug.severity)}
          <Badge variant={SEVERITY_COLORS[bug.severity] || 'default'} size="sm">
            {bug.severity?.toUpperCase()}
          </Badge>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (bug) => <StatusBadge status={bug.status} />,
    },
    { key: 'assignee_id', header: 'Assignee', render: (bug) => bug.assignee_id || 'Unassigned' },
    { key: 'reporter', header: 'Reporter', render: (bug) => bug.reporter || '—' },
    {
      key: 'created_at',
      header: 'Reported',
      render: (bug) => (
        <span title={formatDate(bug.created_at)}>
          {timeAgo(bug.created_at)}
        </span>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading bug reports..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Bug Tracking"
        subtitle="Create, track, and manage software defects and quality issues."
        actions={
          <Button
            variant="primary"
            leftIcon={<Plus size={16} />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Report Bug
          </Button>
        }
      />

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Total Bugs</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-primary)' }}>{bugs.length}</div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Open</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--primary)' }}>
            {bugs.filter((b) => b.status === 'open').length}
          </div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Critical/High</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--danger)' }}>
            {bugs.filter((b) => b.severity === 'critical' || b.severity === 'high').length}
          </div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Resolved</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--success)' }}>
            {bugs.filter((b) => b.status === 'resolved').length}
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search bugs by title or ID..."
          width="280px"
        />
        <div style={{ width: '160px' }}>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            placeholder="All Statuses"
            options={Object.values(BUG_STATUS).map((s) => ({
              value: s,
              label: s.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
            }))}
          />
        </div>
        <div style={{ width: '160px' }}>
          <Select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            placeholder="All Severities"
            options={Object.values(BUG_SEVERITY).map((s) => ({
              value: s,
              label: s.charAt(0).toUpperCase() + s.slice(1),
            }))}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredBugs}
        emptyMessage="No bug reports found matching your filters."
      />

      {/* Create Bug Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Report Bug"
        subtitle="Document a software defect or quality issue"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setIsCreateModalOpen(false)}>
              Report Bug
            </Button>
          </>
        }
      >
        <form style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Bug Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="e.g. Login button not responding on mobile"
            required
          />
          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Detailed description of the bug"
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Severity"
              value={formData.severity}
              onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
              options={Object.values(BUG_SEVERITY).map((s) => ({
                value: s,
                label: s.charAt(0).toUpperCase() + s.slice(1),
              }))}
            />
            <Select
              label="Priority"
              value={formData.priority}
              onChange={(e) => setFormData({ ...formData, priority: e.target.value })}
              options={[
                { value: 'low', label: 'Low' },
                { value: 'medium', label: 'Medium' },
                { value: 'high', label: 'High' },
                { value: 'critical', label: 'Critical' },
              ]}
            />
          </div>
          <Input
            label="Steps to Reproduce"
            value={formData.steps_to_reproduce}
            onChange={(e) => setFormData({ ...formData, steps_to_reproduce: e.target.value })}
            placeholder="1. Go to login page&#10;2. Click login button&#10;3. Observe error"
          />
        </form>
      </Modal>
    </div>
  );
}
