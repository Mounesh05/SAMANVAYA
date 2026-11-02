/**
 * BoardPage — Kanban board with @dnd-kit drag & drop
 * Optimistic UI + rollback on failure
 */
import { useState, useCallback } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
} from '@dnd-kit/core';
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical } from 'lucide-react';
import { tasksApi } from '../../api/tasks.api';
import { boardApi } from '../../api/board.api';
import { LoadingState, ErrorState } from '../../components/common/States';
import { PriorityBadge } from '../../components/common/Badges';
import toast from 'react-hot-toast';

const COLUMNS = [
  { id: 'TODO',        label: 'To Do' },
  { id: 'IN_PROGRESS', label: 'In Progress' },
  { id: 'REVIEW',      label: 'Review' },
  { id: 'DONE',        label: 'Done' },
];

const COL_COLORS = {
  TODO: 'var(--text-muted)',
  IN_PROGRESS: 'var(--info)',
  REVIEW: 'var(--warning)',
  DONE: 'var(--success)',
};

function TaskCard({ task, isDragging }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: task._id || task.id });
  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  return (
    <div ref={setNodeRef} style={style} className="kanban-card" aria-roledescription="draggable task">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <button
          {...attributes}
          {...listeners}
          style={{ color: 'var(--text-muted)', cursor: 'grab', flexShrink: 0, marginTop: 2, background: 'none', border: 'none', padding: 0 }}
          aria-label={`Drag task: ${task.title}`}
        >
          <GripVertical size={14} />
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '0.8125rem', fontWeight: 500, color: 'var(--text-primary)', marginBottom: 4 }}>
            {task.title}
          </div>
          <PriorityBadge priority={task.priority} />
        </div>
      </div>
      {task.assignee_name && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4 }}>
          <div className="avatar avatar-sm">{task.assignee_name.charAt(0)}</div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{task.assignee_name}</span>
        </div>
      )}
    </div>
  );
}

export function BoardPage() {
  const qc = useQueryClient();
  const [activeId, setActiveId] = useState(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['board-tasks'],
    queryFn: () => tasksApi.list().then((r) => {
      const raw = Array.isArray(r.data) ? r.data : r.data?.tasks || [];
      return raw;
    }),
  });

  const moveMutation = useMutation({
    mutationFn: ({ taskId, newStatus }) => boardApi.moveTask(taskId, newStatus),
    onError: (err, variables, ctx) => {
      qc.setQueryData(['board-tasks'], ctx.previous);
      toast.error('Failed to move task. Change reverted.');
    },
  });

  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: { distance: 8 } }));

  const tasks = data || [];

  const tasksByColumn = COLUMNS.reduce((acc, col) => {
    acc[col.id] = tasks.filter((t) => t.status === col.id);
    return acc;
  }, {});

  const handleDragStart = ({ active }) => setActiveId(active.id);

  const handleDragEnd = useCallback(({ active, over }) => {
    setActiveId(null);
    if (!over) return;

    const task = tasks.find((t) => (t._id || t.id) === active.id);
    if (!task) return;

    // Determine target column
    const targetColId = COLUMNS.find((c) => c.id === over.id)?.id ||
      tasks.find((t) => (t._id || t.id) === over.id)?.status;

    if (!targetColId || task.status === targetColId) return;

    // Optimistic update
    const previous = qc.getQueryData(['board-tasks']);
    qc.setQueryData(['board-tasks'], (old) =>
      (old || []).map((t) =>
        (t._id || t.id) === task._id || t.id === task._id
          ? { ...t, status: targetColId }
          : t
      )
    );

    moveMutation.mutate(
      { taskId: task._id || task.id, newStatus: targetColId },
      { onError: (err, vars, ctx) => { qc.setQueryData(['board-tasks'], previous); } }
    );
  }, [tasks, qc, moveMutation]);

  if (isLoading) return <LoadingState message="Loading board…" />;
  if (isError) return <ErrorState description={error.userMessage} onRetry={refetch} />;

  const activeTask = activeId ? tasks.find((t) => (t._id || t.id) === activeId) : null;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Kanban Board</h1>
          <p className="page-subtitle">{tasks.length} tasks</p>
        </div>
      </div>

      <DndContext sensors={sensors} collisionDetection={closestCorners} onDragStart={handleDragStart} onDragEnd={handleDragEnd}>
        <div className="kanban-board">
          {COLUMNS.map((col) => {
            const colTasks = tasksByColumn[col.id];
            return (
              <div key={col.id} className="kanban-column">
                <div className="kanban-col-header">
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: COL_COLORS[col.id] }} />
                    <span className="kanban-col-title">{col.label}</span>
                  </div>
                  <span className="kanban-col-count">{colTasks.length}</span>
                </div>

                <SortableContext
                  id={col.id}
                  items={colTasks.map((t) => t._id || t.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="kanban-cards">
                    {colTasks.map((task) => (
                      <TaskCard
                        key={task._id || task.id}
                        task={task}
                        isDragging={(task._id || task.id) === activeId}
                      />
                    ))}
                  </div>
                </SortableContext>
              </div>
            );
          })}
        </div>

        <DragOverlay>
          {activeTask ? (
            <div className="kanban-card" style={{ boxShadow: 'var(--shadow-lg)', opacity: 0.9 }}>
              <div style={{ fontSize: '0.8125rem', fontWeight: 500 }}>{activeTask.title}</div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
