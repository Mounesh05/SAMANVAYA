import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { incidentsApi } from '../../api/incidents.api';
import { projectsApi } from '../../api/projects.api';
import { DEFAULT_ORG_ID } from '../../utils/constants';
import { useToast } from '../../components/common/Toast';
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

// Next status actions (backend: open -> investigating -> resolved -> closed)
const NEXT_ACTIONS = {
  open: [{ status: 'investigating', label: 'Investigate' }, { status: 'resolved', label: 'Resolve' }],
  investigating: [{ status: 'resolved', label: 'Resolve' }],
  resolved: [{ status: 'closed', label: 'Close' }, { status: 'investigating', label: 'Reopen' }],
  closed: [],
};

const EMPTY_FORM = {
  project_id: '',
  title: '',
  description: '',
  severity: 'medium',
  service: '',
  assignee_id: '',
};

function isToday(value) {
  if (!value) return false;
  const date = new Date(value);
  const now = new Date();
  return date.getFullYear() === now.getFullYear()
    && date.getMonth() === now.getMonth()
    && date.getDate() === now.getDate();
}

export function IncidentsPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const queryClient = useQueryClient();
  const toast = useToast();

  const { data: incidentData, isLoading, error, refetch } = useQuery({
    queryKey: ['incidents'],
    queryFn: () => incidentsApi.list(),
    retry: 1,
  });

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', DEFAULT_ORG_ID],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
  });

  const createMutation = useMutation({
    mutationFn: (data) => incidentsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
      setIsCreateModalOpen(false);
      setFormData(EMPTY_FORM);
      toast.success('Incident reported');
    },
    onError: (err) => toast.error(err.message || 'Could not report the incident'),
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }) => incidentsApi.update(id, { status }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['incidents'] }),
    onError: (err) => toast.error(err.message || 'Could not update the incident'),
  });

  const projectId = formData.project_id || projects[0]?.id || '';

  const submitIncident = () => {
    if (!formData.title.trim() || !projectId) return;
    createMutation.mutate({
      project_id: projectId,
      title: formData.title.trim(),
      severity: formData.severity,
      description: formData.description || undefined,
      service: formData.service || undefined,
      assignee_id: formData.assignee_id || undefined,
    });
  };

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
    {
      key: 'actions',
      header: 'Actions',
      render: (inc) => (
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          {(NEXT_ACTIONS[inc.status] || []).map((action) => (
            <Button
              key={action.status}
              size="sm"
              variant="secondary"
              disabled={statusMutation.isPending}
              onClick={() => statusMutation.mutate({ id: inc.id, status: action.status })}
            >
              {action.label}
            </Button>
          ))}
        </div>
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
          value={incidents.filter((i) => isToday(i.resolved_at)).length}
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
            <Button
              variant="primary"
              onClick={submitIncident}
              disabled={!formData.title.trim() || !projectId || createMutation.isPending}
            >
              Report Incident
            </Button>
          </>
        }
      >
        <form
          style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}
          onSubmit={(e) => { e.preventDefault(); submitIncident(); }}
        >
          <Select
            label="Project"
            value={projectId}
            onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
            options={projects.map((p) => ({ value: p.id, label: p.name || p.id }))}
          />
          <Input
            label="Incident Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="Summarize the incident"
            required
          />
          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Describe the impact and observed symptoms"
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
              placeholder="Enter the affected service or component"
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
