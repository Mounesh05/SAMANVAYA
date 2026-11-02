/**
 * Notifications Page — full notification list
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notificationsApi } from '../../api/notifications.api';
import { LoadingState, ErrorState, EmptyState } from '../../components/common/States';
import { timeAgo } from '../../utils/dates';
import { Bell, CheckCheck } from 'lucide-react';
import toast from 'react-hot-toast';

export function NotificationsPage() {
  const qc = useQueryClient();

  const { data, isLoading, isError, error, refetch } = useQuery({
    queryKey: ['notifications-all'],
    queryFn: () => notificationsApi.list({ limit: 50 }).then((r) => r.data),
  });

  const markAllMutation = useMutation({
    mutationFn: () => notificationsApi.markAllRead(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
      qc.invalidateQueries({ queryKey: ['notifications-all'] });
      toast.success('All notifications marked as read');
    },
  });

  const markOneMutation = useMutation({
    mutationFn: (id) => notificationsApi.markRead(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['notifications'] });
      qc.invalidateQueries({ queryKey: ['notifications-all'] });
    },
  });

  const notifications = Array.isArray(data) ? data : data?.notifications || [];
  const unread = notifications.filter((n) => !n.is_read).length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Notifications</h1>
          <p className="page-subtitle">{unread} unread</p>
        </div>
        {unread > 0 && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={() => markAllMutation.mutate()}
            disabled={markAllMutation.isPending}
          >
            <CheckCheck size={14} />
            Mark all read
          </button>
        )}
      </div>

      {isLoading && <LoadingState message="Loading notifications…" />}
      {isError && <ErrorState description={error.userMessage} onRetry={refetch} />}

      {!isLoading && !isError && notifications.length === 0 && (
        <EmptyState
          title="No notifications"
          description="You're all caught up!"
          action={<Bell size={40} style={{ color: 'var(--text-muted)' }} />}
        />
      )}

      {!isLoading && !isError && notifications.length > 0 && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          {notifications.map((n, i) => (
            <div
              key={n._id || n.id || i}
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: 'var(--space-4)',
                padding: 'var(--space-4) var(--space-5)',
                borderBottom: i < notifications.length - 1 ? '1px solid var(--border)' : 'none',
                background: !n.is_read ? 'rgba(99,102,241,0.04)' : 'transparent',
                cursor: !n.is_read ? 'pointer' : 'default',
                transition: 'background var(--transition)',
              }}
              onClick={() => !n.is_read && markOneMutation.mutate(n._id || n.id)}
              role={!n.is_read ? 'button' : undefined}
              tabIndex={!n.is_read ? 0 : undefined}
              aria-label={!n.is_read ? `Mark as read: ${n.message || n.title}` : undefined}
              onKeyDown={(e) => e.key === 'Enter' && !n.is_read && markOneMutation.mutate(n._id || n.id)}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: '50%',
                  background: !n.is_read ? 'var(--brand-500)' : 'transparent',
                  flexShrink: 0,
                  marginTop: 6,
                }}
                aria-hidden="true"
              />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: '0.875rem', color: !n.is_read ? 'var(--text-primary)' : 'var(--text-secondary)', marginBottom: 4, fontWeight: !n.is_read ? 500 : 400 }}>
                  {n.message || n.title}
                </div>
                {n.description && (
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginBottom: 4 }}>{n.description}</div>
                )}
                <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{timeAgo(n.created_at)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
