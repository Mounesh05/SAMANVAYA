/**
 * PM Projects page — list + create projects, project health
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, AlertCircle, ExternalLink } from 'lucide-react';
import { projectsApi } from '../../api/projects.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { ProgressBar } from '../../components/common/ScoreCard';
import { formatPercent, scoreColor } from '../../utils/formatters';
import { formatDate } from '../../utils/dates';
import toast from 'react-hot-toast';

const projectSchema = z.object({
  name: z.string().min(2, 'Project name must be at least 2 characters'),
  description: z.string().optional(),
  org_id: z.string().min(1, 'Organisation ID is required'),
  team_id: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  github_repos: z.string().optional(),
});

function ProjectForm({ onSuccess, onCancel }) {
  const qc = useQueryClient();
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(projectSchema),
  });

  const onSubmit = async (data) => {
    try {
      const payload = {
        ...data,
        github_repos: data.github_repos ? data.github_repos.split(',').map(s => s.trim()).filter(Boolean) : [],
      };
      await projectsApi.create(payload);
      toast.success('Project created');
      qc.invalidateQueries({ queryKey: ['pm-projects'] });
      onSuccess();
    } catch (err) {
      toast.error(err.userMessage || 'Failed to create project');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-group">
          <label className="form-label required" htmlFor="proj-name">Project Name</label>
          <input id="proj-name" className={`form-control${errors.name ? ' error' : ''}`}
            placeholder="e.g. Payment Gateway v2" {...register('name')} />
          {errors.name && <span className="form-error"><AlertCircle size={12} />{errors.name.message}</span>}
        </div>

        <div className="form-group">
          <label className="form-label required" htmlFor="proj-org">Organisation ID</label>
          <input id="proj-org" className={`form-control${errors.org_id ? ' error' : ''}`}
            placeholder="org-001" {...register('org_id')} />
          {errors.org_id && <span className="form-error"><AlertCircle size={12} />{errors.org_id.message}</span>}
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="proj-desc">Description</label>
          <textarea id="proj-desc" className="form-control" rows={3}
            placeholder="Project description…" {...register('description')} />
        </div>

        <div className="grid-2">
          <div className="form-group">
            <label className="form-label" htmlFor="proj-start">Start Date</label>
            <input id="proj-start" type="date" className="form-control" {...register('start_date')} />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="proj-end">End Date</label>
            <input id="proj-end" type="date" className="form-control" {...register('end_date')} />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="proj-repos">GitHub Repos (comma-separated)</label>
          <input id="proj-repos" className="form-control"
            placeholder="owner/repo1, owner/repo2" {...register('github_repos')} />
        </div>
      </div>

      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting && <span className="spinner" style={{ width: 14, height: 14 }} />}
          Create Project
        </button>
      </div>
    </form>
  );
}

export function PMProjectsPage() {
  const [createOpen, setCreateOpen] = useState(false);

  // PM projects come from role endpoint or general project list
  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['pm-projects'],
    queryFn: () => projectsApi.list().then(r => Array.isArray(r.data) ? r.data : r.data?.projects || []),
  });

  const projects = data || [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-subtitle">{projects.length} project{projects.length !== 1 ? 's' : ''}</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} /> New Project
        </button>
      </div>

      {isLoading && <LoadingState message="Loading projects…" />}
      {isError && <ErrorState description={error?.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && projects.length === 0 && (
        <EmptyState
          title="No projects yet"
          description="Create your first project to get started"
          action={
            <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> New Project
            </button>
          }
        />
      )}

      {!isLoading && !isError && projects.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: 'var(--space-4)' }}>
          {projects.map((proj) => (
            <div key={proj._id || proj.id || proj.project_id} className="card">
              <div className="card-header" style={{ marginBottom: 'var(--space-3)' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="card-title" style={{ marginBottom: 4 }}>{proj.name}</div>
                  <StatusBadge status={proj.status || 'ACTIVE'} />
                </div>
                <ExternalLink size={16} style={{ color: 'var(--text-muted)', flexShrink: 0 }} />
              </div>

              {proj.description && (
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)', lineHeight: 1.5, display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>
                  {proj.description}
                </p>
              )}

              {proj.completion_percentage !== undefined && (
                <div style={{ marginBottom: 'var(--space-4)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', marginBottom: 6 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Completion</span>
                    <span className={scoreColor(proj.completion_percentage)}>{formatPercent(proj.completion_percentage)}</span>
                  </div>
                  <ProgressBar value={proj.completion_percentage} />
                </div>
              )}

              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Start: {formatDate(proj.start_date) || '—'}</span>
                <span>End: {formatDate(proj.end_date) || '—'}</span>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="New Project" size="lg">
        <ProjectForm onSuccess={() => setCreateOpen(false)} onCancel={() => setCreateOpen(false)} />
      </Modal>
    </div>
  );
}
