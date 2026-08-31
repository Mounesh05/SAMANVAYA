import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useAuthStore } from '../../store/useAuthStore';
import {
  DndContext,
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
import { Card } from '../../components/common/Card';
import { Select } from '../../components/common/Select';
import { StatusBadge } from '../../components/common/StatusBadge';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Button } from '../../components/common/Button';
import { Plus, GripVertical, AlertCircle } from 'lucide-react';
import { TASK_STATUS, STATUS_LABELS, DEFAULT_ORG_ID, ROLES } from '../../utils/constants';

// Sortable Task Card Component
function SortableCard({ item, onClick }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id, data: { item } });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
    backgroundColor: 'var(--bg-secondary)',
    borderRadius: 'var(--radius-md)',
    padding: '0.85rem',
    border: '1px solid var(--border-default)',
    boxShadow: 'var(--shadow-sm)',
    cursor: 'pointer',
    marginBottom: '0.65rem',
    display: 'flex',
    flexDirection: 'column',
    gap: '0.4rem',
  };

  return (
    <div ref={setNodeRef} style={style} onClick={onClick}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.5rem' }}>
        <span style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', lineHeight: '1.3' }}>
          {item.title}
        </span>
        <button
          {...attributes}
          {...listeners}
          style={{
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'grab',
            padding: '0.1rem',
          }}
        >
          <GripVertical size={16} />
        </button>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '0.35rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        <span className="font-mono">{item.id}</span>
        <span style={{ textTransform: 'capitalize', color: item.priority === 'critical' || item.priority === 'high' ? 'var(--danger)' : 'var(--text-secondary)' }}>
          {item.priority}
        </span>
      </div>

      {item.assignee_id && (
        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
          👤 {item.assignee_id}
        </div>
      )}
    </div>
  );
}

// Kanban Column Component
function KanbanColumn({ id, title, count, items = [], onItemClick }) {
  return (
    <div
      style={{
        flex: 1,
        minWidth: '260px',
        backgroundColor: 'rgba(15, 23, 42, 0.4)',
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
          padding: '0.85rem 1rem',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)' }}>
            {title}
          </span>
          <span
            style={{
              fontSize: '0.75rem',
              fontWeight: '700',
              padding: '0.1rem 0.45rem',
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
      <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
        <SortableContext items={items.map((i) => i.id)} strategy={verticalListSortingStrategy}>
          {items.map((item) => (
            <SortableCard key={item.id} item={item} onClick={() => onItemClick(item)} />
          ))}
        </SortableContext>
      </div>
    </div>
  );
}

export function BoardPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();
  const canMoveTasks = role === ROLES.DEVELOPER || role === ROLES.LEAD || role === ROLES.PM;

  const [selectedProjectId, setSelectedProjectId] = useState('');
  const [activeItem, setActiveItem] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const queryClient = useQueryClient();

  const { data: projects = [] } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
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
    if (!canMoveTasks) {
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
            />
          ))}
        </div>

        <DragOverlay>
          {activeItem ? (
            <div
              style={{
                backgroundColor: 'var(--bg-secondary)',
                borderRadius: 'var(--radius-md)',
                padding: '0.85rem',
                border: '2px solid var(--primary)',
                boxShadow: 'var(--shadow-xl)',
                width: '240px',
              }}
            >
              <div style={{ fontWeight: '700', fontSize: '0.875rem', color: 'var(--text-primary)' }}>
                {activeItem.title}
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>
    </div>
  );
}
