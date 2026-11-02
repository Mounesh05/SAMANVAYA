/**
 * Feedback page — role-specific feedback submission form
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, AlertCircle, MessageSquare, CheckCircle } from 'lucide-react';
import { feedbackApi } from '../../api/feedback.api';
import { employeesApi } from '../../api/employees.api';
import { useAuth } from '../../auth/AuthContext';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, RoleBadge } from '../../components/common/Badges';
import { Modal } from '../../components/common/Modal';
import { formatDate, timeAgo } from '../../utils/dates';
import toast from 'react-hot-toast';

// Role-specific feedback criteria (4 criteria per role, 1-5 scale -> 20 Marks Superior Score)
const FEEDBACK_CATEGORIES = {
  LEAD:   ['Technical Skill', 'Code Quality', 'Mentoring', 'Technical Ownership'],
  PM:     ['Requirement Understanding', 'Delivery Reliability', 'Communication', 'Business Alignment'],
  QA:     ['Quality Focus', 'Test Coverage', 'Bug Response', 'Regression Awareness'],
  DEVOPS: ['Deployment Quality', 'CI/CD Compliance', 'Monitoring Awareness', 'Incident Response'],
  HR:     ['Collaboration', 'Professionalism', 'Communication Skills', 'Cultural Fit'],
  CEO:    ['Business Impact', 'Innovation', 'Company Alignment', 'Leadership Potential'],
};

const feedbackSchema = z.object({
  target_employee_id: z.string().min(1, 'Select an employee'),
  period: z.string().min(1, 'Enter evaluation period'),
  scores: z.record(z.coerce.number().min(1).max(5)).optional(),
  comments: z.string().min(10, 'Comments must be at least 10 characters'),
  recommendations: z.string().optional(),
});

function FeedbackForm({ onSuccess, onCancel }) {
  const { role } = useAuth();
  const qc = useQueryClient();
  const categories = FEEDBACK_CATEGORIES[role] || [];

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(feedbackSchema),
  });

  const { data: employeeData } = useQuery({
    queryKey: ['employees-list'],
    queryFn: () => employeesApi.list({ is_active: true }).then(r => Array.isArray(r.data) ? r.data : r.data?.employees || []),
  });

  const employees = employeeData || [];

  const onSubmit = async (data) => {
    try {
      await feedbackApi.submit({ ...data, evaluator_role: role });
      toast.success('Feedback submitted successfully');
      qc.invalidateQueries({ queryKey: ['feedback'] });
      onSuccess();
    } catch (err) {
      toast.error(err.userMessage || 'Failed to submit feedback');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-group">
          <label className="form-label required" htmlFor="fb-target">Employee</label>
          <select id="fb-target" className={`form-control${errors.target_employee_id ? ' error' : ''}`}
            {...register('target_employee_id')}>
            <option value="">Select employee…</option>
            {employees.map(e => (
              <option key={e.employee_id} value={e.employee_id}>{e.name} ({e.role})</option>
            ))}
          </select>
          {errors.target_employee_id && <span className="form-error"><AlertCircle size={12} />{errors.target_employee_id.message}</span>}
        </div>

        <div className="form-group">
          <label className="form-label required" htmlFor="fb-period">Evaluation Period</label>
          <input id="fb-period" className={`form-control${errors.period ? ' error' : ''}`}
            placeholder="e.g. 2026-Q3" {...register('period')} />
          {errors.period && <span className="form-error"><AlertCircle size={12} />{errors.period.message}</span>}
        </div>

        {/* Category scores */}
        {categories.length > 0 && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-2)' }}>
              <div className="form-label" style={{ margin: 0 }}>Superior Evaluation Criteria (1–5 Scale)</div>
              <span className="badge badge-primary" style={{ fontSize: '0.6875rem' }}>Contributes 20 Marks</span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 'var(--space-3)' }}>
              Ratings (1 = Needs Growth, 5 = Exemplary) across these 4 criteria determine the employee's <strong>20 Marks Superior Score</strong>.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)' }}>
              {categories.map(cat => (
                <div key={cat} className="form-group">
                  <label className="form-label" htmlFor={`score-${cat}`} style={{ fontSize: '0.75rem' }}>{cat}</label>
                  <input id={`score-${cat}`} type="number" min={1} max={5} className="form-control"
                    placeholder="1–5" {...register(`scores.${cat}`)} />
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="form-group">
          <label className="form-label required" htmlFor="fb-comments">Comments</label>
          <textarea id="fb-comments" className={`form-control${errors.comments ? ' error' : ''}`}
            rows={4} placeholder="Provide detailed feedback…" {...register('comments')} />
          {errors.comments && <span className="form-error"><AlertCircle size={12} />{errors.comments.message}</span>}
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="fb-recs">Recommendations</label>
          <textarea id="fb-recs" className="form-control" rows={2}
            placeholder="Development recommendations…" {...register('recommendations')} />
        </div>
      </div>

      <div style={{ padding: '10px 14px', background: 'var(--warning-bg)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 'var(--radius-md)', marginBottom: 'var(--space-4)', fontSize: '0.8125rem', color: 'var(--warning)' }}>
        ⚠ Once submitted, feedback cannot be casually edited. Please review carefully.
      </div>

      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting && <span className="spinner" style={{ width: 14, height: 14 }} />}
          Submit Feedback
        </button>
      </div>
    </form>
  );
}

export function FeedbackPage() {
  const { role } = useAuth();
  const [formOpen, setFormOpen] = useState(false);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['feedback', role],
    queryFn: () => feedbackApi.list({ evaluator_role: role }).then(r => Array.isArray(r.data) ? r.data : r.data?.feedback || []),
  });

  const submissions = data || [];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Feedback</h1>
          <p className="page-subtitle">{role} feedback · {submissions.length} submitted</p>
        </div>
        <button className="btn btn-primary" onClick={() => setFormOpen(true)}>
          <Plus size={16} /> Submit Feedback
        </button>
      </div>

      {isLoading && <LoadingState message="Loading feedback…" />}
      {isError && <ErrorState description={error?.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && submissions.length === 0 && (
        <EmptyState
          title="No feedback submitted yet"
          description="Submit your first feedback evaluation below"
          action={
            <button className="btn btn-primary" onClick={() => setFormOpen(true)}>
              <MessageSquare size={16} /> Submit Feedback
            </button>
          }
        />
      )}

      {!isLoading && !isError && submissions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {submissions.map((fb, i) => (
            <div key={fb._id || i} className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 'var(--space-3)' }}>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {fb.target_employee_name || fb.target_employee_id}
                  </div>
                  <div style={{ display: 'flex', gap: 'var(--space-2)', alignItems: 'center' }}>
                    <span className="badge badge-neutral">{fb.period}</span>
                    <RoleBadge role={fb.evaluator_role || role} />
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--success)', fontSize: '0.8125rem', marginBottom: 2 }}>
                    <CheckCircle size={14} />
                    Submitted
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {timeAgo(fb.submitted_at || fb.created_at)}
                  </div>
                </div>
              </div>

              {fb.comments && (
                <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: 1.6, borderLeft: '3px solid var(--border)', paddingLeft: 12 }}>
                  {fb.comments}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={formOpen} onClose={() => setFormOpen(false)} title="Submit Feedback" size="lg">
        <FeedbackForm onSuccess={() => setFormOpen(false)} onCancel={() => setFormOpen(false)} />
      </Modal>
    </div>
  );
}
