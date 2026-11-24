import { useSessionScope } from '../../store/useSessionScope';
import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { tasksApi } from '../../api/tasks.api';
import { projectsApi } from '../../api/projects.api';
import { employeesApi } from '../../api/employees.api';
import { sprintsApi } from '../../api/sprints.api';
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
import { TASK_STATUS, STATUS_LABELS } from '../../utils/constants';
import { canUpdateTask, isSignOffOnly, SIGN_OFF_TARGETS } from '../../utils/taskPermissions';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS, hasPermission } from '../../auth/permissions';
import { TaskDeliveryPanel } from './TaskDeliveryPanel';

export function TasksPage() {
  const sessionScope = useSessionScope();
  const { user } = useAuthStore();
  // Leads/PMs plan work for others; contributors create tasks for themselves
  // (the backend refuses anything else).
  const assignsOthers = hasPermission(user, PERMISSIONS.MOVE_TASK);

  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [params, setParams] = useSearchParams();
  const selectedProjectId = params.get('project');
  const selectedTaskId = params.get('task');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);

  const [formData, setFormData] = useState({
    title: '',
    project_id: '',
    assignee_id: '',
    sprint_id: '',
    type: 'feature',
    priority: 'high',
    due_date: '',
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const projectsQuery = useQuery({
    queryKey: ['projects', 'list', sessionScope],
    queryFn: () => projectsApi.list(),
  });

  const projects = projectsQuery.data || [];
  const activeProjectId = selectedProjectId
    ? projects.find((p) => p.id === selectedProjectId)?.id || ''
    : projects[0]?.id || '';

  const {
    data: tasks = [],
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', 'project', activeProjectId, sessionScope],
    queryFn: () => tasksApi.listByProject(activeProjectId),
    enabled: !!activeProjectId,
  });
  const taskDetail = selectedTaskId
    ? tasks.find((t) => t.id === selectedTaskId && (!t.project_id || t.project_id === activeProjectId))
    : null;
  const setTaskDetail = (task) => {
    const next = new URLSearchParams(params);
    if (task) {
      next.set('project', activeProjectId);
      next.set('task', task.id);
    } else {
      next.delete('task');
    }
    setParams(next, { replace: true });
  };

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'list', sessionScope],
    queryFn: () => employeesApi.list(),
    enabled: assignsOthers,
  });

  const { data: sprints = [] } = useQuery({
    queryKey: ['sprints', 'project', activeProjectId, sessionScope],
    queryFn: () => sprintsApi.listByProject(activeProjectId),
    enabled: !!activeProjectId,
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
        sprint_id: '',
        type: 'feature',
        priority: 'high',
        due_date: '',
      });
    },
  });

  const transitionMutation = useMutation({
    mutationFn: ({ taskId, status }) => tasksApi.transition(taskId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
      queryClient.invalidateQueries({ queryKey: ['board'] });
      queryClient.invalidateQueries({ queryKey: ['pm-blocked-work'] });
      setTaskDetail(null);
    },
  });

  const {
    data: availableTransitions = [],
    isLoading: isTransitionsLoading,
    error: transitionsError,
  } = useQuery({
    queryKey: ['task-transitions', taskDetail?.id, sessionScope],
    queryFn: () => tasksApi.getAvailableTransitions(taskDetail.id),
    enabled: !!taskDetail?.id,
    select: (result) => result.allowed_statuses,
  });

  const sprintMutation = useMutation({
    mutationFn: ({ taskId, sprintId }) => tasksApi.updateSprint(taskId, sprintId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    createMutation.mutate({
      ...formData,
      project_id: formData.project_id || activeProjectId,
      assignee_id: assignsOthers ? formData.assignee_id : user?.employee_id,
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
      render: (t) => canUpdateTask(user, t) ? (
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
      ) : null,
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
              onChange={(e) => setParams({ project: e.target.value }, { replace: true })}
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

      {projectsQuery.error ? (
        <ErrorState message={projectsQuery.error.message} onRetry={projectsQuery.refetch} />
      ) : projectsQuery.isLoading || isLoading ? (
        <LoadingState message="Loading tasks..." />
      ) : error ? (
        <ErrorState message={error.message} onRetry={refetch} />
      ) : (
        <>
        {selectedTaskId && !taskDetail && <p role="status">This task is unavailable in the selected project.</p>}
        <Table
          columns={columns}
          data={filteredTasks}
          emptyMessage="No tasks found matching your filters."
          onRowClick={(t) => setTaskDetail(t)}
        />
        </>
      )}

      {/* Task Detail / Status Update Modal */}
      <Modal
        isOpen={!!taskDetail}
        onClose={() => setTaskDetail(null)}
        title={taskDetail?.title || 'Task Details'}
        maxWidth="680px"
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
            <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '0.4rem 0.75rem', margin: 0, fontSize: '0.8125rem' }}>
              <dt style={{ color: 'var(--text-muted)' }}>Assignee</dt>
              <dd style={{ margin: 0, color: 'var(--text-primary)' }}>{taskDetail.assignee_id || 'Unassigned'}</dd>
              <dt style={{ color: 'var(--text-muted)' }}>Type</dt>
              <dd style={{ margin: 0, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{taskDetail.type || '—'}</dd>
              <dt style={{ color: 'var(--text-muted)' }}>Priority</dt>
              <dd style={{ margin: 0, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{taskDetail.priority || '—'}</dd>
              <dt style={{ color: 'var(--text-muted)' }}>Sprint</dt>
              <dd style={{ margin: 0, color: 'var(--text-primary)' }}>{taskDetail.sprint_id || 'Unassigned'}</dd>
              {taskDetail.story_id && (
                <>
                  <dt style={{ color: 'var(--text-muted)' }}>Story</dt>
                  <dd style={{ margin: 0, color: 'var(--text-primary)' }}>{taskDetail.story_id}</dd>
                </>
              )}
              {taskDetail.due_date && (
                <>
                  <dt style={{ color: 'var(--text-muted)' }}>Due date</dt>
                  <dd style={{ margin: 0, color: 'var(--text-primary)' }}>{taskDetail.due_date}</dd>
                </>
              )}
            </dl>

            <TaskDeliveryPanel key={JSON.stringify([sessionScope, taskDetail.id])} taskId={taskDetail.id} />

            {assignsOthers ? (
              <Select
                label="Sprint"
                value={taskDetail.sprint_id || ''}
                onChange={(e) => {
                  sprintMutation.mutate({
                    taskId: taskDetail.id,
                    sprintId: e.target.value,
                  });
                }}
                placeholder="No sprint"
                options={sprints.map((sprint) => ({
                  value: sprint.id,
                  label: sprint.name,
                }))}
                disabled={sprintMutation.isPending}
              />
            ) : null}

            <div>
              <h4 style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                Transition Status:
              </h4>
              {canUpdateTask(user, taskDetail) ? (
                isTransitionsLoading ? (
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Loading valid transitions...</p>
                ) : transitionsError ? (
                  <p role="alert" style={{ fontSize: '0.8125rem', color: 'var(--danger)' }}>
                    Could not load valid transitions: {transitionsError.message}
                  </p>
                ) : availableTransitions.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                    {availableTransitions
                      .filter((status) => !isSignOffOnly(user, taskDetail) || SIGN_OFF_TARGETS.includes(status))
                      .map((status) => (
                      <Button
                        key={status}
                        variant="secondary"
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
                    No workflow transitions are available from this status.
                  </p>
                )
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
            placeholder="Describe the task"
            required
          />

          <div className="form-columns">
            <Select
              label="Project"
              value={formData.project_id || activeProjectId}
              onChange={(e) => setFormData({ ...formData, project_id: e.target.value })}
              options={projects.map((p) => ({ value: p.id, label: p.name }))}
              required
            />
            {assignsOthers ? (
              <Select
                label="Assignee"
                value={formData.assignee_id}
                onChange={(e) => setFormData({ ...formData, assignee_id: e.target.value })}
                placeholder="No assignee selected"
                options={employees.map((e) => ({
                  value: e.employee_id,
                  label: `${e.name} (${e.employee_id})`,
                }))}
              />
            ) : (
              <Input label="Assignee" value={user?.name || user?.employee_id || ''} readOnly />
            )}
            <Select
              label="Sprint"
              value={formData.sprint_id}
              onChange={(e) => setFormData({ ...formData, sprint_id: e.target.value })}
              placeholder="No sprint selected"
              options={sprints.map((sprint) => ({
                value: sprint.id,
                label: sprint.name,
              }))}
            />
          </div>

          <div className="form-columns">
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
