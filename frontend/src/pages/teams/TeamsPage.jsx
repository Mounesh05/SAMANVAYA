import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { teamsApi } from '../../api/teams.api';
import { employeesApi } from '../../api/employees.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Users, Building2, UserCheck, FolderGit2, Plus, ArrowRight } from 'lucide-react';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';

export function TeamsPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    team_id: '',
    name: '',
    description: '',
    team_lead_id: '',
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: teams = [], isLoading, error, refetch } = useQuery({
    queryKey: ['teams', 'list'],
    queryFn: () => teamsApi.list(),
  });

  const { data: employees = [] } = useQuery({
    queryKey: ['employees', 'leads'],
    queryFn: () => employeesApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => teamsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['teams'] });
      setIsCreateModalOpen(false);
      setFormData({ team_id: '', name: '', description: '', team_lead_id: '' });
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    createMutation.mutate({
      ...formData,
      team_lead_id: formData.team_lead_id || null,
    });
  };

  if (isLoading) return <LoadingState message="Loading engineering teams..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Engineering Teams"
        subtitle="Manage development teams, assign Team Leads, and organize project allocations."
        actions={
          <PermissionGuard permission={PERMISSIONS.CREATE_TEAM}>
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              Create Team
            </Button>
          </PermissionGuard>
        }
      />

      {/* Teams Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {teams.map((team) => (
          <Card
            key={team.team_id}
            padding="lg"
            onClick={() => navigate(`/teams/${team.team_id}`)}
            style={{ cursor: 'pointer', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <div
                  style={{
                    width: '42px',
                    height: '42px',
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--primary-light)',
                    color: 'var(--primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Building2 size={22} />
                </div>
                <span
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: '700',
                    color: 'var(--text-muted)',
                    fontFamily: 'var(--font-mono)',
                  }}
                >
                  {team.team_id}
                </span>
              </div>

              <h3 style={{ fontSize: '1.15rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                {team.name}
              </h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.35rem', lineHeight: '1.4' }}>
                {team.description || 'No description provided.'}
              </p>

              <div style={{ marginTop: '1.25rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <UserCheck size={15} style={{ color: 'var(--purple)' }} />
                  <span>Lead: <strong style={{ color: 'var(--text-primary)' }}>{team.team_lead_name || 'Unassigned'}</strong></span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <Users size={15} style={{ color: 'var(--cyan)' }} />
                  <span>Members: <strong style={{ color: 'var(--text-primary)' }}>{team.member_count || 0} engineers</strong></span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                  <FolderGit2 size={15} style={{ color: 'var(--primary)' }} />
                  <span>Projects: <strong style={{ color: 'var(--text-primary)' }}>{team.project_ids?.length || 0}</strong></span>
                </div>
              </div>
            </div>

            <div style={{ marginTop: '1.25rem', display: 'flex', justifyContent: 'flex-end' }}>
              <span style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                View Team Details <ArrowRight size={14} />
              </span>
            </div>
          </Card>
        ))}
      </div>

      {/* Create Team Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create Engineering Team"
        subtitle="Organize staff and assign leadership"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} isLoading={createMutation.isPending}>
              Create Team
            </Button>
          </>
        }
      >
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Team ID"
            value={formData.team_id}
            onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
            placeholder="e.g. TEAM001 or BACKEND-TEAM"
            required
          />
          <Input
            label="Team Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g. Core Services & Platform"
            required
          />
          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Focus area and technical responsibilities"
          />
          <Select
            label="Assign Team Lead"
            value={formData.team_lead_id}
            onChange={(e) => setFormData({ ...formData, team_lead_id: e.target.value })}
            placeholder="Select a Team Lead"
            options={employees.map((e) => ({
              value: e.employee_id,
              label: `${e.name} (${e.role}) - ${e.employee_id}`,
            }))}
          />
        </form>
      </Modal>
    </div>
  );
}
