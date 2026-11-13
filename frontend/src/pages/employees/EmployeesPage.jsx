import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { employeesApi } from '../../api/employees.api';
import { teamsApi } from '../../api/teams.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { UserPlus, Edit, Trash2, ShieldCheck, ShieldOff } from 'lucide-react';
import { ROLES, ROLE_LABELS, HR_DESIGNATION_LABELS, designationLabel } from '../../utils/constants';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';

const ASSIGNABLE_ROLES = Object.keys(ROLES).filter((r) => r !== 'CEO');

export function EmployeesPage() {
  const { user } = useAuthStore();
  // CR-006: show only actions the backend accepts. Create and edit check
  // MANAGE_EMPLOYEES; deactivation is system-admin only (Decision 2).
  const canManageEmployees = hasPermission(user, PERMISSIONS.MANAGE_EMPLOYEES);
  const canDeactivate = Boolean(user?.is_admin);
  // CR-008: only admins grant or remove admin rights (the backend's existing
  // is_admin field). The backend refuses to remove the last active admin.
  const canManageAdmins = Boolean(user?.is_admin);
  const [adminError, setAdminError] = useState('');
  // CR-009: admins and HR Managers assign HR designations (never their own).
  const canAssignDesignations = hasPermission(user, PERMISSIONS.MANAGE_HR_DESIGNATIONS);
  const [search, setSearch] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editEmployee, setEditEmployee] = useState(null);
  const [deleteId, setDeleteId] = useState(null);

  // Form states
  const [formData, setFormData] = useState({
    employee_id: '',
    name: '',
    email: '',
    role: 'DEVELOPER',
    dept: 'Engineering',
    organisation_password: '',
    employee_password: '',
    team_id: '',
    github_username: '',
    designation: '',
  });

  const queryClient = useQueryClient();

  const { data: employees = [], isLoading, error, refetch } = useQuery({
    queryKey: ['employees', { role: roleFilter }],
    queryFn: () => employeesApi.list(roleFilter ? { role: roleFilter } : {}),
  });

  const { data: teams = [] } = useQuery({
    queryKey: ['teams', 'list'],
    queryFn: () => teamsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => employeesApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setIsCreateModalOpen(false);
      resetForm();
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, updates }) => employeesApi.update(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setEditEmployee(null);
      resetForm();
    },
  });

  const adminMutation = useMutation({
    mutationFn: ({ id, isAdmin }) => employeesApi.update(id, { is_admin: isAdmin }),
    onSuccess: () => {
      setAdminError('');
      queryClient.invalidateQueries({ queryKey: ['employees'] });
    },
    onError: (error) => {
      setAdminError(error?.response?.data?.detail || error?.message || 'Could not change admin rights');
    },
  });

  const adminButton = (e) => (
    canManageAdmins && e.employee_id !== user?.employee_id && (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => adminMutation.mutate({ id: e.employee_id, isAdmin: !e.is_admin })}
        title={e.is_admin ? `Remove admin rights from ${e.name}` : `Make ${e.name} an admin`}
        aria-label={e.is_admin ? `Remove admin rights from ${e.name}` : `Make ${e.name} an admin`}
      >
        {e.is_admin ? <ShieldOff size={15} style={{ color: 'var(--warning)' }} /> : <ShieldCheck size={15} />}
      </Button>
    )
  );

  const deleteMutation = useMutation({
    mutationFn: (id) => employeesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setDeleteId(null);
    },
  });

  const resetForm = () => {
    setFormData({
      employee_id: '',
      name: '',
      email: '',
      role: 'DEVELOPER',
      dept: 'Engineering',
      organisation_password: '',
      employee_password: '',
      team_id: '',
      github_username: '',
      designation: '',
    });
  };

  const canEditDesignation = canAssignDesignations && editEmployee?.employee_id !== user?.employee_id;

  const handleSave = (e) => {
    e.preventDefault();
    if (editEmployee) {
      updateMutation.mutate({
        id: editEmployee.employee_id,
        updates: {
          name: formData.name,
          email: formData.email,
          role: formData.role,
          dept: formData.dept,
          github_username: formData.github_username || null,
          // Send the designation only when this user may change it and it changed.
          ...(canEditDesignation && (formData.designation || '') !== (editEmployee.designation || '')
            ? { designation: formData.role === 'HR' ? formData.designation || null : null }
            : {}),
        },
      });
    } else {
      const { designation, ...rest } = formData;
      createMutation.mutate(
        canAssignDesignations && rest.role === 'HR' && designation ? { ...rest, designation } : rest,
      );
    }
  };

  const openEdit = (emp) => {
    if (emp.role === 'CEO') return;
    setEditEmployee(emp);
    setFormData({
      employee_id: emp.employee_id,
      name: emp.name,
      email: emp.email,
      role: emp.role,
      dept: emp.dept,
      organisation_password: '',
      employee_password: '',
      team_id: emp.team_id || '',
      github_username: emp.github_username || '',
      designation: emp.designation || '',
    });
  };

  const filteredEmployees = employees.filter(
    (e) =>
      e.name.toLowerCase().includes(search.toLowerCase()) ||
      e.email.toLowerCase().includes(search.toLowerCase()) ||
      e.employee_id.toLowerCase().includes(search.toLowerCase())
  );

  const columns = [
    { key: 'name', header: 'Name', render: (e) => <span style={{ fontWeight: '700' }}>{e.name}</span> },
    { key: 'employee_id', header: 'Employee ID', render: (e) => <span className="font-mono">{e.employee_id}</span> },
    {
      key: 'role',
      header: 'Role',
      render: (e) => (e.role === 'HR' && e.designation
        ? `${ROLE_LABELS[e.role] || e.role} · ${designationLabel(e.designation)}`
        : ROLE_LABELS[e.role] || e.role),
    },
    {
      key: 'dept',
      header: 'Department',
      render: (e) => {
        const r = e.role?.toUpperCase();
        if (r === 'CEO' && (e.dept === 'Engineering' || !e.dept)) return 'Executive';
        if (r === 'HR' && (e.dept === 'Engineering' || !e.dept)) return 'People & Culture';
        return e.dept || '—';
      },
    },
    {
      key: 'team_id',
      header: 'Team',
      render: (e) => {
        const r = e.role?.toUpperCase();
        if (r === 'CEO' || r === 'HR') return '—';
        return e.team_id || e.current_team_id || '—';
      },
    },
    { key: 'github_username', header: 'GitHub', render: (e) => e.github_username || '—' },
    {
      key: 'status',
      header: 'Status',
      render: (e) => (
        <span style={{ color: e.is_active ? 'var(--success)' : 'var(--danger)', fontWeight: '600', fontSize: '0.8125rem' }}>
          {e.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (e) => {
        const isCEO = e.role === 'CEO';
        const isSelf = e.employee_id === user?.employee_id;
        if (isCEO || isSelf) {
          return (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              {!isCEO && canManageEmployees && (
                <Button variant="ghost" size="sm" onClick={() => openEdit(e)} title="Edit Profile">
                  <Edit size={15} />
                </Button>
              )}
              {adminButton(e)}
              <span
                style={{
                  fontSize: '0.75rem',
                  color: isCEO ? 'var(--text-muted)' : 'var(--primary)',
                  padding: '0.2rem 0.5rem',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: isCEO ? 'var(--bg-tertiary)' : 'rgba(59, 130, 246, 0.08)',
                  border: isCEO ? '1px solid var(--border-subtle)' : '1px solid rgba(59, 130, 246, 0.25)',
                  fontWeight: isSelf ? '600' : 'normal',
                  fontStyle: isCEO ? 'italic' : 'normal',
                }}
              >
                {isCEO ? 'Protected' : 'You'}
              </span>
            </div>
          );
        }
        return (
          <div style={{ display: 'flex', gap: '0.35rem' }}>
            {canManageEmployees && (
              <Button variant="ghost" size="sm" onClick={() => openEdit(e)} title="Edit Employee">
                <Edit size={15} />
              </Button>
            )}
            {adminButton(e)}
            {canDeactivate && (
              <Button variant="ghost" size="sm" onClick={() => setDeleteId(e.employee_id)} title="Deactivate Employee">
                <Trash2 size={15} style={{ color: 'var(--danger)' }} />
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  if (isLoading) return <LoadingState message="Loading employees..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Employee Directory"
        subtitle="Manage company staff, role assignments, department allocation, and authentication accounts."
        actions={
          canManageEmployees && (
            <Button
              variant="primary"
              leftIcon={<UserPlus size={16} />}
              onClick={() => {
                resetForm();
                setIsCreateModalOpen(true);
              }}
            >
              Add Employee
            </Button>
          )
        }
      />

      {adminError && <p role="alert" style={{ color: 'var(--danger)' }}>{adminError}</p>}

      {/* Filters Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '1rem',
          marginBottom: '1.25rem',
        }}
      >
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by name, ID, or email..."
          width="320px"
        />

        <div style={{ display: 'flex', gap: '0.75rem', width: '220px' }}>
          <Select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value)}
            placeholder="All Roles"
            options={Object.keys(ROLES).map((r) => ({ value: r, label: ROLE_LABELS[r] || r }))}
          />
        </div>
      </div>

      {/* Employees Table */}
      <Table
        columns={columns}
        data={filteredEmployees}
        emptyMessage="No employees found matching your criteria."
      />

      {/* Create / Edit Modal */}
      <Modal
        isOpen={isCreateModalOpen || !!editEmployee}
        onClose={() => {
          setIsCreateModalOpen(false);
          setEditEmployee(null);
        }}
        title={editEmployee ? `Edit Employee — ${editEmployee.employee_id}` : 'Create New Employee'}
        subtitle="HR & Organizational Administration"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => {
                setIsCreateModalOpen(false);
                setEditEmployee(null);
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={handleSave}
              isLoading={createMutation.isPending || updateMutation.isPending}
            >
              {editEmployee ? 'Save Changes' : 'Create Employee'}
            </Button>
          </>
        }
      >
        {(createMutation.error || updateMutation.error) && (
          <div
            style={{
              padding: '0.75rem',
              borderRadius: 'var(--radius-md)',
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid var(--danger)',
              color: 'var(--danger)',
              fontSize: '0.85rem',
              marginBottom: '1rem',
            }}
          >
            {createMutation.error?.response?.data?.detail ||
              updateMutation.error?.response?.data?.detail ||
              'An error occurred while saving employee record.'}
          </div>
        )}
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Employee ID"
              value={formData.employee_id}
              onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
              placeholder="e.g. EMP001"
              disabled={!!editEmployee}
              required
            />
            <Input
              label="Full Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Full name"
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="name@organization.com"
              required
            />
            {!editEmployee && (
              <Input
                label="Organization password"
                type="password"
                value={formData.organisation_password}
                onChange={(e) => setFormData({ ...formData, organisation_password: e.target.value })}
                placeholder="At least 12 characters"
                required
              />
            )}
            {!editEmployee && (
              <Input
                label="Employee password"
                type="password"
                value={formData.employee_password}
                onChange={(e) => setFormData({ ...formData, employee_password: e.target.value })}
                placeholder="Different from organization password"
                required
              />
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Role"
              value={formData.role}
              onChange={(e) => {
                const newRole = e.target.value;
                let defaultDept = formData.dept;
                if (!editEmployee) {
                  if (newRole === 'HR') defaultDept = 'People & Culture';
                  else if (newRole === 'PM') defaultDept = 'Product';
                  else if (['DEVELOPER', 'LEAD', 'QA', 'DEVOPS'].includes(newRole)) defaultDept = 'Engineering';
                }
                setFormData({ ...formData, role: newRole, dept: defaultDept });
              }}
              options={ASSIGNABLE_ROLES.map((r) => ({ value: r, label: ROLE_LABELS[r] || r }))}
              required
            />
            <Input
              label="Department"
              value={formData.dept}
              onChange={(e) => setFormData({ ...formData, dept: e.target.value })}
              placeholder="Engineering"
              required
            />
          </div>

          {formData.role === 'HR' && (
            <Select
              label="HR designation"
              value={formData.designation}
              onChange={(e) => setFormData({ ...formData, designation: e.target.value })}
              placeholder="HR generalist (no designation)"
              options={Object.entries(HR_DESIGNATION_LABELS).map(([value, label]) => ({ value, label }))}
              disabled={editEmployee ? !canEditDesignation : !canAssignDesignations}
            />
          )}

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            {editEmployee ? (
              <div>
                <label style={{ display: 'block', fontSize: '0.8125rem', fontWeight: '600', marginBottom: '0.35rem', color: 'var(--text-secondary)' }}>
                  Assigned Team
                </label>
                <div
                  style={{
                    padding: '0.55rem 0.75rem',
                    background: 'var(--bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                    fontSize: '0.875rem',
                    color: 'var(--text-primary)',
                  }}
                >
                  {teams.find((t) => t.team_id === formData.team_id)?.name || formData.team_id || 'No team assigned'}
                </div>
                <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.25rem', display: 'block' }}>
                  Engineering team assignments require an Organizational Transfer Request.
                </span>
              </div>
            ) : (
              <Select
                label="Assigned Team"
                value={formData.team_id}
                onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
                placeholder="No team assigned"
                options={teams.map((t) => ({ value: t.team_id, label: t.name }))}
              />
            )}
            <Input
              label="GitHub Username"
              value={formData.github_username}
              onChange={(e) => setFormData({ ...formData, github_username: e.target.value })}
              placeholder="GitHub username"
            />
          </div>
        </form>
      </Modal>

      {/* Delete / Deactivate Dialog */}
      <ConfirmDialog
        isOpen={!!deleteId}
        onClose={() => setDeleteId(null)}
        onConfirm={() => deleteMutation.mutate(deleteId)}
        title="Deactivate Employee"
        message={`Are you sure you want to deactivate employee ${deleteId}? They will no longer be able to log in.`}
        isDangerous
        isLoading={deleteMutation.isPending}
      />
    </div>
  );
}
