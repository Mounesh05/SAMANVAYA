import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import {
  DndContext,
  useDroppable,
  closestCorners,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragOverlay,
} from '@dnd-kit/core';
import {
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { boardApi } from '../../api/board.api';
import { projectsApi } from '../../api/projects.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Select } from '../../components/common/Select';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { GripVertical, AlertCircle, User } from 'lucide-react';
import { useSessionScope } from '../../store/useSessionScope';
import { canUpdateTask, isSignOffOnly, SIGN_OFF_TARGETS } from '../../utils/taskPermissions';

// Sortable Task Card Component
function SortableCard({ item, onClick, canDrag }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id, data: { item }, disabled: !canDrag });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: 'var(--radius-md)',
    padding: '12px',
    border: '1px solid var(--border-default)',
    cursor: canDrag ? 'grab' : 'default',
    marginBottom: '8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      onClick={onClick}
      {...(canDrag ? attributes : {})}
      {...(canDrag ? listeners : {})}
      aria-label={canDrag ? `${item.title}. Drag to change status` : item.title}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)', lineHeight: '1.3' }}>
          {item.title}
        </span>
        {canDrag && (
          <GripVertical size={16} aria-hidden="true" style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
        )}
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '4px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        <span className="font-mono">{item.id}</span>
        <span style={{ textTransform: 'capitalize', color: item.priority === 'critical' || item.priority === 'high' ? 'var(--danger)' : 'var(--text-secondary)' }}>
          {item.priority}
        </span>
      </div>

      {item.assignee_id && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          <User size={16} strokeWidth={1.5} aria-hidden="true" />
          <span className="font-mono">{item.assignee_id}</span>
        </div>
      )}
    </div>
  );
}

// Kanban Column Component
function KanbanColumn({ id, title, count, items = [], onItemClick, user }) {
  // The whole column is a drop target, so a card can be dropped into an
  // empty column (previously only cards were targets, so empty columns
  // swallowed the drop and nothing was sent).
  const { setNodeRef, isOver } = useDroppable({ id });
  return (
    <div
      data-column={id}
      style={{
        flex: 1,
        minWidth: '260px',
        backgroundColor: 'var(--bg-tertiary)',
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        maxHeight: 'calc(100vh - 220px)',
      }}
    >
      {/* Column Header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-primary)' }}>
            {title}
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: '600',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-elevated)',
              color: 'var(--text-muted)',
            }}
          >
            {count}
          </span>
        </div>
      </div>

      {/* Column Items */}
      <div
        ref={setNodeRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '0.75rem',
          minHeight: '120px',
          borderRadius: '0 0 var(--radius-lg) var(--radius-lg)',
          background: isOver ? 'var(--shell-active, rgba(59, 130, 246, 0.08))' : 'transparent',
          transition: 'background-color var(--transition-fast)',
        }}
      >
        <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
          {items.map((item) => (
            <SortableCard
              key={item.id}
              item={item}
              onClick={() => onItemClick(item)}
              canDrag={canUpdateTask(user, item)}
            />
          ))}
        </SortableContext>
      </div>
    </div>
  );
}

export function BoardPage() {
  const sessionScope = useSessionScope();
  const { user } = useAuthStore();
  // Same rule as PATCH /api/boards/move.
  const canMoveTasks = hasPermission(user, PERMISSIONS.TRANSITION_TASK);

  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [activeItem, setActiveItem] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const queryClient = useQueryClient();

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'list', sessionScope],
    queryFn: () => projectsApi.list(),
  });

  const activeProjectId = selectedProjectId || projects[0]?.id || '';

  const {
    data: boardData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['board', 'project', activeProjectId],
    queryFn: () => boardApi.getProjectBoard(activeProjectId),
    enabled: !!activeProjectId,
  });

  const moveMutation = useMutation({
    mutationFn: ({ itemId, targetStatus }) =>
      boardApi.moveItem(itemId, 'task', targetStatus),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['board'] });
      setErrorMessage('');
    },
    onError: (err) => {
      setErrorMessage(err.message || 'Failed to move item according to workflow rules.');
      queryClient.invalidateQueries({ queryKey: ['board'] });
    },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates })
  );

  const handleDragStart = (event) => {
    const { active } = event;
    const item = active.data.current?.item;
    setActiveItem(item);
  };

  const handleDragEnd = (event) => {
    const { active, over } = event;
    setActiveItem(null);

    if (!over) return;
    if (!canMoveTasks || !canUpdateTask(user, active.data.current?.item)) {
      setErrorMessage('You do not have permission to move tasks on this board.');
      return;
    }

    const activeId = active.id;
    const overId = over.id;

    // Determine target column status
    let targetStatus = null;
    const taskCols = boardData?.tasks?.columns || [];

    // Did we drop directly on a column or another card?
    for (const col of taskCols) {
      if (col.id === overId || col.items.some((i) => i.id === overId)) {
        targetStatus = col.id;
        break;
      }
    }

    if (
      targetStatus
      && isSignOffOnly(user, active.data.current?.item)
      && !SIGN_OFF_TARGETS.includes(targetStatus)
    ) {
      setErrorMessage('QA sign-off can only pass a task (Done) or fail it (In Progress).');
      return;
    }

    if (targetStatus && targetStatus !== active.data.current?.item?.status) {
      moveMutation.mutate({
        itemId: activeId,
        targetStatus,
      });
    }
  };

  if (isLoading) return <LoadingState message="Loading Kanban Board..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const taskColumns = boardData?.tasks?.columns || [
    { id: 'todo', title: 'To Do', count: 0, items: [] },
    { id: 'in_progress', title: 'In Progress', count: 0, items: [] },
    { id: 'review', title: 'Review', count: 0, items: [] },
    { id: 'done', title: 'Done', count: 0, items: [] },
    { id: 'blocked', title: 'Blocked', count: 0, items: [] },
  ];

  return (
    <div>
      <PageHeader
        title="Interactive Kanban Board"
        subtitle="Drag and drop tasks across workflow states with automated workflow engine transition validation."
      />

      {/* Project Selector */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1.25rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: '600', color: 'var(--text-muted)' }}>
          Select Project:
        </span>
        <div style={{ width: '280px' }}>
          <Select
            value={activeProjectId}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            options={projects.map((p) => ({ value: p.id, label: `${p.name} (${p.id})` }))}
          />
        </div>
      </div>

      {errorMessage && (
        <div
          style={{
            padding: '0.75rem 1rem',
            backgroundColor: 'var(--danger-light)',
            border: '1px solid var(--danger-border)',
            color: 'var(--danger)',
            borderRadius: 'var(--radius-md)',
            marginBottom: '1rem',
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.875rem',
          }}
        >
          <AlertCircle size={16} />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Kanban Drag and Drop Context */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div
          style={{
            display: 'flex',
            gap: '1rem',
            overflowX: 'auto',
            paddingBottom: '1rem',
          }}
        >
          {taskColumns.map((col) => (
            <KanbanColumn
              key={col.id}
              id={col.id}
              title={col.title}
              count={col.count || col.items?.length || 0}
              items={col.items || []}
              onItemClick={() => {}}
              user={user}
            />
          ))}
        </div>

        <DragOverlay>
          {activeItem ? (
            <div
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                padding: '12px',
                border: '2px solid var(--primary)',
                boxShadow: 'var(--shadow-xl)',
                width: '240px',
              }}
            >
              <div style={{ fontWeight: '600', fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                {activeItem.title}
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
