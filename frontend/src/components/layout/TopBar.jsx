import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Bell,
  Search,
  Moon,
  Sun,
  Menu,
  ChevronRight,
  User,
  Shield,
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { useThemeStore } from '../../store/useThemeStore';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationDrawer } from './NotificationDrawer';
import { GlobalSearchModal } from './GlobalSearchModal';
import { ROLES, ROLE_COLORS } from '../../utils/constants';

export function TopBar() {
  const { user } = useAuthStore();
  const { theme, toggleTheme, toggleSidebar } = useThemeStore();
  const { unreadCount } = useNotifications();
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase();
  const roleColor = ROLE_COLORS[role] || '#3b82f6';

  // Build clean breadcrumb segments
  const getBreadcrumbs = () => {
    const rawSegments = location.pathname.split('/').filter((x) => x);
    if (rawSegments.length === 0) return [];

    // Role dashboards (e.g. /hr/dashboard, /ceo/dashboard, /developer/dashboard)
    const roleKeys = Object.keys(ROLES).map((k) => k.toLowerCase());
    if (rawSegments.length === 2 && roleKeys.includes(rawSegments[0]) && rawSegments[1] === 'dashboard') {
      const roleUpper = rawSegments[0].toUpperCase();
      return [
        {
          label: `${roleUpper === 'HR' || roleUpper === 'CEO' || roleUpper === 'QA' || roleUpper === 'PM' ? roleUpper : roleUpper.charAt(0) + roleUpper.slice(1).toLowerCase()} Dashboard`,
          to: `/${rawSegments[0]}/dashboard`,
          isLast: true,
        },
      ];
    }

    return rawSegments.map((name, index) => {
      const routeTo = `/${rawSegments.slice(0, index + 1).join('/')}`;
      const isLast = index === rawSegments.length - 1;
      const formattedName = name.charAt(0).toUpperCase() + name.slice(1).replace(/-/g, ' ');
      return {
        label: formattedName,
        to: routeTo,
        isLast,
      };
    });
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <>
      <header
        className="app-topbar"
        style={{
          height: '70px',
          backgroundColor: 'var(--bg-glass)',
          backdropFilter: 'blur(16px)',
          WebkitBackdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 1.5rem',
          position: 'sticky',
          top: 0,
          zIndex: 30,
        }}
      >
        {/* Left: Mobile Toggle & Breadcrumbs */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <button
            onClick={toggleSidebar}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              padding: '0.4rem',
            }}
          >
            <Menu size={20} />
          </button>

          {/* Breadcrumbs */}
          <nav
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              fontSize: '0.8125rem',
              color: 'var(--text-muted)',
            }}
          >
            <span style={{ fontWeight: '600', color: 'var(--text-secondary)' }}>Samanvaya</span>
            {breadcrumbs.map((crumb) => (
              <React.Fragment key={crumb.to}>
                <ChevronRight size={14} style={{ opacity: 0.5 }} />
                {crumb.isLast ? (
                  <span style={{ fontWeight: '700', color: 'var(--text-primary)' }}>
                    {crumb.label}
                  </span>
                ) : (
                  <span
                    onClick={() => navigate(crumb.to)}
                    onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--primary)')}
                    onMouseLeave={(e) => (e.currentTarget.style.color = '')}
                    style={{ cursor: 'pointer' }}
                  >
                    {crumb.label}
                  </span>
                )}
              </React.Fragment>
            ))}
          </nav>
        </div>

        {/* Right: Actions (Search, Theme, Notifications, Role Badge, Profile) */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {/* Quick Search Button */}
          <button
            onClick={() => setIsSearchOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.65rem',
              padding: '0.45rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-input)',
              border: '1px solid var(--border-default)',
              color: 'var(--text-muted)',
              fontSize: '0.8125rem',
              cursor: 'pointer',
              transition: 'border-color var(--transition-fast)',
            }}
          >
            <Search size={15} />
            <span>Search anything...</span>
            <kbd
              style={{
                fontSize: '0.7rem',
                padding: '0.1rem 0.35rem',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(255, 255, 255, 0.08)',
                color: 'var(--text-secondary)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              ⌘K
            </kbd>
          </button>

          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            style={{
              width: '38px',
              height: '38px',
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              transition: 'color var(--transition-fast)',
            }}
            title={theme === 'dark' ? 'Switch to Light Mode' : 'Switch to Dark Mode'}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {/* Notifications Bell */}
          <button
            onClick={() => setIsNotificationOpen(true)}
            style={{
              position: 'relative',
              width: '38px',
              height: '38px',
              borderRadius: 'var(--radius-md)',
              background: 'transparent',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-secondary)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            title="Notifications"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: '-4px',
                  right: '-4px',
                  backgroundColor: 'var(--danger)',
                  color: '#fff',
                  borderRadius: 'var(--radius-full)',
                  fontSize: '0.65rem',
                  fontWeight: '800',
                  minWidth: '18px',
                  height: '18px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  padding: '0 4px',
                  boxShadow: '0 0 8px rgba(239, 68, 68, 0.6)',
                }}
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>

          {/* Role Badge Indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.35rem 0.75rem',
              borderRadius: 'var(--radius-full)',
              backgroundColor: `${roleColor}18`,
              border: `1px solid ${roleColor}40`,
              color: roleColor,
              fontSize: '0.75rem',
              fontWeight: '700',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            <Shield size={13} />
            <span>{role}</span>
          </div>

          {/* User Profile Avatar */}
          <div
            onClick={() => navigate('/profile')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              cursor: 'pointer',
              padding: '0.25rem',
            }}
          >
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '50%',
                backgroundColor: 'var(--bg-elevated)',
                border: '1px solid var(--border-default)',
                color: 'var(--text-primary)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                fontSize: '0.875rem',
              }}
            >
              {user?.name?.charAt(0) || <User size={16} />}
            </div>
          </div>
        </div>
      </header>

      {/* Global Modals & Drawers */}
      <NotificationDrawer
        isOpen={isNotificationOpen}
        onClose={() => setIsNotificationOpen(false)}
      />
      <GlobalSearchModal
        isOpen={isSearchOpen}
        onClose={() => setIsSearchOpen(false)}
        onOpen={() => setIsSearchOpen(true)}
      />
    </>
  );
}
