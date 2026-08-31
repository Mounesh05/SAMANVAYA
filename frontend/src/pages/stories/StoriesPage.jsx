import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { storiesApi } from '../../api/stories.api';
import { projectsApi } from '../../api/projects.api';
import { sprintsApi } from '../../api/sprints.api';
import { employeesApi } from '../../api/employees.api';
import { PageHeader } from '../../components/layout/PageHeader';
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
import { BookOpen, Plus, ArrowRight } from 'lucide-react';
import { DEFAULT_ORG_ID } from '../../utils/constants';

const STORY_STATUS = {
  TODO: 'todo',
  IN_PROGRESS: 'in_progress',
  REVIEW: 'review',
  DONE: 'done',
};

export function StoriesPage() {
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [selectedSprintId, setSelectedSprintId] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    project_id: '',
    sprint_id: '',
    assignee_id: '',
    points: '',
    priority: 'medium',
  });

  const queryClient = useQueryClient();

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
  });

  const { data: sprints = [] } = useQuery({
    queryKey: ['sprints', 'project', selectedProjectId],
    queryFn: () => sprintsApi.listByProject(selectedProjectId),
    enabled: !!selectedProjectId,
  });

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
  });

  const activeProjectId = selectedProjectId || projects[0]?.id || '';
  const activeSprintId = selectedSprintId || '';

  const { data: stories = [], isLoading, error, refetch } = useQuery({
    queryKey: ['stories', 'sprint', activeSprintId],
    queryFn: () => storiesApi.listBySprint(activeSprintId),
    enabled: !!activeSprintId,
  });

  const createMutation = useMutation({
    mutationFn: (data) => storiesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stories'] });
      setIsCreateModalOpen(false);
      setFormData({
        title: '',
        description: '',
        project_id: activeProjectId,
        sprint_id: activeSprintId,
        assignee_id: '',
        points: '',
        priority: 'medium',
      });
    },
  });

  const filteredStories = stories.filter((story) => {
    const matchesSearch = !search ||
      story.title?.toLowerCase().includes(search.toLowerCase()) ||
      story.id?.toLowerCase().includes(search.toLowerCase());
    const matchesStatus = !statusFilter || story.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const columns = [
    {
      key: 'id',
      header: 'Story ID',
      render: (story) => (
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700' }}>{story.id}</span>
      ),
    },
    {
      key: 'title',
      header: 'Title',
      render: (story) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <BookOpen size={14} style={{ color: 'var(--primary)', flexShrink: 0 }} />
          <span style={{ fontWeight: '600' }}>{story.title}</span>
        </div>
      ),
    },
    {
      key: 'points',
      header: 'Points',
      render: (story) => (
        <Badge variant="primary" size="sm">{story.points || '—'}</Badge>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (story) => <StatusBadge status={story.status} />,
    },
    {
      key: 'priority',
      header: 'Priority',
      render: (story) => (
        <span style={{ textTransform: 'capitalize' }}>{story.priority || '—'}</span>
      ),
    },
    { key: 'assignee_id', header: 'Assignee', render: (story) => story.assignee_id || 'Unassigned' },
    {
      key: 'actions',
      header: 'Actions',
      render: () => (
        <Button variant="secondary" size="sm">
          Details <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  if (isLoading) return <LoadingState message="Loading stories..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Stories"
        subtitle="Manage user stories, acceptance criteria, and sprint planning."
        actions={
          <Button
            variant="primary"
            leftIcon={<Plus size={16} />}
            onClick={() => setIsCreateModalOpen(true)}
          >
            Create Story
          </Button>
        }
      />

      {/* Filters */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.5rem', flexWrap: 'wrap' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search stories..."
          width="260px"
        />
        <div style={{ width: '220px' }}>
          <Select
            value={activeProjectId}
            onChange={(e) => { setSelectedProjectId(e.target.value); setSelectedSprintId(''); }}
            options={projects.map((p) => ({ value: p.id, label: p.name }))}
          />
        </div>
        <div style={{ width: '220px' }}>
          <Select
            value={activeSprintId}
            onChange={(e) => setSelectedSprintId(e.target.value)}
            placeholder="Select Sprint"
            options={sprints.map((s) => ({ value: s.id, label: s.name || s.sprint_id }))}
          />
        </div>
        <div style={{ width: '160px' }}>
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            placeholder="All Statuses"
            options={Object.values(STORY_STATUS).map((s) => ({
              value: s,
              label: s.replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
            }))}
          />
        </div>
      </div>

      <Table
        columns={columns}
        data={filteredStories}
        emptyMessage="No stories found. Select a project and sprint to view stories."
      />

      {/* Create Story Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Story"
        subtitle="Add a user story to the sprint backlog"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => createMutation.mutate(formData)} isLoading={createMutation.isPending}>
              Create Story
            </Button>
          </>
        }
      >
        <form style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Story Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="e.g. As a user, I want to reset my password"
            required
          />
          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Acceptance criteria and details"
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Project"
              value={formData.project_id}
              onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
            <Select
              label="Sprint"
              value={formData.sprint_id}
              onChange={(e) => setFormData({ ...formData, sprint_id: e.target.value })}
              options={sprints.map((s) => ({ value: s.id, label: s.name || s.sprint_id }))}
            />
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
            <Select
              label="Assignee"
              value={formData.assignee_id}
              onChange={(e) => setFormData({ ...formData, assignee_id: e.target.value })}
              placeholder="Unassigned"
              options={employees.map((e) => ({ value: e.employee_id, label: e.name }))}
            />
            <Input
              label="Story Points"
              type="number"
              value={formData.points}
              onChange={(e) => setFormData({ ...formData, points: e.target.value })}
              placeholder="e.g. 5"
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
        </form>
      </Modal>
    </div>
  );
}
