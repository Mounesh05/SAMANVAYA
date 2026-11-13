import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { approvalsApi } from '../../api/approvals.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';

const EMPTY = [];

function formatTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function ApprovalCard({ approval, actions }) {
  return (
    <Card padding="md" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <strong>{approval.description}</strong>
        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{approval.id}</span>
      </div>
      <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
        Requested by {approval.requested_by || approval.agent_name} · {formatTime(approval.created_at)} · expires {formatTime(approval.expires_at)}
      </p>
      {actions}
    </Card>
  );
}

/**
 * CR-010: approvals waiting for you, and the requests you raised.
 * The backend decides who may approve; this page only shows the decision.
 */
export function ApprovalsPage() {
  const queryClient = useQueryClient();
  const [notice, setNotice] = useState(null);
  const [reasons, setReasons] = useState({});

  const pendingQuery = useQuery({ queryKey: ['approvals', 'pending'], queryFn: approvalsApi.listPending });
  const mineQuery = useQuery({ queryKey: ['approvals', 'mine'], queryFn: approvalsApi.listMine });

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['approvals'] });
    queryClient.invalidateQueries({ queryKey: ['employees'] });
  };
  const failure = (error) => setNotice({
    tone: 'danger', text: error?.response?.data?.detail || error?.message || 'The request could not be completed',
  });

  const approveMutation = useMutation({
    mutationFn: (id) => approvalsApi.approve(id),
    onSuccess: (_, id) => { setNotice({ tone: 'success', text: `Approved and applied (${id}).` }); refresh(); },
    onError: (error) => { failure(error); refresh(); },
  });
  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }) => approvalsApi.reject(id, reason),
    onSuccess: (_, { id }) => { setNotice({ tone: 'success', text: `Rejected (${id}). Nothing was changed.` }); refresh(); },
    onError: failure,
  });

  if (pendingQuery.isLoading || mineQuery.isLoading) return <LoadingState message="Loading approvals..." />;
  if (pendingQuery.error) return <ErrorState message="Could not load approvals" onRetry={() => pendingQuery.refetch()} />;

  const pending = pendingQuery.data?.approvals || EMPTY;
  const mine = mineQuery.data?.approvals || EMPTY;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <PageHeader
        title="Approvals"
        subtitle="Account changes need a second person: admin rights, role changes, and activation or deactivation."
      />
      {notice && (
        <p role={notice.tone === 'danger' ? 'alert' : 'status'} style={{ color: `var(--${notice.tone})`, margin: 0 }}>
          {notice.text}
        </p>
      )}

      <section style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <h2 style={{ fontSize: '1rem', margin: 0 }}>Waiting for you ({pending.length})</h2>
        {pending.length === 0 && <p style={{ color: 'var(--text-muted)', margin: 0 }}>Nothing is waiting for your approval.</p>}
        {pending.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            actions={(
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => approveMutation.mutate(approval.id)}
                  disabled={approveMutation.isPending}
                >
                  Approve
                </Button>
                <input
                  aria-label={`Reason for rejecting ${approval.id}`}
                  placeholder="Reason for rejecting"
                  value={reasons[approval.id] || ''}
                  onChange={(event) => setReasons({ ...reasons, [approval.id]: event.target.value })}
                  style={{ flex: '1 1 200px', minWidth: 0, padding: '0.4rem 0.6rem' }}
                />
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => rejectMutation.mutate({ id: approval.id, reason: reasons[approval.id] })}
                  disabled={!reasons[approval.id]?.trim() || rejectMutation.isPending}
                >
                  Reject
                </Button>
              </div>
            )}
          />
        ))}
      </section>

      <section style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <h2 style={{ fontSize: '1rem', margin: 0 }}>Your requests ({mine.length})</h2>
        {mine.length === 0 && <p style={{ color: 'var(--text-muted)', margin: 0 }}>You have no pending requests.</p>}
        {mine.map((approval) => (
          <ApprovalCard
            key={approval.id}
            approval={approval}
            actions={<span style={{ fontSize: '0.8125rem' }}>Waiting for: {approval.approvers.join(', ')}</span>}
          />
        ))}
      </section>
    </div>
  );
}
