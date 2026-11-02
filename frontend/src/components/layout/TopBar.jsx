/**
 * TopBar — breadcrumbs, notifications, profile
 */
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Bell, Menu, Search, X } from 'lucide-react';
import { useQuery } from '@tanstack/react-query';
import { notificationsApi } from '../../api/notifications.api';
import { useAuth } from '../../auth/AuthContext';
import { NOTIFICATION_POLL_INTERVAL } from '../../utils/constants';
import { timeAgo } from '../../utils/dates';
import { initials } from '../../utils/formatters';

function useBreadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split('/').filter(Boolean);
  return parts.map((part, i) => ({
    label: part.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    to: '/' + parts.slice(0, i + 1).join('/'),
    isLast: i === parts.length - 1,
  }));
}

export function TopBar({ onMenuToggle }) {
  const { user } = useAuth();
  const crumbs = useBreadcrumbs();
  const [showNotifs, setShowNotifs] = useState(false);

  const { data: notifData } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => notificationsApi.list({ limit: 10 }).then((r) => r.data),
    refetchInterval: NOTIFICATION_POLL_INTERVAL,
    retry: false,
  });

  const notifications = notifData?.notifications || notifData || [];
  const unreadCount = notifications.filter?.((n) => !n.is_read).length || 0;

  return (
    <header className="topbar" role="banner">
      <div className="topbar-left">
        {/* Mobile menu toggle */}
        <button
          className="btn btn-ghost btn-icon"
          onClick={onMenuToggle}
          aria-label="Toggle navigation"
          style={{ display: 'none' }}
          id="menu-toggle"
        >
          <Menu size={20} />
        </button>

        {/* Breadcrumbs */}
        <nav className="breadcrumb" aria-label="Breadcrumb">
          <Link to="/" style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
            Home
          </Link>
          {crumbs.map((crumb, i) => (
            <span key={crumb.to} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className="breadcrumb-sep" aria-hidden="true">/</span>
              {crumb.isLast ? (
                <span className="breadcrumb-current">{crumb.label}</span>
              ) : (
                <Link to={crumb.to} style={{ color: 'var(--text-secondary)' }}>
                  {crumb.label}
                </Link>
              )}
            </span>
          ))}
        </nav>
      </div>

      <div className="topbar-right">
        {/* Notification bell */}
        <div style={{ position: 'relative' }}>
          <button
            className="btn btn-ghost btn-icon"
            onClick={() => setShowNotifs(!showNotifs)}
            aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ''}`}
            aria-expanded={showNotifs}
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="notif-count" aria-hidden="true">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {/* Notification panel */}
          {showNotifs && (
            <div
              style={{
                position: 'absolute',
                top: 'calc(100% + 8px)',
                right: 0,
                width: 340,
                background: 'var(--bg-card)',
                border: '1px solid var(--border-light)',
                borderRadius: 'var(--radius-lg)',
                boxShadow: 'var(--shadow-lg)',
                zIndex: 300,
                overflow: 'hidden',
              }}
              role="region"
              aria-label="Notifications"
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
                <span style={{ fontWeight: 600, fontSize: '0.875rem' }}>Notifications</span>
                <button className="btn btn-ghost btn-icon" onClick={() => setShowNotifs(false)} aria-label="Close notifications">
                  <X size={16} />
                </button>
              </div>
              <div style={{ maxHeight: 360, overflowY: 'auto' }}>
                {notifications.length === 0 ? (
                  <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
                    No notifications
                  </div>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n._id || n.id}
                      style={{
                        padding: '10px 16px',
                        borderBottom: '1px solid var(--border)',
                        background: !n.is_read ? 'rgba(99,102,241,0.05)' : 'transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <div style={{ fontSize: '0.8125rem', color: 'var(--text-primary)', marginBottom: 2 }}>
                        {n.message || n.title}
                      </div>
                      <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)' }}>
                        {timeAgo(n.created_at)}
                      </div>
                    </div>
                  ))
                )}
              </div>
              <div style={{ padding: '8px 16px', borderTop: '1px solid var(--border)', textAlign: 'center' }}>
                <Link to="/notifications" style={{ fontSize: '0.8125rem', color: 'var(--brand-400)' }} onClick={() => setShowNotifs(false)}>
                  View all
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Profile avatar */}
        <Link to="/profile" aria-label="Profile">
          <div className="avatar avatar-sm" title={user?.name || 'Profile'}>
            {initials(user?.name)}
          </div>
        </Link>
      </div>

      {/* Close notifs on outside click */}
      {showNotifs && (
        <div
          style={{ position: 'fixed', inset: 0, zIndex: 250 }}
          onClick={() => setShowNotifs(false)}
          aria-hidden="true"
        />
      )}
    </header>
  );
}
