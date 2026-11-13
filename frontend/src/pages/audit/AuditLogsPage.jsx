import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { auditApi } from '../../api/audit.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { SearchInput } from '../../components/common/SearchInput';
import { Select } from '../../components/common/Select';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Shield } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';

/** Readable names for audit actions; anything else is shown as it is. */
const ACTION_LABELS = {
  USER_CREATED: 'Employee created',
  USER_UPDATED: 'Employee updated',
  USER_ACTIVATED: 'Account activated',
  USER_DEACTIVATED: 'Account deactivated',
  ADMIN_GRANTED: 'Admin rights granted',
  ADMIN_REVOKED: 'Admin rights removed',
  EXPORT_DATA: 'Report exported',
  INCIDENT_UPDATED: 'Incident triaged',
  TRANSFER_APPROVED: 'Transfer approved',
  TRANSFER_REJECTED: 'Transfer rejected',
  TRANSFER_EXECUTED: 'Transfer executed',
};
const SENSITIVE = new Set(['ADMIN_GRANTED', 'ADMIN_REVOKED', 'USER_DEACTIVATED', 'EXPORT_DATA']);

const label = (action) => ACTION_LABELS[action] || (action || '').replaceAll('_', ' ').toLowerCase();

function summarise(details) {
  if (!details || typeof details !== 'object') return '—';
  const parts = [];
  if (details.field) parts.push(`${details.field}: ${JSON.stringify(details.old ?? null)} → ${JSON.stringify(details.new ?? null)}`);
  if (details.purpose) parts.push(`purpose: ${details.purpose}`);
  if (details.approval_requested) parts.push(`approval requested ${details.approval_requested}`);
  if (details.approved_by) parts.push(`approved by ${details.approved_by}`);
  if (details.second_approver === 'none_available') parts.push('no second approver available');
  if (details.action && details.changes) parts.push(`${details.action}`);
  if (details.row_count !== undefined) parts.push(`${details.row_count} rows`);
  return parts.length ? parts.join(' · ') : '—';
}

/**
 * The audit trail of sensitive actions. The page opens for VIEW_AUDIT_LOGS
 * holders (CEO, admins, HR and some HR designations); the backend decides
 * which events each of them receives (HR accounts see HR-relevant events).
 */
export function AuditLogsPage() {
  const [search, setSearch] = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['audit-logs', actionFilter],
    queryFn: () => auditApi.list({ action: actionFilter }),
    retry: 1,
  });

  const logs = data?.logs || [];
  const actions = [...new Set([...(data?.allowed_actions || []), ...logs.map((l) => l.action)])].filter(Boolean).sort();
  const filtered = logs.filter((log) => {
    if (!search) return true;
    const text = `${log.actor_name || ''} ${log.actor_id || ''} ${log.resource_type || ''} ${log.resource_id || ''} ${label(log.action)}`;
    return text.toLowerCase().includes(search.toLowerCase());
  });

  const columns = [
    {
      key: 'timestamp',
      header: 'Time',
      render: (l) => (
        <span title={formatDate(l.timestamp)} style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>{timeAgo(l.timestamp)}</span>
      ),
    },
    {
      key: 'action',
      header: 'Action',
      render: (l) => <Badge variant={SENSITIVE.has(l.action) ? 'warning' : 'info'} size="sm">{label(l.action)}</Badge>,
    },
    { key: 'actor', header: 'By', render: (l) => <span style={{ fontWeight: 600 }}>{l.actor_name || l.actor_id || '—'}</span> },
    { key: 'resource', header: 'On', render: (l) => (l.resource_type ? `${l.resource_type} ${l.resource_id || ''}` : '—') },
    { key: 'details', header: 'Details', render: (l) => <span style={{ fontSize: '0.8125rem' }}>{summarise(l.details)}</span> },
    { key: 'success', header: 'Result', render: (l) => (l.success === false ? <Badge variant="danger" size="sm">failed</Badge> : 'ok') },
  ];

  if (isLoading) return <LoadingState message="Loading audit logs..." />;
  if (error) return <ErrorState message={error?.response?.data?.detail || error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader title="Audit Logs" subtitle="Audit trail of sensitive actions: accounts, approvals, exports, transfers and incidents." />

      {data?.filtered_for_role === 'HR' && (
        <Card variant="flat" padding="md" style={{ marginBottom: '1.5rem', backgroundColor: 'var(--bg-elevated)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            <Shield size={16} style={{ color: 'var(--warning)' }} />
            <span>Showing HR-relevant events (employee lifecycle and team structure).</span>
          </div>
        </Card>
      )}

      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput value={search} onChange={setSearch} placeholder="Search by person, record or action..." width="320px" />
        <div style={{ width: '220px' }}>
          <Select
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder="All actions"
            options={actions.map((a) => ({ value: a, label: label(a) }))}
          />
        </div>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{filtered.length} of {data?.total ?? logs.length} entries</span>
      </div>

      <Table columns={columns} data={filtered} emptyMessage="No audit log entries found." />
    </div>
  );
}
