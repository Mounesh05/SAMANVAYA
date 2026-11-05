import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { transfersApi } from '../../api/transfers.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Table } from '../../components/common/Table';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { Badge } from '../../components/common/Badge';
import { useAuthStore } from '../../store/useAuthStore';
import { Plus, ArrowRight } from 'lucide-react';

export function TransferRequestsPage() {
  const navigate = useNavigate();
  const { user } = useAuthStore();
  const [statusFilter, setStatusFilter] = useState('all');

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['transfers', statusFilter],
    queryFn: () => transfersApi.getTransfers(statusFilter !== 'all' ? { status: statusFilter } : {}),
  });

  if (isLoading) return <LoadingState message="Loading transfer requests..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const transfers = data?.transfers || [];

  const getStatusBadge = (status) => {
    const variants = {
      pending: 'warning',
      approved: 'success',
      rejected: 'error',
      flagged: 'info',
      executed: 'success',
    };
    return <Badge variant={variants[status] || 'default'}>{status}</Badge>;
  };

  const columns = [
    {
      key: 'employee_id',
      header: 'Employee',
      render: (t) => (
        <span style={{ fontWeight: '600' }}>{t.employee_id}</span>
      ),
    },
    {
      key: 'from_team',
      header: 'From Team',
      render: (t) => t.from_team_id || 'N/A',
    },
    {
      key: 'to_team',
      header: 'To Team',
      render: (t) => t.to_team_id,
    },
    {
      key: 'reason',
      header: 'Reason',
      render: (t) => (
        <span style={{ maxWidth: '200px', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {t.reason || 'N/A'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (t) => getStatusBadge(t.status),
    },
    {
      key: 'requested_at',
      header: 'Requested',
      render: (t) => new Date(t.requested_at).toLocaleDateString(),
    },
    {
      key: 'action',
      header: 'Details',
      render: (t) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/transfers/${t.transfer_id}`)}
        >
          View <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  const canCreateTransfer = user?.role === 'HR' || user?.role === 'Lead';

  return (
    <div>
      <PageHeader
        title="Transfer Requests"
        subtitle="Manage employee team transfer requests across the organization"
        actions={
          canCreateTransfer && (
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => navigate('/transfers/new')}
            >
              New Transfer Request
            </Button>
          )
        }
      />

      {/* Status Filters */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {['all', 'pending', 'approved', 'rejected', 'flagged', 'executed'].map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setStatusFilter(status)}
          >
            {status.charAt(0).toUpperCase() + status.slice(1)}
          </Button>
        ))}
      </div>

      <Card title="Transfer Requests" subtitle="Review and manage transfer requests">
        <Table
          columns={columns}
          data={transfers}
          emptyMessage="No transfer requests found."
        />
      </Card>
    </div>
  );
}
