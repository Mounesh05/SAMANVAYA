import React from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { teamsApi } from '../../api/teams.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Users, Building2, UserCheck, ArrowLeft, MessageSquareQuote, Award } from 'lucide-react';
import { ROLE_LABELS } from '../../utils/constants';

export function TeamDetailPage() {
  const { teamId } = useParams();
  const navigate = useNavigate();

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
      <div style={{ marginBottom: '1rem' }}>
        <Button variant="ghost" size="sm" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/teams')}>
          Back to Teams
        </Button>
      </div>

      <PageHeader
        title={team?.name || 'Team Details'}
        subtitle={team?.description || `Team ID: ${team?.team_id}`}
        actions={
          <Button
            variant="primary"
            leftIcon={<MessageSquareQuote size={16} />}
            onClick={() => navigate('/feedback')}
          >
            Submit Feedback
          </Button>
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
      <Card title="Team Members" subtitle="Engineers currently assigned to this team unit">
        <Table columns={memberColumns} data={members} emptyMessage="No members assigned to this team." />
      </Card>
    </div>
  );
}
