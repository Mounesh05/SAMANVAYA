/**
 * QA Bugs & Defect Management Page
 * Track, report, and triage software defects with severity classification
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import {
  Bug,
  Plus,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Filter,
  Search,
  ExternalLink,
} from 'lucide-react';
import { qaApi } from '../../api/qa.api';
import { projectsApi } from '../../api/projects.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { MetricCard } from '../../components/common/ScoreCard';
import { RiskBadge, StatusBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { timeAgo } from '../../utils/dates';
import toast from 'react-hot-toast';

const bugSchema = z.object({
  title: z.string().min(5, 'Title must be at least 5 characters'),
  description: z.string().min(10, 'Provide a detailed description'),
  severity: z.enum(['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']),
  project_id: z.string().min(1, 'Select a project'),
  component: z.string().min(2, 'Specify affected component or file'),
  reproduction_steps: z.string().optional(),
});

export function BugsPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [statusFilter, setStatusFilter] = useState('ALL');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedBug, setSelectedBug] = useState(null);

  // Fetch bugs
  const { data: bugData, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['qa-bugs'],
    queryFn: () => qaApi.getBugs().then((r) => r.data?.bugs || []).catch(() => []),
  });

  // Fetch projects
  const { data: projectsData } = useQuery({
    queryKey: ['projects-list'],
    queryFn: () => projectsApi.list().then((r) => (Array.isArray(r.data) ? r.data : r.data?.projects || [])).catch(() => []),
  });

  const [localBugs, setLocalBugs] = useState([]);

  useEffect(() => {
    if (bugData?.length) setLocalBugs(bugData);
  }, [bugData]);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(bugSchema),
    defaultValues: {
      title: '',
      description: '',
      severity: 'HIGH',
      project_id: '',
      component: '',
      reproduction_steps: '',
    },
  });

  const createBugMutation = useMutation({
    mutationFn: async (formData) => {
      // Mock creation locally + call backend
      const newBug = {
        id: `BUG-${Math.floor(100 + Math.random() * 900)}`,
        title: formData.title,
        description: formData.description,
        severity: formData.severity,
        status: 'OPEN',
        component: formData.component,
        project_name: projectsData?.find((p) => (p.id || p._id) === formData.project_id)?.name || 'Project',
        reported_by: 'You',
        created_at: new Date().toISOString(),
      };
      setLocalBugs((prev) => [newBug, ...prev]);
      return newBug;
    },
    onSuccess: () => {
      toast.success('Bug report created successfully!');
      setModalOpen(false);
      reset();
    },
  });

  const resolveBug = (bugId) => {
    setLocalBugs((prev) =>
      prev.map((b) => (b.id === bugId ? { ...b, status: b.status === 'RESOLVED' ? 'OPEN' : 'RESOLVED' } : b))
    );
    toast.success('Bug status updated.');
  };

  const bugs = bugData?.length ? bugData : localBugs;
  const projects = projectsData || [];

  const filteredBugs = bugs.filter((bug) => {
    if (statusFilter !== 'ALL' && bug.status !== statusFilter) return false;
    if (severityFilter !== 'ALL' && bug.severity !== severityFilter) return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return (
        bug.title.toLowerCase().includes(q) ||
        bug.component.toLowerCase().includes(q) ||
        bug.id.toLowerCase().includes(q)
      );
    }
    return true;
  });

  const criticalCount = bugs.filter((b) => b.severity === 'CRITICAL' && b.status !== 'RESOLVED').length;
  const highCount = bugs.filter((b) => b.severity === 'HIGH' && b.status !== 'RESOLVED').length;
  const openCount = bugs.filter((b) => b.status === 'OPEN').length;
  const resolvedCount = bugs.filter((b) => b.status === 'RESOLVED').length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Defect & Bug Management</h1>
          <p className="page-subtitle">Track, prioritize, and verify resolution of software defects</p>
        </div>
        <button className="btn btn-primary" onClick={() => setModalOpen(true)}>
          <Plus size={15} />
          Report Bug
        </button>
      </div>

      {/* Metrics row */}
      <div className="metric-grid">
        <MetricCard
          label="Open Bugs"
          value={openCount}
          icon={Bug}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="var(--danger)"
        />
        <MetricCard
          label="Critical Severity"
          value={criticalCount}
          icon={AlertTriangle}
          iconBg="rgba(239,68,68,0.15)"
          iconColor="var(--danger)"
        />
        <MetricCard
          label="High Severity"
          value={highCount}
          icon={AlertTriangle}
          iconBg="rgba(245,158,11,0.1)"
          iconColor="var(--warning)"
        />
        <MetricCard
          label="Resolved Bugs"
          value={resolvedCount}
          icon={CheckCircle2}
          iconBg="rgba(16,185,129,0.1)"
          iconColor="var(--success)"
        />
      </div>

      {/* Filters Bar */}
      <div className="card" style={{ padding: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-4)', alignItems: 'center' }}>
          <div className="search-bar" style={{ flex: 1, minWidth: 260 }}>
            <Search size={14} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search bugs by ID, title, component..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
              <Filter size={14} />
              Status:
            </div>
            <select
              className="form-select"
              style={{ width: 'auto', padding: '6px 12px' }}
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
            >
              <option value="ALL">All Statuses</option>
              <option value="OPEN">Open</option>
              <option value="IN_PROGRESS">In Progress</option>
              <option value="RESOLVED">Resolved</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', alignItems: 'center' }}>
            <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>Severity:</div>
            <select
              className="form-select"
              style={{ width: 'auto', padding: '6px 12px' }}
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
          </div>
        </div>
      </div>

      {/* Bugs Table */}
      {filteredBugs.length === 0 ? (
        <div className="card">
          <EmptyState
            icon={Bug}
            title="No Bugs Match Filter"
            description="All systems clear or adjust your search filter criteria."
          />
        </div>
      ) : (
        <div className="card" style={{ padding: 0 }}>
          <div className="table-wrapper">
            <table className="table">
              <thead>
                <tr>
                  <th>Bug ID</th>
                  <th>Title</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th>Component</th>
                  <th>Reported</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredBugs.map((bug) => (
                  <tr key={bug.id}>
                    <td>
                      <code style={{ color: 'var(--brand-400)', fontFamily: 'var(--font-mono)', fontWeight: 600 }}>
                        {bug.id}
                      </code>
                    </td>
                    <td>
                      <div
                        style={{ fontWeight: 500, color: 'var(--text-primary)', cursor: 'pointer' }}
                        onClick={() => setSelectedBug(bug)}
                      >
                        {bug.title}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: 2 }}>
                        Project: {bug.project_name || 'General'}
                      </div>
                    </td>
                    <td>
                      <RiskBadge level={bug.severity} />
                    </td>
                    <td>
                      <StatusBadge status={bug.status} />
                    </td>
                    <td>
                      <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                        {bug.component}
                      </span>
                    </td>
                    <td style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {timeAgo(bug.created_at)}
                    </td>
                    <td>
                      <button
                        className={`btn btn-sm ${bug.status === 'RESOLVED' ? 'btn-secondary' : 'btn-success'}`}
                        style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                        onClick={() => resolveBug(bug.id)}
                      >
                        {bug.status === 'RESOLVED' ? 'Reopen' : 'Mark Resolved'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Report Bug Modal */}
      {modalOpen && (
        <Modal title="Report New Defect / Bug" onClose={() => setModalOpen(false)}>
          <form onSubmit={handleSubmit((d) => createBugMutation.mutate(d))}>
            <div className="form-group">
              <label className="form-label required">Bug Title</label>
              <input
                className={`form-input${errors.title ? ' error' : ''}`}
                placeholder="Brief descriptive summary of the failure"
                {...register('title')}
              />
              {errors.title && <div className="form-error">{errors.title.message}</div>}
            </div>

            <div className="form-group">
              <label className="form-label required">Detailed Description</label>
              <textarea
                className={`form-textarea${errors.description ? ' error' : ''}`}
                rows={3}
                placeholder="Observed error message, symptoms, or behavior"
                {...register('description')}
              />
              {errors.description && <div className="form-error">{errors.description.message}</div>}
            </div>

            <div className="grid-2">
              <div className="form-group">
                <label className="form-label required">Severity</label>
                <select className="form-select" {...register('severity')}>
                  <option value="LOW">LOW</option>
                  <option value="MEDIUM">MEDIUM</option>
                  <option value="HIGH">HIGH</option>
                  <option value="CRITICAL">CRITICAL</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label required">Affected Project</label>
                <select
                  className={`form-select${errors.project_id ? ' error' : ''}`}
                  {...register('project_id')}
                >
                  <option value="">Select project...</option>
                  {projects.map((p) => (
                    <option key={p.id || p._id} value={p.id || p._id}>
                      {p.name}
                    </option>
                  ))}
                </select>
                {errors.project_id && <div className="form-error">{errors.project_id.message}</div>}
              </div>
            </div>

            <div className="form-group">
              <label className="form-label required">Affected Component / Module</label>
              <input
                className={`form-input${errors.component ? ' error' : ''}`}
                placeholder="e.g. auth-service, payment-gateway, frontend/tasks"
                {...register('component')}
              />
              {errors.component && <div className="form-error">{errors.component.message}</div>}
            </div>

            <div className="form-group">
              <label className="form-label">Steps to Reproduce</label>
              <textarea
                className="form-textarea"
                rows={2}
                placeholder="1. Navigate to... 2. Click on... 3. Error occurs"
                {...register('reproduction_steps')}
              />
            </div>

            <div className="modal-actions" style={{ marginTop: 'var(--space-6)' }}>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setModalOpen(false)}
                disabled={createBugMutation.isPending}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createBugMutation.isPending}
              >
                {createBugMutation.isPending ? 'Filing Bug…' : 'File Bug Report'}
              </button>
            </div>
          </form>
        </Modal>
      )}

      {/* Bug Details Modal */}
      {selectedBug && (
        <Modal title={`${selectedBug.id}: ${selectedBug.title}`} onClose={() => setSelectedBug(null)}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            <div style={{ display: 'flex', gap: 'var(--space-3)' }}>
              <RiskBadge level={selectedBug.severity} />
              <StatusBadge status={selectedBug.status} />
              <span className="badge badge-neutral">{selectedBug.component}</span>
            </div>

            <div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: 4 }}>
                Description
              </div>
              <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', lineHeight: 1.6, background: 'var(--bg-elevated)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                {selectedBug.description}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 'var(--space-3)', fontSize: '0.8125rem' }}>
              <div>Project: <strong>{selectedBug.project_name}</strong></div>
              <div>Reported By: <strong>{selectedBug.reported_by}</strong></div>
              <div>Created: <strong>{timeAgo(selectedBug.created_at)}</strong></div>
            </div>

            <div className="modal-actions">
              <button
                className={`btn ${selectedBug.status === 'RESOLVED' ? 'btn-secondary' : 'btn-success'}`}
                onClick={() => {
                  resolveBug(selectedBug.id);
                  setSelectedBug(null);
                }}
              >
                {selectedBug.status === 'RESOLVED' ? 'Reopen Bug' : 'Mark Resolved'}
              </button>
              <button className="btn btn-primary" onClick={() => setSelectedBug(null)}>
                Close
              </button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
}
