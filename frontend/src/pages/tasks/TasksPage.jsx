import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { tasksApi } from '../../api/tasks.api';
import { projectsApi } from '../../api/projects.api';
import { employeesApi } from '../../api/employees.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { StatusBadge } from '../../components/common/StatusBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Plus, KanbanSquare } from 'lucide-react';
import { TASK_STATUS, STATUS_LABELS, DEFAULT_ORG_ID, ROLES } from '../../utils/constants';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';

export function TasksPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const canTransitionTask = role === ROLES.PM || role === ROLES.LEAD || role === ROLES.DEVELOPER;

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [taskDetail, setTaskDetail] = useState(null);

  const [formData, setFormData] = useState({
    title: '',
    project_id: '',
    assignee_id: '',
    type: 'feature',
    priority: 'high',
    due_date: '',
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
  });

  const activeProjectId = selectedProjectId || projects[0]?.id || '';

  const {
    data: tasks = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', 'project', activeProjectId],
    queryFn: () => tasksApi.listByProject(activeProjectId),
    enabled: !!activeProjectId,
  });

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list'],
    queryFn: () => employeesApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => tasksApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setIsCreateModalOpen(false);
      setFormData({
        title: '',
        project_id: activeProjectId,
        assignee_id: '',
        type: 'feature',
        priority: 'high',
        due_date: '',
      });
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({ taskId, status }) => tasksApi.updateStatus(taskId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      setTaskDetail(null);
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    createMutation.mutate({
      ...formData,
      project_id: formData.project_id || activeProjectId,
    });
  };

  const filteredTasks = tasks.filter((t) => {
    const matchesSearch =
      t.title.toLowerCase().includes(search.toLowerCase()) ||
      (t.assignee_id && t.assignee_id.toLowerCase().includes(search.toLowerCase()));
    const matchesStatus = !statusFilter || t.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const columns = [
    { key: 'title', header: 'Task Title', render: (t) => <span style={{ fontWeight: '600' }}>{t.title}</span> },
    { key: 'id', header: 'Task ID', render: (t) => <span className="font-mono">{t.id}</span> },
    { key: 'assignee_id', header: 'Assignee', render: (t) => t.assignee_id || 'Unassigned' },
    { key: 'type', header: 'Type', render: (t) => <span style={{ textTransform: 'capitalize' }}>{t.type}</span> },
    { key: 'priority', header: 'Priority', render: (t) => <span style={{ textTransform: 'capitalize' }}>{t.priority}</span> },
    { key: 'status', header: 'Status', render: (t) => <StatusBadge status={t.status} /> },
    { key: 'due_date', header: 'Due Date', render: (t) => t.due_date || '—' },
    {
      key: 'action',
      header: 'Actions',
      render: (t) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={(e) => {
            e.stopPropagation();
            setTaskDetail(t);
          }}
        >
          Update
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Tasks & Backlog"
        subtitle="Create, assign, track, and update engineering work items."
        actions={
          <div style={{ display: 'flex', gap: '0.65rem' }}>
            <Button
              variant="secondary"
              leftIcon={<KanbanSquare size={16} />}
              onClick={() => navigate('/board')}
            >
              Open Kanban Board
            </Button>
            <PermissionGuard permission={PERMISSIONS.CREATE_TASK}>
              <Button
                variant="primary"
                leftIcon={<Plus size={16} />}
                onClick={() => {
                  setFormData({ ...formData, project_id: activeProjectId });
                  setIsCreateModalOpen(true);
                }}
              >
                New Task
              </Button>
            </PermissionGuard>
          </div>
        }
      />

      {/* Filter and Search Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search tasks or assignee..."
            width="280px"
          />

          <div style={{ width: '220px' }}>
            <Select
              value={activeProjectId}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
            />
          </div>

          <div style={{ width: '180px' }}>
            <Select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              placeholder="All Statuses"
              options={Object.values(TASK_STATUS).map((s) => ({
                value: s,
                label: STATUS_LABELS[s] || s,
              }))}
            />
          </div>
        </div>
      </div>

      {isLoading ? (
        <LoadingState message="Loading tasks..." />
      ) : error ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : (
        <Table
          columns={columns}
          data={filteredTasks}
          emptyMessage="No tasks found matching your filters."
          onRowClick={(t) => setTaskDetail(t)}
        />
      )}

      {/* Task Detail / Status Update Modal */}
      <Modal
        isOpen={!!taskDetail}
        onClose={() => setTaskDetail(null)}
        title={taskDetail?.title || 'Task Details'}
        subtitle={`Task ID: ${taskDetail?.id}`}
        footer={
          <Button variant="secondary" onClick={() => setTaskDetail(null)}>
            Close
          </Button>
        }
      >
        {taskDetail && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.875rem', color: 'var(--text-muted)' }}>Current Status:</span>
              <StatusBadge status={taskDetail.status} size="md" />
            </div>

            <div>
              <h4 style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Transition Status:
              </h4>
              {canTransitionTask ? (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                  {Object.values(TASK_STATUS).map((status) => (
                    <Button
                      key={status}
                      variant={taskDetail.status === status ? 'primary' : 'secondary'}
                      size="sm"
                      onClick={() =>
                        transitionMutation.mutate({
                          taskId: taskDetail.id,
                          status,
                        })
                      }
                      isLoading={transitionMutation.isPending}
                    >
                      Move to {STATUS_LABELS[status]}
                    </Button>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  You do not have permission to transition this task.
                </p>
              )}
            </div>
          </div>
        )}
      </Modal>

      {/* Create Task Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Task"
        subtitle="Add a work item to the project backlog"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} isLoading={createMutation.isPending}>
              Create Task
            </Button>
          </>
        }
      >
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Task Title"
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            placeholder="e.g. Write unit tests for OAuth flow"
            required
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Project"
              value={formData.project_id || activeProjectId}
              onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
              required
            />
            <Select
              label="Assignee"
              value={formData.assignee_id}
              onChange={(e) => setFormData({ ...formData, assignee_id: e.target.value })}
              placeholder="Unassigned"
              options={employees.map((e) => ({
                value: e.employee_id,
                label: `${e.name} (${e.employee_id})`,
              }))}
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
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
              required
            />
            <Input
              label="Due Date"
              type="date"
              value={formData.due_date}
              onChange={(e) => setFormData({ ...formData, due_date: e.target.value })}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
