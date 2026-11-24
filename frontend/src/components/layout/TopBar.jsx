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
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { useThemeStore } from '../../store/useThemeStore';
import { useNotifications } from '../../hooks/useNotifications';
import { NotificationDrawer } from './NotificationDrawer';
import { GlobalSearchModal } from './GlobalSearchModal';
import { ROLES, ROLE_LABELS } from '../../utils/constants';
import './Shell.css';

const ACRONYM_SEGMENTS = new Set(['HR', 'CEO', 'QA', 'PM']);
const SEGMENT_LABELS = { devops: 'DevOps', github: 'GitHub', 'cicd-logs': 'CI/CD log AI', 'pull-requests': 'Pull requests', 'code-quality': 'Code quality' };

export function TopBar() {
  const { user } = useAuthStore();
  const { theme, toggleTheme, toggleSidebar } = useThemeStore();
  const { unreadCount } = useNotifications();
  const [isNotificationOpen, setIsNotificationOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase();

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
          // Breadcrumb text from the URL segment: acronyms stay upper case.
          label: `${SEGMENT_LABELS[rawSegments[0]] || (ACRONYM_SEGMENTS.has(roleUpper) ? roleUpper : roleUpper.charAt(0) + roleUpper.slice(1).toLowerCase())} dashboard`,
          to: `/${rawSegments[0]}/dashboard`,
          isLast: true,
        },
      ];
    }

    return rawSegments.map((name, index) => {
      const routeTo = `/${rawSegments.slice(0, index + 1).join('/')}`;
      const isLast = index === rawSegments.length - 1;
      const formattedName = SEGMENT_LABELS[name] || name.charAt(0).toUpperCase() + name.slice(1).replace(/-/g, ' ');
      return {
        label: formattedName,
        to: routeTo,
        isLast,
      };
    });
  };

  const breadcrumbs = getBreadcrumbs();
  const roleLabel = ROLE_LABELS[role] || role || '';
  const initials = (user?.name || '')
    .split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('');
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);

  return (
    <>
      <header className="app-topbar">
        <div className="tb-left">
          <button type="button" className="tb-icon tb-menu" onClick={toggleSidebar} aria-label="Open menu" title="Menu">
            <Menu size={20} />
          </button>

          <nav aria-label="Breadcrumb" style={{ minWidth: 0 }}>
            <ol className="tb-crumbs">
              <li>
                <button type="button" className="tb-crumb-link" onClick={() => navigate('/')}>Samanvaya</button>
              </li>
              {breadcrumbs.map((crumb) => (
                <li key={crumb.to}>
                  <ChevronRight size={14} aria-hidden="true" />
                  {crumb.isLast ? (
                    <span className="tb-crumb-current" aria-current="page">{crumb.label}</span>
                  ) : (
                    <button type="button" className="tb-crumb-link" onClick={() => navigate(crumb.to)}>{crumb.label}</button>
                  )}
                </li>
              ))}
            </ol>
          </nav>
        </div>

        <div className="tb-right">
          <button type="button" className="tb-search" onClick={() => setIsSearchOpen(true)} aria-label="Search">
            <Search size={16} aria-hidden="true" />
            <span>Search</span>
            <kbd>{isMac ? '⌘K' : 'Ctrl K'}</kbd>
          </button>

          <button
            type="button"
            className="tb-icon tb-theme"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
            title={theme === 'dark' ? 'Light theme' : 'Dark theme'}
          >
            {theme === 'dark' ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          <button
            type="button"
            className="tb-icon"
            onClick={() => setIsNotificationOpen(true)}
            aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
            title="Notifications"
          >
            <Bell size={18} />
            {unreadCount > 0 && <span className="tb-badge">{unreadCount > 99 ? '99+' : unreadCount}</span>}
          </button>

          <span className="tb-divider" aria-hidden="true" />

          <button type="button" className="tb-user" onClick={() => navigate('/profile')} title="Your profile">
            <span className="shell-avatar" aria-hidden="true">{initials || <User size={15} />}</span>
            <span className="tb-user-text">
              <span className="tb-user-name">{user?.name || 'User'}</span>
              <span className="tb-user-role">{roleLabel}</span>
            </span>
          </button>
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
