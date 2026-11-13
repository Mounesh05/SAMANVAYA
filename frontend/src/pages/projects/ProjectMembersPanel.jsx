import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { projectsApi } from '../../api/projects.api';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { ROLE_LABELS } from '../../utils/constants';

/**
 * CR-013: who is on a project. CEO and admins change any member; a PM changes
 * the non-PM members of projects they manage. The backend enforces this and
 * says whether the viewer may manage (`can_manage`).
 */
export function ProjectMembersPanel({ projectId }) {
  const queryClient = useQueryClient();
  const [employeeId, setEmployeeId] = useState('');
  const [notice, setNotice] = useState(null);

  const membersQuery = useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => projectsApi.listMembers(projectId),
    enabled: Boolean(projectId),
  });

  const done = (text) => {
    setNotice({ tone: 'success', text });
    queryClient.invalidateQueries({ queryKey: ['project-members', projectId] });
  };
  const failed = (error) => setNotice({
    tone: 'danger', text: error?.response?.data?.detail || error?.message || 'The change could not be made',
  });

  const addMutation = useMutation({
    mutationFn: (id) => projectsApi.addMember(projectId, id),
    onSuccess: (_, id) => { setEmployeeId(''); done(`${id} added to the project.`); },
    onError: failed,
  });
  const removeMutation = useMutation({
    mutationFn: (id) => projectsApi.removeMember(projectId, id),
    onSuccess: (_, id) => done(`${id} removed from the project.`),
    onError: failed,
  });

  if (membersQuery.isLoading) return <p>Loading members...</p>;
  if (membersQuery.error) return <p role="alert">Could not load members.</p>;

  const { members = [], can_manage: canManage = false } = membersQuery.data || {};
  const columns = [
    { key: 'name', header: 'Name', render: (m) => m.name || m.employee_id },
    { key: 'employee_id', header: 'Employee ID' },
    { key: 'role', header: 'Role', render: (m) => ROLE_LABELS[m.role] || m.role },
    { key: 'link', header: 'On the project through', render: (m) => (m.link === 'assigned' ? 'Assignment' : 'Team') },
    {
      key: 'actions',
      header: '',
      render: (m) => (canManage && m.link === 'assigned' ? (
        <Button variant="ghost" size="sm" onClick={() => removeMutation.mutate(m.employee_id)}
          aria-label={`Remove ${m.name || m.employee_id} from the project`}>
          Remove
        </Button>
      ) : null),
    },
  ];

  return (
    <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      {notice && (
        <p role={notice.tone === 'danger' ? 'alert' : 'status'} style={{ color: `var(--${notice.tone})`, margin: 0 }}>
          {notice.text}
        </p>
      )}
      {canManage && (
        <form
          onSubmit={(event) => { event.preventDefault(); if (employeeId.trim()) addMutation.mutate(employeeId.trim()); }}
          style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}
        >
          <input
            aria-label="Employee ID to add"
            placeholder="Employee ID"
            value={employeeId}
            onChange={(event) => setEmployeeId(event.target.value)}
            style={{ flex: '1 1 200px', minWidth: 0, padding: '0.4rem 0.6rem' }}
          />
          <Button type="submit" variant="primary" size="sm" disabled={!employeeId.trim() || addMutation.isPending}>
            Add member
          </Button>
        </form>
      )}
      <Table columns={columns} data={members} emptyMessage="No one is on this project yet." />
    </div>
  );
}
