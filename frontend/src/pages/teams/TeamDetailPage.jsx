import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { teamsApi } from '../../api/teams.api';
import { employeesApi } from '../../api/employees.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Select } from '../../components/common/Select';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Users, UserCheck, ArrowLeft, MessageSquareQuote, Award, UserPlus } from 'lucide-react';
import { ROLE_LABELS } from '../../utils/constants';
import { useAuthStore } from '../../store/useAuthStore';
import { canOpenPage } from '../../routes/access';
import {
  hasPermission,
  hasAnyPermission,
  FEEDBACK_SUBMIT_PERMISSIONS,
  PERMISSIONS,
} from '../../auth/permissions';

// CEO and HR work across the organisation and are not placed in a team.
const ORG_WIDE_ROLES = new Set(['CEO', 'HR']);

export function TeamDetailPage() {
  const { teamId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuthStore();
  // Only show actions the backend will accept for this user.
  const canViewMemberPerformance = hasAnyPermission(user, [
    PERMISSIONS.VIEW_TEAM_PERFORMANCE,
    PERMISSIONS.VIEW_ORGANIZATION_PERFORMANCE,
    PERMISSIONS.VIEW_PERFORMANCE_OUTCOMES,
  ]);
  const canSubmitFeedback = hasAnyPermission(user, FEEDBACK_SUBMIT_PERMISSIONS);
  const canListTeams = canOpenPage(user, 'teams');
  // The backend places employees in a team only for ASSIGN_PROJECT holders (admins).
  const canAddMembers = hasPermission(user, PERMISSIONS.ASSIGN_PROJECT);
  const queryClient = useQueryClient();
  const [isAddOpen, setIsAddOpen] = useState(false);
  const [newMemberId, setNewMemberId] = useState('');

  const {
    data: team,
    isLoading: isTeamLoading,
    error: teamError,
  } = useQuery({
    queryKey: ['team', teamId],
    queryFn: () => teamsApi.getById(teamId),
  });

  const {
    data: members = [],
    isLoading: isMembersLoading,
  } = useQuery({
    queryKey: ['team', teamId, 'members'],
    queryFn: () => teamsApi.getMembers(teamId),
    enabled: !!teamId,
  });

  // Only people without a team are offered: moving someone from another team
  // goes through a transfer request. CEO and HR work org-wide, not in a team.
  const { data: employees = [], isLoading: isEmployeesLoading } = useQuery({
    queryKey: ['employees', { is_active: true }],
    queryFn: () => employeesApi.list({ is_active: true }),
    enabled: canAddMembers && isAddOpen,
  });
  const candidates = employees.filter(
    (e) => e.is_active !== false && !e.team_id && !ORG_WIDE_ROLES.has(e.role),
  );

  const addMember = useMutation({
    mutationFn: (employeeId) => teamsApi.addMember(teamId, employeeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['team', teamId] });
      queryClient.invalidateQueries({ queryKey: ['employees'] });
      setNewMemberId('');
      setIsAddOpen(false);
    },
  });

  const closeAdd = () => {
    setIsAddOpen(false);
    setNewMemberId('');
    addMember.reset();
  };

  if (isTeamLoading || isMembersLoading) return <LoadingState message="Loading team details..." />;
  if (teamError) return <ErrorState message={teamError.message} onRetry={() => window.location.reload()} />;

  const memberColumns = [
    { key: 'name', header: 'Engineer Name', render: (m) => <span style={{ fontWeight: '700' }}>{m.name}</span> },
    { key: 'employee_id', header: 'Employee ID', render: (m) => <span className="font-mono">{m.employee_id}</span> },
    { key: 'role', header: 'Role', render: (m) => ROLE_LABELS[m.role] || m.role },
    { key: 'email', header: 'Email', render: (m) => <span style={{ color: 'var(--text-muted)' }}>{m.email}</span> },
    {
      key: 'lead_badge',
      header: 'Designation',
      render: (m) =>
        m.is_team_lead ? (
          <span
            style={{
              padding: '0.2rem 0.6rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--purple-light)',
              color: 'var(--purple)',
              fontWeight: '700',
              fontSize: '0.725rem',
            }}
          >
            Team Lead
          </span>
        ) : (
          <span style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>Member</span>
        ),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (m) => (
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/performance?developer=${m.employee_id}`)}
          >
            <Award size={14} /> Performance
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div>
      {canListTeams && (
        <div style={{ marginBottom: '1rem' }}>
          <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/teams')}>
            Back to Teams
          </Button>
        </div>
      )}

      <PageHeader
        title={team?.name || 'Team Details'}
        subtitle={team?.description || `Team ID: ${team?.team_id}`}
        actions={
          canSubmitFeedback && (
            <Button
              variant="primary"
              leftIcon={<MessageSquareQuote size={16} />}
              onClick={() => navigate('/feedback')}
            >
              Submit Feedback
            </Button>
          )
        }
      />

      {/* Team Info Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Team Lead</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem' }}>
            <UserCheck size={18} style={{ color: 'var(--purple)' }} />
            <strong style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
              {team?.team_lead_name || 'Unassigned'}
            </strong>
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Engineers</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem' }}>
            <Users size={18} style={{ color: 'var(--cyan)' }} />
            <strong style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
              {members.length} members
            </strong>
          </div>
        </Card>

        <Card padding="md">
          <span style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-muted)' }}>Assigned Projects</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem' }}>
            <strong style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>
              {team?.project_ids?.length || 0} active
            </strong>
          </div>
        </Card>
      </div>

      {/* Team Members Table */}
      <Card
        title="Team members"
        action={canAddMembers && (
          <Button variant="primary" size="sm" leftIcon={<UserPlus size={14} />} onClick={() => setIsAddOpen(true)}>
            Add member
          </Button>
        )}
      >
        <Table
          columns={canViewMemberPerformance ? memberColumns : memberColumns.filter((column) => column.key !== 'actions')}
          data={members} emptyMessage="No members assigned to this team." />
      </Card>

      <Modal
        isOpen={isAddOpen}
        onClose={closeAdd}
        title="Add team member"
        subtitle={team?.name}
        footer={
          <>
            <Button variant="secondary" onClick={closeAdd}>Cancel</Button>
            <Button
              variant="primary"
              onClick={() => addMember.mutate(newMemberId)}
              disabled={!newMemberId}
              isLoading={addMember.isPending}
            >
              Add to team
            </Button>
          </>
        }
      >
        {isEmployeesLoading ? (
          <LoadingState message="Loading employees..." />
        ) : candidates.length === 0 ? (
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
            Everyone is already in a team. Use a transfer request to move someone between teams.
          </p>
        ) : (
          <Select
            label="Employee"
            value={newMemberId}
            onChange={(e) => setNewMemberId(e.target.value)}
            placeholder="Select an employee"
            options={candidates.map((e) => ({
              value: e.employee_id,
              label: `${e.name.trim()} · ${e.employee_id} · ${ROLE_LABELS[e.role] || e.role}`,
            }))}
          />
        )}
        <p style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.75rem' }}>
          Only employees without a team are listed.
        </p>
        {addMember.error && (
          <p role="alert" style={{ fontSize: '0.8125rem', color: 'var(--danger)', marginTop: '0.5rem' }}>
            {addMember.error.message}
          </p>
        )}
      </Modal>
    </div>
  );
}
