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
import { UserPlus, Edit, Trash2, Users, Shield } from 'lucide-react';
import { ROLES, ROLE_LABELS } from '../../utils/constants';

export function EmployeesPage() {
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
    password: '',
    team_id: '',
    github_username: '',
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
      password: '',
      team_id: '',
      github_username: '',
    });
  };

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
          team_id: formData.team_id || null,
          github_username: formData.github_username || null,
        },
      });
    } else {
      createMutation.mutate(formData);
    }
  };

  const openEdit = (emp) => {
    setEditEmployee(emp);
    setFormData({
      employee_id: emp.employee_id,
      name: emp.name,
      email: emp.email,
      role: emp.role,
      dept: emp.dept,
      password: '',
      team_id: emp.team_id || '',
      github_username: emp.github_username || '',
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
    { key: 'role', header: 'Role', render: (e) => ROLE_LABELS[e.role] || e.role },
    { key: 'dept', header: 'Department', render: (e) => e.dept },
    { key: 'team_id', header: 'Team', render: (e) => e.team_id || '—' },
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
      render: (e) => (
        <div style={{ display: 'flex', gap: '0.35rem' }}>
          <Button variant="ghost" size="sm" onClick={() => openEdit(e)}>
            <Edit size={15} />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setDeleteId(e.employee_id)}>
            <Trash2 size={15} style={{ color: 'var(--danger)' }} />
          </Button>
        </div>
      ),
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
        }
      />

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
        <form onSubmit={handleSave} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Employee ID"
              value={formData.employee_id}
              onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
              placeholder="e.g. E001"
              disabled={!!editEmployee}
              required
            />
            <Input
              label="Full Name"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="John Doe"
              required
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Email"
              type="email"
              value={formData.email}
              onChange={(e) => setFormData({ ...formData, email: e.target.value })}
              placeholder="name@company.com"
              required
            />
            {!editEmployee && (
              <Input
                label="Password"
                type="password"
                value={formData.password}
                onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                placeholder="Initial password"
                required
              />
            )}
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Role"
              value={formData.role}
              onChange={(e) => setFormData({ ...formData, role: e.target.value })}
              options={Object.keys(ROLES).map((r) => ({ value: r, label: ROLE_LABELS[r] || r }))}
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

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Assigned Team"
              value={formData.team_id}
              onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
              placeholder="No team assigned"
              options={teams.map((t) => ({ value: t.team_id, label: t.name }))}
            />
            <Input
              label="GitHub Username"
              value={formData.github_username}
              onChange={(e) => setFormData({ ...formData, github_username: e.target.value })}
              placeholder="e.g. octocat"
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
