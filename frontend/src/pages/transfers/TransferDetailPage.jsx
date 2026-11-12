import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { transfersApi } from '../../api/transfers.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Badge } from '../../components/common/Badge';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { useAuthStore } from '../../store/useAuthStore';
import { CheckCircle, XCircle, Flag, Play, ArrowLeft } from 'lucide-react';

export function TransferDetailPage() {
  const { transferId } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuthStore();

  const [actionComment, setActionComment] = useState('');
  const [error, setError] = useState(null);

  const { data, isLoading, error: fetchError, refetch } = useQuery({
    queryKey: ['transfer', transferId],
    queryFn: () => transfersApi.getTransferById(transferId),
  });

  const approveMutation = useMutation({
    mutationFn: (comment) => transfersApi.approveTransfer(transferId, { hr_comment: comment }),
    onSuccess: () => {
      queryClient.invalidateQueries(['transfer', transferId]);
      queryClient.invalidateQueries(['transfers']);
      setActionComment('');
    },
    onError: (err) => setError(err.message),
  });

  const rejectMutation = useMutation({
    mutationFn: (comment) => transfersApi.rejectTransfer(transferId, { hr_comment: comment }),
    onSuccess: () => {
      queryClient.invalidateQueries(['transfer', transferId]);
      queryClient.invalidateQueries(['transfers']);
      setActionComment('');
    },
    onError: (err) => setError(err.message),
  });

  const flagMutation = useMutation({
    mutationFn: (comment) => transfersApi.flagTransfer(transferId, { manager_comment: comment }),
    onSuccess: () => {
      queryClient.invalidateQueries(['transfer', transferId]);
      queryClient.invalidateQueries(['transfers']);
      setActionComment('');
    },
    onError: (err) => setError(err.message),
  });

  const executeMutation = useMutation({
    mutationFn: () => transfersApi.executeTransfer(transferId),
    onSuccess: () => {
      queryClient.invalidateQueries(['transfer', transferId]);
      queryClient.invalidateQueries(['transfers']);
    },
    onError: (err) => setError(err.message),
  });

  if (isLoading) return <LoadingState message="Loading transfer details..." />;
  if (fetchError) return <ErrorState message={fetchError.message} onRetry={refetch} />;

  const transfer = data?.transfer || data;

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

  const isHR = user?.role === 'HR';
  const isManager = user?.role === 'Lead';
  const isPMorCEO = user?.role === 'PM' || user?.role === 'CEO';
  const canApprove = isHR && transfer.status === 'pending';
  const canReject = isHR && transfer.status === 'pending';
  const canFlag = isManager && transfer.status === 'pending';
  const canExecute = isPMorCEO && transfer.status === 'approved';

  return (
    <div>
      <PageHeader
        title={`Transfer Request: ${transfer.id}`}
        subtitle={`Employee: ${transfer.employee_id}`}
        actions={
          <Button variant="secondary" leftIcon={<ArrowLeft size={16} />} onClick={() => navigate('/transfers')}>
            Back to Transfers
          </Button>
        }
      />

      {/* Transfer Details */}
      <Card title="Transfer Information" subtitle="Details of the transfer request" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: '1rem', fontSize: '0.875rem' }}>
          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Transfer ID:</div>
          <div style={{ fontWeight: '600', fontFamily: 'monospace' }}>{transfer.id}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Employee:</div>
          <div style={{ fontWeight: '600' }}>{transfer.employee_id}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>From Team:</div>
          <div>{transfer.current_team_id || 'Unassigned'}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>To Team:</div>
          <div style={{ fontWeight: '600' }}>{transfer.requested_team_id}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Status:</div>
          <div>{getStatusBadge(transfer.status)}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Requested By:</div>
          <div>{transfer.initiated_by}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Requested At:</div>
          <div>{transfer.created_at ? new Date(transfer.created_at).toLocaleString() : 'N/A'}</div>

          <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Reason:</div>
          <div style={{ whiteSpace: 'pre-wrap' }}>{[transfer.reason?.replace(/_/g, ' '), transfer.justification].filter(Boolean).join(' — ') || 'N/A'}</div>

          {transfer.hr_comment && (
            <>
              <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>HR Comment:</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{transfer.hr_comment}</div>
            </>
          )}

          {transfer.manager_comment && (
            <>
              <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Manager Comment:</div>
              <div style={{ whiteSpace: 'pre-wrap' }}>{transfer.manager_comment}</div>
            </>
          )}

          {transfer.approved_at && (
            <>
              <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Approved At:</div>
              <div>{new Date(transfer.approved_at).toLocaleString()}</div>
            </>
          )}

          {transfer.executed_at && (
            <>
              <div style={{ fontWeight: '600', color: 'var(--text-muted)' }}>Executed At:</div>
              <div>{new Date(transfer.executed_at).toLocaleString()}</div>
            </>
          )}
        </div>
      </Card>

      {/* Actions Section */}
      {(canApprove || canReject || canFlag || canExecute) && (
        <Card title="Actions" subtitle="Take action on this transfer request">
          {error && (
            <div
              style={{
                padding: '0.75rem',
                backgroundColor: 'var(--error-bg)',
                color: 'var(--error)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.875rem',
                marginBottom: '1rem',
              }}
            >
              {error}
            </div>
          )}

          {/* Comment Input (for approve/reject/flag) */}
          {(canApprove || canReject || canFlag) && (
            <div style={{ marginBottom: '1rem' }}>
              <label
                style={{
                  display: 'block',
                  fontSize: '0.875rem',
                  fontWeight: '600',
                  marginBottom: '0.5rem',
                }}
              >
                Comment (optional)
              </label>
              <textarea
                value={actionComment}
                onChange={(e) => setActionComment(e.target.value)}
                placeholder="Add a comment for this action..."
                rows={3}
                style={{
                  width: '100%',
                  padding: '0.625rem',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.875rem',
                  backgroundColor: 'var(--bg-primary)',
                  color: 'var(--text-primary)',
                  fontFamily: 'inherit',
                  resize: 'vertical',
                }}
              />
            </div>
          )}

          {/* Action Buttons */}
          <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            {canApprove && (
              <Button
                variant="primary"
                leftIcon={<CheckCircle size={16} />}
                onClick={() => approveMutation.mutate(actionComment)}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? 'Approving...' : 'Approve Transfer'}
              </Button>
            )}

            {canReject && (
              <Button
                variant="danger"
                leftIcon={<XCircle size={16} />}
                onClick={() => rejectMutation.mutate(actionComment)}
                disabled={rejectMutation.isPending}
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Reject Transfer'}
              </Button>
            )}

            {canFlag && (
              <Button
                variant="warning"
                leftIcon={<Flag size={16} />}
                onClick={() => flagMutation.mutate(actionComment)}
                disabled={flagMutation.isPending}
              >
                {flagMutation.isPending ? 'Flagging...' : 'Flag for Review'}
              </Button>
            )}

            {canExecute && (
              <Button
                variant="success"
                leftIcon={<Play size={16} />}
                onClick={() => executeMutation.mutate()}
                disabled={executeMutation.isPending}
              >
                {executeMutation.isPending ? 'Executing...' : 'Execute Transfer'}
              </Button>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
