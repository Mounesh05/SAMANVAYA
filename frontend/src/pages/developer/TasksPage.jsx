/**
 * Tasks Page — developer view of own tasks
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Filter } from 'lucide-react';
import { tasksApi } from '../../api/tasks.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, PriorityBadge } from '../../components/common/Badges';
import { formatDate, timeAgo } from '../../utils/dates';
import toast from 'react-hot-toast';

const STATUS_FILTERS = ['ALL', 'TODO', 'IN_PROGRESS', 'REVIEW', 'DONE'];

export function TasksPage() {
  const [statusFilter, setStatusFilter] = useState('ALL');
  const qc = useQueryClient();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['tasks', { status: statusFilter }],
    queryFn: () =>
      tasksApi.list(statusFilter !== 'ALL' ? { status: statusFilter } : {}).then((r) => r.data),
  });

  const tasks = Array.isArray(data) ? data : data?.tasks || [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">My Tasks</h1>
          <p className="page-subtitle">{tasks.length} task{tasks.length !== 1 ? 's' : ''}</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="tabs">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            className={`tab-btn${statusFilter === s ? ' active' : ''}`}
            onClick={() => setStatusFilter(s)}
          >
            {s.replace('_', ' ')}
          </button>
        ))}
      </div>

      {isLoading && <LoadingState message="Loading tasks…" />}
      {isError && <ErrorState description={error.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && tasks.length === 0 && (
        <EmptyState title="No tasks" description="You have no tasks matching the selected filter." />
      )}

      {!isLoading && !isError && tasks.length > 0 && (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Task</th>
                <th>Status</th>
                <th>Priority</th>
                <th>Sprint</th>
                <th>Due Date</th>
                <th>Updated</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task._id || task.id}>
                  <td>
                    <div style={{ fontWeight: 500, color: 'var(--text-primary)', marginBottom: 2 }}>
                      {task.title}
                    </div>
                    {task.description && (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 320 }}>
                        {task.description}
                      </div>
                    )}
                  </td>
                  <td><StatusBadge status={task.status} /></td>
                  <td><PriorityBadge priority={task.priority} /></td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{task.sprint_name || task.sprint_id || '—'}</td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{formatDate(task.due_date)}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{timeAgo(task.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
