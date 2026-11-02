/**
 * Sprint Management page — list, create, view sprints
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, AlertCircle, Zap } from 'lucide-react';
import { sprintsApi } from '../../api/sprints.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { ProgressBar } from '../../components/common/ScoreCard';
import { formatPercent, scoreColor } from '../../utils/formatters';
import { formatDate } from '../../utils/dates';
import toast from 'react-hot-toast';

const sprintSchema = z.object({
  name: z.string().min(2, 'Sprint name required'),
  project_id: z.string().min(1, 'Project ID required'),
  goal: z.string().optional(),
  start_date: z.string().min(1, 'Start date required'),
  end_date: z.string().min(1, 'End date required'),
});

function SprintForm({ onSuccess, onCancel }) {
  const qc = useQueryClient();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(sprintSchema),
  });

  const onSubmit = async (data) => {
    try {
      await sprintsApi.create(data);
      toast.success('Sprint created');
      qc.invalidateQueries({ queryKey: ['sprints'] });
      onSuccess();
    } catch (err) {
      toast.error(err.userMessage || 'Failed to create sprint');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-group">
          <label className="form-label required" htmlFor="sp-name">Sprint Name</label>
          <input id="sp-name" className={`form-control${errors.name ? ' error' : ''}`}
            placeholder="Sprint 1" {...register('name')} />
          {errors.name && <span className="form-error"><AlertCircle size={12} />{errors.name.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="sp-proj">Project ID</label>
          <input id="sp-proj" className={`form-control${errors.project_id ? ' error' : ''}`}
            placeholder="proj-001" {...register('project_id')} />
          {errors.project_id && <span className="form-error"><AlertCircle size={12} />{errors.project_id.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="sp-goal">Sprint Goal</label>
          <textarea id="sp-goal" className="form-control" rows={2}
            placeholder="What will this sprint achieve?" {...register('goal')} />
        </div>
        <div className="grid-2">
          <div className="form-group">
            <label className="form-label required" htmlFor="sp-start">Start Date</label>
            <input id="sp-start" type="date" className={`form-control${errors.start_date ? ' error' : ''}`}
              {...register('start_date')} />
          </div>
          <div className="form-group">
            <label className="form-label required" htmlFor="sp-end">End Date</label>
            <input id="sp-end" type="date" className={`form-control${errors.end_date ? ' error' : ''}`}
              {...register('end_date')} />
          </div>
        </div>
      </div>
      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting && <span className="spinner" style={{ width: 14, height: 14 }} />}
          Create Sprint
        </button>
      </div>
    </form>
  );
}

export function SprintsPage() {
  const [createOpen, setCreateOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['sprints'],
    queryFn: () => sprintsApi.list().then(r => Array.isArray(r.data) ? r.data : r.data?.sprints || []),
  });

  const sprints = data || [];
  const active = sprints.filter(s => s.status === 'active' || s.status === 'ACTIVE');
  const past = sprints.filter(s => s.status !== 'active' && s.status !== 'ACTIVE');

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Sprints</h1>
          <p className="page-subtitle">{active.length} active · {past.length} completed</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> New Sprint
        </button>
      </div>

      {isLoading && <LoadingState message="Loading sprints…" />}
      {isError && <ErrorState description={error?.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && sprints.length === 0 && (
        <EmptyState title="No sprints" description="Create your first sprint" action={
          <button className="btn btn-primary" onClick={() => setCreateOpen(true)}><Plus size={16} /> New Sprint</button>
        } />
      )}

      {!isLoading && !isError && sprints.length > 0 && (
        <>
          {active.length > 0 && (
            <div style={{ marginBottom: 'var(--space-6)' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                Active
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {active.map(s => <SprintCard key={s._id || s.id} sprint={s} />)}
              </div>
            </div>
          )}
          {past.length > 0 && (
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 'var(--space-3)' }}>
                Past Sprints
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
                {past.map(s => <SprintCard key={s._id || s.id} sprint={s} />)}
              </div>
            </div>
          )}
        </>
      )}

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="New Sprint">
        <SprintForm onSuccess={() => setCreateOpen(false)} onCancel={() => setCreateOpen(false)} />
      </Modal>
    </div>
  );
}

function SprintCard({ sprint }) {
  const pct = sprint.completion_percentage ?? sprint.progress ?? 0;
  return (
    <div className="card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-4)' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <Zap size={16} style={{ color: 'var(--brand-400)' }} />
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{sprint.name}</span>
          </div>
          {sprint.goal && <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>{sprint.goal}</div>}
        </div>
        <StatusBadge status={sprint.status} />
      </div>

      <div style={{ marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: 6 }}>
          <span style={{ color: 'var(--text-muted)' }}>Completion</span>
          <span className={scoreColor(pct)}>{formatPercent(pct)}</span>
        </div>
        <ProgressBar value={pct} />
      </div>

      <div style={{ display: 'flex', gap: 'var(--space-6)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
        <span>Start: <strong style={{ color: 'var(--text-secondary)' }}>{formatDate(sprint.start_date)}</strong></span>
        <span>End: <strong style={{ color: 'var(--text-secondary)' }}>{formatDate(sprint.end_date)}</strong></span>
        {sprint.story_count !== undefined && <span>Stories: <strong style={{ color: 'var(--text-secondary)' }}>{sprint.story_count}</strong></span>}
      </div>
    </div>
  );
}
