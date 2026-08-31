import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { activityApi } from '../../api/activity.api';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { SearchInput } from '../../components/common/SearchInput';
import { Select } from '../../components/common/Select';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { History, User, FolderGit2, ListTodo, Users, Settings, Shield, GitPullRequest } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';
import { ROLES } from '../../utils/constants';

const ACTIVITY_TYPES = {
  employee_created: { label: 'Employee Created', icon: User, color: 'primary' },
  employee_edited: { label: 'Employee Edited', icon: User, color: 'info' },
  employee_deactivated: { label: 'Employee Deactivated', icon: User, color: 'danger' },
  team_created: { label: 'Team Created', icon: Users, color: 'primary' },
  team_member_changed: { label: 'Team Membership Changed', icon: Users, color: 'info' },
  team_lead_assigned: { label: 'Team Lead Assigned', icon: Users, color: 'warning' },
  project_created: { label: 'Project Created', icon: FolderGit2, color: 'primary' },
  project_membership_changed: { label: 'Project Membership Changed', icon: FolderGit2, color: 'info' },
  feedback_submitted: { label: 'Feedback Submitted', icon: History, color: 'success' },
  evaluation_triggered: { label: 'Evaluation Triggered', icon: Shield, color: 'purple' },
  evaluation_completed: { label: 'Evaluation Completed', icon: Shield, color: 'success' },
  role_changed: { label: 'Role Changed', icon: Settings, color: 'warning' },
  task_created: { label: 'Task Created', icon: ListTodo, color: 'primary' },
  task_completed: { label: 'Task Completed', icon: ListTodo, color: 'success' },
  pr_merged: { label: 'PR Merged', icon: GitPullRequest, color: 'success' },
};

export function AuditLogsPage() {
  const { user } = useAuthStore();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const role = user?.role?.toUpperCase();
  const canViewAll = role === ROLES.HR || role === ROLES.CEO;

  const { data: activityData, isLoading, error, refetch } = useQuery({
    queryKey: ['activity', 'me'],
    queryFn: () => activityApi.getMyFeed(),
    retry: 1,
  });

  const activities = activityData?.activities || activityData?.items || activityData || [];

  const filteredActivities = activities.filter((activity) => {
    const matchesSearch = !search ||
      activity.description?.toLowerCase().includes(search.toLowerCase()) ||
      activity.user?.toLowerCase().includes(search.toLowerCase()) ||
      activity.entity_type?.toLowerCase().includes(search.toLowerCase());
    const matchesType = !typeFilter || activity.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const getActivityConfig = (type) => {
    return ACTIVITY_TYPES[type] || { label: type, icon: History, color: 'default' };
  };

  const columns = [
    {
      key: 'timestamp',
      header: 'Time',
      render: (a) => (
        <span title={formatDate(a.timestamp)} style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
          {timeAgo(a.timestamp)}
        </span>
      ),
    },
    {
      key: 'type',
      header: 'Action',
      render: (a) => {
        const config = getActivityConfig(a.type);
        const Icon = config.icon;
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Icon size={14} style={{ color: `var(--${config.color})` }} />
            <Badge variant={config.color} size="sm">{config.label}</Badge>
          </div>
        );
      },
    },
    {
      key: 'description',
      header: 'Description',
      render: (a) => (
        <span style={{ fontSize: '0.875rem' }}>{a.description || '—'}</span>
      ),
    },
    {
      key: 'user',
      header: 'User',
      render: (a) => (
        <span style={{ fontWeight: '600' }}>{a.user || a.performed_by || '—'}</span>
      ),
    },
    {
      key: 'entity_type',
      header: 'Entity',
      render: (a) => a.entity_type || '—',
    },
    {
      key: 'entity_id',
      header: 'Entity ID',
      render: (a) => a.entity_id ? (
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8125rem' }}>{a.entity_id}</span>
      ) : '—',
    },
  ];

  if (isLoading) return <LoadingState message="Loading audit logs..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Audit Logs"
        subtitle={canViewAll
          ? 'Organization-wide audit trail of sensitive actions and changes.'
          : 'Your recent activity and action history.'
        }
      />

      {!canViewAll && (
        <Card
          variant="flat"
          padding="md"
          style={{ marginBottom: '1.5rem', backgroundColor: 'var(--bg-elevated)' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            <Shield size={16} style={{ color: 'var(--warning)' }} />
            <span>
              Full audit log access is restricted to HR and CEO roles. You can view your own activity below.
            </span>
          </div>
        </Card>
      )}

      {/* Summary */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Total Actions</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--text-primary)' }}>{activities.length}</div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>Today</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--primary)' }}>
            {activities.filter((a) => {
              const today = new Date().toDateString();
              return new Date(a.timestamp).toDateString() === today;
            }).length}
          </div>
        </Card>
        <Card variant="flat" padding="md">
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.25rem' }}>This Week</div>
          <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--success)' }}>
            {activities.filter((a) => {
              const weekAgo = new Date();
              weekAgo.setDate(weekAgo.getDate() - 7);
              return new Date(a.timestamp) >= weekAgo;
            }).length}
          </div>
        </Card>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by description, user, or entity..."
          width="320px"
        />
        <div style={{ width: '200px' }}>
          <Select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            placeholder="All Action Types"
            options={Object.entries(ACTIVITY_TYPES).map(([key, val]) => ({
              value: key,
              label: val.label,
            }))}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredActivities}
        emptyMessage="No audit log entries found."
      />
    </div>
  );
}
