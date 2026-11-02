/**
 * Employees Page — HR-managed employee list with create/edit
 */
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { Plus, Search, Edit2, UserX, AlertCircle } from 'lucide-react';
import { employeesApi } from '../../api/employees.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { StatusBadge, RoleBadge } from '../../components/common/Badges';
import { Modal, ConfirmDialog } from '../../components/common/Modal';
import { formatDate } from '../../utils/dates';
import toast from 'react-hot-toast';

const ROLES = ['DEVELOPER', 'LEAD', 'PM', 'QA', 'DEVOPS', 'HR', 'CEO'];

const employeeSchema = z.object({
  employee_id: z.string().min(1, 'Employee ID required'),
  name: z.string().min(2, 'Name must be at least 2 characters'),
  email: z.string().email('Invalid email'),
  role: z.enum(ROLES, { errorMap: () => ({ message: 'Select a role' }) }),
  dept: z.string().min(1, 'Department required'),
  password: z.string().min(6, 'Password must be at least 6 characters').optional().or(z.literal('')),
  github_username: z.string().optional(),
});

function EmployeeForm({ employee, onSuccess, onCancel }) {
  const qc = useQueryClient();
  const isEdit = !!employee;

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(employeeSchema),
    defaultValues: employee ? {
      employee_id: employee.employee_id,
      name: employee.name,
      email: employee.email,
      role: employee.role,
      dept: employee.dept,
      github_username: employee.github_username || '',
    } : {},
  });

  const onSubmit = async (data) => {
    try {
      if (isEdit) {
        await employeesApi.update(employee.employee_id, data);
        toast.success('Employee updated');
      } else {
        await employeesApi.create({ ...data, password: data.password || data.employee_id });
        toast.success('Employee created');
      }
      qc.invalidateQueries({ queryKey: ['employees'] });
      onSuccess();
    } catch (err) {
      toast.error(err.userMessage || 'Failed to save employee');
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-4)', marginBottom: 'var(--space-4)' }}>
        <div className="form-group">
          <label className="form-label required" htmlFor="emp-id">Employee ID</label>
          <input id="emp-id" className={`form-control${errors.employee_id ? ' error' : ''}`}
            placeholder="EMP001" {...register('employee_id')} readOnly={isEdit} />
          {errors.employee_id && <span className="form-error"><AlertCircle size={12} />{errors.employee_id.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="emp-name">Full Name</label>
          <input id="emp-name" className={`form-control${errors.name ? ' error' : ''}`}
            placeholder="Alice Smith" {...register('name')} />
          {errors.name && <span className="form-error"><AlertCircle size={12} />{errors.name.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="emp-email">Email</label>
          <input id="emp-email" type="email" className={`form-control${errors.email ? ' error' : ''}`}
            placeholder="alice@company.com" {...register('email')} />
          {errors.email && <span className="form-error"><AlertCircle size={12} />{errors.email.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="emp-role">Role</label>
          <select id="emp-role" className={`form-control${errors.role ? ' error' : ''}`} {...register('role')}>
            <option value="">Select role…</option>
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
          {errors.role && <span className="form-error"><AlertCircle size={12} />{errors.role.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label required" htmlFor="emp-dept">Department</label>
          <input id="emp-dept" className={`form-control${errors.dept ? ' error' : ''}`}
            placeholder="Engineering" {...register('dept')} />
          {errors.dept && <span className="form-error"><AlertCircle size={12} />{errors.dept.message}</span>}
        </div>
        <div className="form-group">
          <label className="form-label" htmlFor="emp-github">GitHub Username</label>
          <input id="emp-github" className="form-control"
            placeholder="alice-dev" {...register('github_username')} />
        </div>
        {!isEdit && (
          <div className="form-group" style={{ gridColumn: '1/-1' }}>
            <label className="form-label required" htmlFor="emp-pw">Password</label>
            <input id="emp-pw" type="password" className={`form-control${errors.password ? ' error' : ''}`}
              placeholder="••••••••" {...register('password')} />
            {errors.password && <span className="form-error"><AlertCircle size={12} />{errors.password.message}</span>}
          </div>
        )}
      </div>

      <div className="modal-footer">
        <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
          {isSubmitting && <span className="spinner" style={{ width: 14, height: 14 }} />}
          {isEdit ? 'Save Changes' : 'Create Employee'}
        </button>
      </div>
    </form>
  );
}

export function EmployeesPage() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [createOpen, setCreateOpen] = useState(false);
  const [editEmployee, setEditEmployee] = useState(null);
  const [deactivateTarget, setDeactivateTarget] = useState(null);

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['employees'],
    queryFn: () => employeesApi.list().then((r) => r.data),
  });

  const deactivateMutation = useMutation({
    mutationFn: (id) => employeesApi.deactivate(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['employees'] });
      toast.success('Employee deactivated');
      setDeactivateTarget(null);
    },
    onError: (err) => toast.error(err.userMessage || 'Failed to deactivate'),
  });

  const employees = Array.isArray(data) ? data : data?.employees || [];
  const filtered = employees.filter(
    (e) =>
      !search ||
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.email.toLowerCase().includes(search.toLowerCase()) ||
      e.role.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Employees</h1>
          <p className="page-subtitle">{employees.length} total employees</p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
          <Plus size={16} />
          Add Employee
        </button>
      </div>

      {/* Search */}
      <div style={{ position: 'relative', marginBottom: 'var(--space-5)', maxWidth: 400 }}>
        <Search size={16} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
        <input
          className="form-control"
          style={{ paddingLeft: 38 }}
          placeholder="Search employees…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          aria-label="Search employees"
        />
      </div>

      {isLoading && <LoadingState message="Loading employees…" />}
      {isError && <ErrorState description={error.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && filtered.length === 0 && (
        <EmptyState
          title={search ? 'No employees match your search' : 'No employees yet'}
          description={search ? 'Try a different search term' : 'Click "Add Employee" to get started'}
          action={!search && (
            <button className="btn btn-primary" onClick={() => setCreateOpen(true)}>
              <Plus size={16} /> Add Employee
            </button>
          )}
        />
      )}

      {!isLoading && !isError && filtered.length > 0 && (
        <div className="table-wrapper">
          <table className="table">
            <thead>
              <tr>
                <th>Employee</th>
                <th>Role</th>
                <th>Department</th>
                <th>GitHub</th>
                <th>Status</th>
                <th>Joined</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((emp) => (
                <tr key={emp.employee_id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <div className="avatar avatar-sm">{emp.name?.charAt(0)}</div>
                      <div>
                        <div style={{ fontWeight: 500 }}>{emp.name}</div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{emp.email}</div>
                      </div>
                    </div>
                  </td>
                  <td><RoleBadge role={emp.role} /></td>
                  <td style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{emp.dept}</td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem', fontFamily: 'var(--font-mono)' }}>
                    {emp.github_username || '—'}
                  </td>
                  <td><StatusBadge status={emp.is_active ? 'ACTIVE' : 'INACTIVE'} /></td>
                  <td style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>{formatDate(emp.created_at)}</td>
                  <td>
                    <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                      <button
                        className="btn btn-ghost btn-icon btn-sm"
                        onClick={() => setEditEmployee(emp)}
                        aria-label={`Edit ${emp.name}`}
                      >
                        <Edit2 size={14} />
                      </button>
                      {emp.is_active && (
                        <button
                          className="btn btn-ghost btn-icon btn-sm"
                          onClick={() => setDeactivateTarget(emp)}
                          aria-label={`Deactivate ${emp.name}`}
                          style={{ color: 'var(--danger)' }}
                        >
                          <UserX size={14} />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create modal */}
      <Modal
        isOpen={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Add Employee"
        size="lg"
      >
        <EmployeeForm
          onSuccess={() => setCreateOpen(false)}
          onCancel={() => setCreateOpen(false)}
        />
      </Modal>

      {/* Edit modal */}
      <Modal
        isOpen={!!editEmployee}
        onClose={() => setEditEmployee(null)}
        title="Edit Employee"
        size="lg"
      >
        {editEmployee && (
          <EmployeeForm
            employee={editEmployee}
            onSuccess={() => setEditEmployee(null)}
            onCancel={() => setEditEmployee(null)}
          />
        )}
      </Modal>

      {/* Deactivate confirm */}
      <ConfirmDialog
        isOpen={!!deactivateTarget}
        onClose={() => setDeactivateTarget(null)}
        onConfirm={() => deactivateMutation.mutate(deactivateTarget.employee_id)}
        title="Deactivate Employee"
        description={`Are you sure you want to deactivate ${deactivateTarget?.name}? They will lose access to Samanvaya.`}
        confirmLabel="Deactivate"
        loading={deactivateMutation.isPending}
      />
    </div>
  );
}
