import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { StatusBadge } from '../../components/common/StatusBadge';
import { Badge } from '../../components/common/Badge';
import { MetricCard } from '../../components/common/MetricCard';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { AlertTriangle, Plus, AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react';
import { formatDate, timeAgo } from '../../utils/dates';

const INCIDENT_STATUS = {
  OPEN: 'open',
  INVESTIGATING: 'investigating',
  RESOLVED: 'resolved',
  CLOSED: 'closed',
};

const INCIDENT_SEVERITY = {
  LOW: 'low',
  MEDIUM: 'medium',
  HIGH: 'high',
  CRITICAL: 'critical',
};

export function IncidentsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    severity: 'medium',
    service: '',
    assignee_id: '',
  });

  const { data: incidentData, isLoading, error, refetch } = useQuery({
    queryKey: ['incidents'],
    queryFn: async () => {
      // Placeholder - will be replaced with real API when backend implements incidents
      return { incidents: [], total: 0 };
    },
    retry: 1,
  });

  const incidents = incidentData?.incidents || [];

  const filteredIncidents = incidents.filter((incident) => {
    const matchesSearch = !search ||
      incident.title?.toLowerCase().includes(search.toLowerCase()) ||
      incident.id?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || incident.status === statusFilter;
    const matchesSeverity = !severityFilter || incident.severity === severityFilter;
    return matchesSearch && matchesStatus && matchesSeverity;
  });

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical': return <XCircle size={14} style={{ color: 'var(--danger)' }} />;
      case 'high': return <AlertTriangle size={14} style={{ color: 'var(--warning)' }} />;
      case 'medium': return <Clock size={14} style={{ color: 'var(--primary)' }} />;
      default: return <AlertCircle size={14} style={{ color: 'var(--text-muted)' }} />;
    }
  };

  const columns = [
    {
      key: 'id',
      header: 'Incident ID',
      render: (inc) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700' }}>{inc.id}</span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (inc) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <AlertTriangle size={14} style={{ color: 'var(--danger)', flexShrink: 0 }} />
          <span style={{ fontWeight: '600' }}>{inc.title}</span>
        </div>
      ),
    },
    {
      key: 'severity',
      header: 'Severity',
      render: (inc) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {getSeverityIcon(inc.severity)}
          <Badge variant={inc.severity === 'critical' || inc.severity === 'high' ? 'danger' : inc.severity === 'medium' ? 'warning' : 'default'} size="sm">
            {inc.severity?.toUpperCase()}
          </Badge>
        </div>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (inc) => <StatusBadge status={inc.status} />,
    },
    { key: 'service', header: 'Service', render: (inc) => inc.service || '—' },
    { key: 'assignee_id', header: 'Assignee', render: (inc) => inc.assignee_id || 'Unassigned' },
    {
      key: 'created_at',
      header: 'Reported',
      render: (inc) => (
        <span title={formatDate(inc.created_at)}>
          {timeAgo(inc.created_at)}
        </span>
      ),
    },
    {
      key: 'resolved_at',
      header: 'Resolved',
      render: (inc) => inc.resolved_at ? (
        <span title={formatDate(inc.resolved_at)}>
          {timeAgo(inc.resolved_at)}
        </span>
      ) : (
        <span style={{ color: 'var(--text-muted)' }}>—</span>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading incidents..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Incidents"
        subtitle="Track, manage, and resolve production incidents."
        actions={
          <Button
            variant="primary"
            leftIcon={<Plus size={16} />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Report Incident
          </Button>
        }
      />

      {/* Summary Metrics */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
        <MetricCard
          title="Active Incidents"
          value={incidents.filter((i) => i.status === 'open' || i.status === 'investigating').length}
          icon={<AlertTriangle size={20} />}
          color="danger"
        />
        <MetricCard
          title="Critical"
          value={incidents.filter((i) => i.severity === 'critical').length}
          icon={<XCircle size={20} />}
          color="danger"
        />
        <MetricCard
          title="Resolved Today"
          value={incidents.filter((i) => i.status === 'resolved').length}
          icon={<CheckCircle size={20} />}
          color="success"
        />
        <MetricCard
          title="Total Incidents"
          value={incidents.length}
          icon={<AlertCircle size={20} />}
          color="primary"
        />
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search incidents..."
          width="280px"
        />
        <div style={{ width: '160px' }}>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            placeholder="All Statuses"
            options={Object.values(INCIDENT_STATUS).map((s) => ({
              value: s,
              label: s.charAt(0).toUpperCase() + s.slice(1),
            }))}
          />
        </div>
        <div style={{ width: '160px' }}>
          <Select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            placeholder="All Severities"
            options={Object.values(INCIDENT_SEVERITY).map((s) => ({
              value: s,
              label: s.charAt(0).toUpperCase() + s.slice(1),
            }))}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredIncidents}
        emptyMessage="No active incidents. All systems operational."
      />

      {/* Create Incident Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Report Incident"
        subtitle="Document a production incident"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setIsCreateModalOpen(false)}>
              Report Incident
            </Button>
          </>
        }
      >
        <form style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Incident Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="e.g. API response time degraded"
            required
          />
          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Impact and symptoms observed"
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Severity"
              value={formData.severity}
              onChange={(e) => setFormData({ ...formData, severity: e.target.value })}
              options={Object.values(INCIDENT_SEVERITY).map((s) => ({
                value: s,
                label: s.charAt(0).toUpperCase() + s.slice(1),
              }))}
            />
            <Input
              label="Affected Service"
              value={formData.service}
              onChange={(e) => setFormData({ ...formData, service: e.target.value })}
              placeholder="e.g. api-gateway"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
