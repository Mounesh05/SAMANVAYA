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
import { hasPermission, hasAnyPermission, PERMISSIONS, TRANSFER_FOR_OTHERS_PERMISSIONS } from '../../auth/permissions';
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

  // GET /api/transfers returns a plain list (scoped by the backend: an
  // employee without manager/HR rights only sees their own requests).
  const transfers = Array.isArray(data) ? data : data?.transfers || [];
  const managesTransfers = hasAnyPermission(user, TRANSFER_FOR_OTHERS_PERMISSIONS);

  const getStatusBadge = (status) => {
    const variant = status?.startsWith('pending') || status === 'submitted' || status === 'returned_for_correction'
      ? 'warning'
      : { approved: 'success', effective: 'success', rejected: 'error', cancelled: 'default' }[status] || 'default';
    return <Badge variant={variant}>{(status || 'unknown').replace(/_/g, ' ')}</Badge>;
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
      render: (t) => t.current_team_id || 'N/A',
    },
    {
      key: 'to_team',
      header: 'To Team',
      render: (t) => t.requested_team_id,
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
      key: 'created_at',
      header: 'Requested',
      render: (t) => (t.created_at ? new Date(t.created_at).toLocaleDateString() : 'N/A'),
    },
    {
      key: 'action',
      header: 'Details',
      render: (t) => (
        <Button
          variant="secondary"
          size="sm"
          onClick={() => navigate(`/transfers/${t.id}`)}
        >
          View <ArrowRight size={14} />
        </Button>
      ),
    },
  ];

  const canCreateTransfer = hasPermission(user, PERMISSIONS.REQUEST_TRANSFER);

  return (
    <div>
      <PageHeader
        title={managesTransfers ? 'Transfer Requests' : 'My Transfer Requests'}
        subtitle={managesTransfers ? 'Manage employee team transfer requests across the organization' : 'Request a move to another team and follow its progress'}
        actions={
          canCreateTransfer && (
            <Button
              variant="primary"
              leftIcon={<Plus size={16} />}
              onClick={() => navigate('/transfers/new')}
            >
              {managesTransfers ? 'New Transfer Request' : 'Request Transfer'}
            </Button>
          )
        }
      />

      {/* Status Filters */}
      <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
        {['all', 'pending_hr_validation', 'approved', 'effective', 'rejected'].map((status) => (
          <Button
            key={status}
            variant={statusFilter === status ? 'primary' : 'secondary'}
            size="sm"
            onClick={() => setStatusFilter(status)}
          >
            {status === 'pending_hr_validation' ? 'Pending HR' : status.charAt(0).toUpperCase() + status.slice(1)}
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
