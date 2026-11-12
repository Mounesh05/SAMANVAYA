import React, { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { qaApi } from '../../api/qa.api';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
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
import { MetricCard } from '../../components/common/MetricCard';
import { Bug, Clock3, RotateCcw } from 'lucide-react';

const EMPTY_DEFECT = {
  title: '',
  description: '',
  steps_to_reproduce: '',
  expected_result: '',
  actual_result: '',
  severity: 'medium',
  priority: 'medium',
};
const EMPTY_LIST = [];

const TRANSITIONS = {
  QA: {
    OPEN: ['ASSIGNED'],
    ASSIGNED: ['IN_PROGRESS'],
    IN_PROGRESS: ['FIXED'],
    FIXED: ['READY_FOR_RETEST'],
    READY_FOR_RETEST: ['CLOSED', 'REOPENED'],
    REOPENED: ['ASSIGNED', 'IN_PROGRESS'],
  },
  DEVELOPER: { ASSIGNED: ['IN_PROGRESS'], IN_PROGRESS: ['FIXED'], FIXED: ['READY_FOR_RETEST'], REOPENED: ['IN_PROGRESS'] },
  DEVOPS: { ASSIGNED: ['IN_PROGRESS'], IN_PROGRESS: ['FIXED'], FIXED: ['READY_FOR_RETEST'], REOPENED: ['IN_PROGRESS'] },
};

export function BugsPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  // CR-002: QA actions follow permissions, as on the backend.
  const canVerifyDefects = hasPermission(user, PERMISSIONS.VERIFY_DEFECTS);
  const canLinkTestCases = hasPermission(user, PERMISSIONS.MANAGE_TEST_CASES);
  // Anyone with CREATE_BUG reports defects; QA still assigns, verifies and closes.
  const canReportDefect = hasPermission(user, PERMISSIONS.CREATE_BUG);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [modal, setModal] = useState('');
  const [selectedDefect, setSelectedDefect] = useState(null);
  const [form, setForm] = useState(EMPTY_DEFECT);
  const [assigneeId, setAssigneeId] = useState('');
  const [feedback, setFeedback] = useState('');

  const projectsQuery = useQuery({ queryKey: ['qa-projects'], queryFn: qaApi.getProjects });
  const projects = projectsQuery.data || EMPTY_LIST;
  const projectId = selectedProjectId || projects[0]?.id || '';
  const defectsQuery = useQuery({
    queryKey: ['qa-defects', projectId],
    queryFn: () => qaApi.getDefects(projectId),
    enabled: Boolean(projectId),
  });
  const defects = defectsQuery.data || EMPTY_LIST;

  const visibleDefects = useMemo(() => defects.filter((defect) => {
    const term = search.trim().toLowerCase();
    return (!term || [defect.id, defect.title, defect.story_id, defect.test_case_id]
      .some((value) => value?.toLowerCase().includes(term)))
      && (!statusFilter || defect.status === statusFilter)
      && (!severityFilter || defect.severity === severityFilter);
  }), [defects, search, severityFilter, statusFilter]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['qa-defects', projectId] });
    queryClient.invalidateQueries({ queryKey: ['qa-dashboard'] });
  };
  const createMutation = useMutation({
    mutationFn: () => qaApi.createDefect({
      project_id: projectId,
      ...form,
      story_id: form.story_id || null,
      task_id: form.task_id || null,
      test_case_id: form.test_case_id || null,
    }),
    onSuccess: (defect) => {
      setModal('');
      setForm(EMPTY_DEFECT);
      setFeedback(`Defect ${defect.id} reported.`);
      refresh();
    },
    onError: (error) => setFeedback(error.message),
  });
  const updateMutation = useMutation({
    mutationFn: ({ defectId, data }) => qaApi.updateDefect(defectId, data),
    onSuccess: (updated) => {
      setSelectedDefect(updated);
      setAssigneeId(updated.assignee_id || '');
      queryClient.setQueryData(['qa-defect', updated.id], updated);
      setFeedback('Defect updated.');
      refresh();
    },
    onError: (error) => setFeedback(error.message),
  });
  const detailQuery = useQuery({
    queryKey: ['qa-defect', selectedDefect?.id],
    queryFn: () => qaApi.getDefect(selectedDefect.id),
    enabled: Boolean(selectedDefect?.id) && modal === 'detail',
  });
  const defectDetail = detailQuery.data || selectedDefect;

  const columns = [
    { key: 'id', header: 'Defect ID', render: (item) => <strong>{item.id}</strong> },
    { key: 'title', header: 'Title', render: (item) => item.title },
    { key: 'severity', header: 'Severity', render: (item) => <Badge>{item.severity?.toUpperCase()}</Badge> },
    { key: 'status', header: 'Status', render: (item) => <StatusBadge status={item.status} /> },
    { key: 'assignee_id', header: 'Assignee', render: (item) => item.assignee_id || 'Unassigned' },
    { key: 'story_id', header: 'Story', render: (item) => item.story_id || '—' },
    {
      key: 'actions',
      header: 'Actions',
      render: (item) => (
        <Button size="sm" variant="secondary" onClick={() => {
          setSelectedDefect(item);
          setAssigneeId(item.assignee_id || '');
          setFeedback('');
          setModal('detail');
        }}>Details</Button>
      ),
    },
  ];

  if (projectsQuery.isLoading) return <LoadingState message="Loading authorized QA projects..." />;
  if (projectsQuery.error) return <ErrorState message={projectsQuery.error.message} onRetry={projectsQuery.refetch} />;
  if (defectsQuery.error) return <ErrorState message={defectsQuery.error.message} onRetry={defectsQuery.refetch} />;

  const openCount = defects.filter((item) => item.status !== 'CLOSED').length;
  const retestCount = defects.filter((item) => item.status === 'READY_FOR_RETEST').length;

  return (
    <div>
      <PageHeader
        title="Defect Tracking"
        subtitle="Track project defects through assignment, fix, retest, and closure."
        actions={
          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
            <div style={{ width: 240 }}>
              <Select aria-label="QA project" value={projectId} onChange={(event) => setSelectedProjectId(event.target.value)} options={projects.map((project) => ({ value: project.id, label: project.name }))} placeholder="Select project" />
            </div>
            {canReportDefect && <Button onClick={() => { setForm(EMPTY_DEFECT); setFeedback(''); setModal('create'); }}>Report Defect</Button>}
          </div>
        }
      />
      {feedback && <p role="status">{feedback}</p>}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.25rem' }}>
        <MetricCard title="Defects" value={defects.length} icon={<Bug size={20} />} color="primary" />
        <MetricCard title="Open" value={openCount} icon={<Clock3 size={20} />} color="warning" />
        <MetricCard title="Awaiting Retest" value={retestCount} icon={<RotateCcw size={20} />} color="cyan" />
      </div>
      <Card title="Project Defects">
        <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
          <SearchInput value={search} onChange={setSearch} placeholder="Search defect, story, or test..." width="300px" />
          <div style={{ width: 180 }}>
            <Select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} placeholder="All statuses" options={Object.keys(TRANSITIONS.QA).concat('CLOSED').map((status) => ({ value: status, label: status.replaceAll('_', ' ') }))} />
          </div>
          <div style={{ width: 180 }}>
            <Select value={severityFilter} onChange={(event) => setSeverityFilter(event.target.value)} placeholder="All severities" options={['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value }))} />
          </div>
        </div>
        {defectsQuery.isLoading ? <LoadingState message="Loading project defects..." /> : (
          <Table columns={columns} data={visibleDefects} emptyMessage="No defects found for this project or filter." />
        )}
      </Card>

      <Modal isOpen={modal === 'create'} onClose={() => setModal('')} title="Report Defect">
        <form onSubmit={(event) => { event.preventDefault(); createMutation.mutate(); }} style={{ display: 'grid', gap: '0.75rem' }}>
          <Input label="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} required />
          <Input label="Description" value={form.description} onChange={(event) => setForm({ ...form, description: event.target.value })} required />
          <Input label="Steps to reproduce" value={form.steps_to_reproduce} onChange={(event) => setForm({ ...form, steps_to_reproduce: event.target.value })} />
          <Input label="Expected result" value={form.expected_result} onChange={(event) => setForm({ ...form, expected_result: event.target.value })} />
          <Input label="Actual result" value={form.actual_result} onChange={(event) => setForm({ ...form, actual_result: event.target.value })} />
          <Input label="Story ID (optional)" value={form.story_id || ''} onChange={(event) => setForm({ ...form, story_id: event.target.value })} />
          <Input label="Task ID (optional)" value={form.task_id || ''} onChange={(event) => setForm({ ...form, task_id: event.target.value })} />
          {canLinkTestCases && <Input label="Test Case ID (optional)" value={form.test_case_id || ''} onChange={(event) => setForm({ ...form, test_case_id: event.target.value })} />}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
            <Select label="Severity" value={form.severity} onChange={(event) => setForm({ ...form, severity: event.target.value })} options={['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value }))} />
            <Select label="Priority" value={form.priority} onChange={(event) => setForm({ ...form, priority: event.target.value })} options={['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: value }))} />
          </div>
          {feedback && <p role="alert">{feedback}</p>}
          <Button type="submit" isLoading={createMutation.isPending}>Create Defect</Button>
        </form>
      </Modal>

      <Modal isOpen={modal === 'detail'} onClose={() => setModal('')} title={defectDetail?.title || 'Defect Details'} maxWidth="760px">
        {detailQuery.isLoading ? <LoadingState message="Loading defect details..." /> : detailQuery.error ? <ErrorState message={detailQuery.error.message} onRetry={detailQuery.refetch} /> : defectDetail && (
          <div style={{ display: 'grid', gap: '0.85rem' }}>
            <div><strong>{defectDetail.id}</strong> · {defectDetail.status} · {defectDetail.severity}/{defectDetail.priority}</div>
            <p>{defectDetail.description}</p>
            <p><strong>Steps:</strong> {defectDetail.steps_to_reproduce || '—'}</p>
            <p><strong>Expected:</strong> {defectDetail.expected_result || '—'}</p>
            <p><strong>Actual:</strong> {defectDetail.actual_result || '—'}</p>
            <p><strong>Story / Task / Test:</strong> {[defectDetail.story_id, defectDetail.task_id, defectDetail.test_case_id].filter(Boolean).join(' / ') || '—'}</p>
            <p><strong>Reporter:</strong> {defectDetail.reporter_name} · <strong>Assignee:</strong> {defectDetail.assignee_id || 'Unassigned'}</p>

            {canVerifyDefects && (
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'end' }}>
                <Input label="Assign to employee ID" value={assigneeId} onChange={(event) => setAssigneeId(event.target.value)} />
                <Button variant="secondary" onClick={() => updateMutation.mutate({ defectId: defectDetail.id, data: { assignee_id: assigneeId || null } })}>Assign</Button>
              </div>
            )}

            {defectDetail.status === 'READY_FOR_RETEST' && canVerifyDefects && defectDetail.test_case_id && (
              <Button onClick={() => navigate(`/tests?caseId=${encodeURIComponent(defectDetail.test_case_id)}&defectId=${encodeURIComponent(defectDetail.id)}`)}>Retest linked case</Button>
            )}

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
              {(TRANSITIONS[role] || {})[defectDetail.status]?.map((status) => (
                <Button key={status} variant={status === 'CLOSED' ? 'primary' : 'secondary'} isLoading={updateMutation.isPending} onClick={() => updateMutation.mutate({ defectId: defectDetail.id, data: { status } })}>Move to {status.replaceAll('_', ' ')}</Button>
              ))}
            </div>
            <Card title="Status history">
              {(defectDetail.history || []).map((item, index) => <div key={`${item.at}-${index}`} style={{ padding: '0.45rem 0', borderBottom: '1px solid var(--border-subtle)' }}>{item.status} · {item.actor_id} · {item.at}</div>)}
            </Card>
            {feedback && <p role="status">{feedback}</p>}
          </div>
        )}
      </Modal>
    </div>
  );
}
