import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { projectsApi } from '../../api/projects.api';
import { teamsApi } from '../../api/teams.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { Modal } from '../../components/common/Modal';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { StatusBadge } from '../../components/common/StatusBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { FolderGit2, Plus, ArrowRight, Calendar, Building2 } from 'lucide-react';
import { formatDate } from '../../utils/dates';
import { DEFAULT_ORG_ID } from '../../utils/constants';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';

export function ProjectsPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    org_id: DEFAULT_ORG_ID,
    team_id: '',
    start_date: '',
    end_date: '',
    main_module: '',
  });

  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data: projects = [], isLoading, error, refetch } = useQuery({
    queryKey: ['projects', 'list'],
    queryFn: () => projectsApi.list(DEFAULT_ORG_ID),
  });

  const { data: teams = [] } = useQuery({
    queryKey: ['teams', 'list'],
    queryFn: () => teamsApi.list(),
  });

  const createMutation = useMutation({
    mutationFn: (data) => projectsApi.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setIsCreateModalOpen(false);
      setFormData({
        name: '',
        description: '',
        org_id: DEFAULT_ORG_ID,
        team_id: '',
        start_date: '',
        end_date: '',
        main_module: '',
      });
    },
  });

  const handleCreate = (e) => {
    e.preventDefault();
    createMutation.mutate({
      ...formData,
      team_id: formData.team_id || null,
      start_date: formData.start_date || null,
      end_date: formData.end_date || null,
      main_module: formData.main_module || null,
    });
  };

  if (isLoading) return <LoadingState message="Loading projects..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const columns = [
    { key: 'name', header: 'Project Name', render: (p) => <span style={{ fontWeight: '700' }}>{p.name}</span> },
    { key: 'id', header: 'Project ID', render: (p) => <span className="font-mono">{p.id}</span> },
    { key: 'team_id', header: 'Team', render: (p) => p.team_id || 'Unassigned' },
    { key: 'status', header: 'Status', render: (p) => <StatusBadge status={p.status} /> },
    { key: 'start_date', header: 'Start Date', render: (p) => formatDate(p.start_date) },
    { key: 'end_date', header: 'Target Completion', render: (p) => formatDate(p.end_date) },
    {
      key: 'actions',
      header: 'Actions',
      render: (p) => (
        <Button variant="secondary" size="sm" onClick={() => navigate(`/projects/${p.id}`)}>
          Details <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Project Management"
        subtitle="Manage software delivery projects, team alignments, sprint execution, and health analytics."
        actions={
          <PermissionGuard permission={PERMISSIONS.CREATE_PROJECT}>
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => setIsCreateModalOpen(true)}
            >
              Create Project
            </Button>
          </PermissionGuard>
        }
      />

      <Table
        columns={columns}
        data={projects}
        emptyMessage="No active projects found. Click 'Create Project' to start."
        onRowClick={(p) => navigate(`/projects/${p.id}`)}
      />

      {/* Create Project Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Project"
        subtitle="PM & Executive Project Definition"
        footer={
          <>
            <Button variant="secondary" onClick={() => setIsCreateModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate} isLoading={createMutation.isPending}>
              Create Project
            </Button>
          </>
        }
      >
        <form onSubmit={handleCreate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <Input
            label="Project Name"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g. Mobile App Redesign"
            required
          />

          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Objectives and scope"
          />

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Select
              label="Assigned Team"
              value={formData.team_id}
              onChange={(e) => setFormData({ ...formData, team_id: e.target.value })}
              placeholder="Select Team"
              options={teams.map((t) => ({ value: t.team_id, label: t.name }))}
            />
            <Input
              label="Main Module"
              value={formData.main_module}
              onChange={(e) => setFormData({ ...formData, main_module: e.target.value })}
              placeholder="e.g. mobile-app"
            />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <Input
              label="Start Date"
              type="date"
              value={formData.start_date}
              onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
            />
            <Input
              label="End Date"
              type="date"
              value={formData.end_date}
              onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
            />
          </div>
        </form>
      </Modal>
    </div>
  );
}
