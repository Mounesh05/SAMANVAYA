/**
 * Sidebar — role-aware navigation
 * Generates nav items from ROLE_NAV based on current user role.
 */
import { NavLink } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { usePermissions } from '../../hooks/usePermissions';
import {
  LayoutDashboard, CheckSquare, Kanban, FolderKanban, Zap,
  GitPullRequest, ShieldCheck, TrendingUp, Users, MessageSquare,
  BarChart3, TestTube, Bug, GitBranch, Rocket, AlertTriangle,
  UserCircle, FileBarChart, Building2, AlertCircle, LogOut,
  Settings,
} from 'lucide-react';

const ICON_MAP = {
  LayoutDashboard, CheckSquare, Kanban, FolderKanban, Zap,
  GitPullRequest, ShieldCheck, TrendingUp, Users, MessageSquare,
  BarChart3, TestTube, Bug, GitBranch, Rocket, AlertTriangle,
  UserCircle, FileBarChart, Building2, AlertCircle,
};

export function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const { navItems } = usePermissions();

  const handleLogout = async () => {
    await logout();
  };

  return (
    <aside className={`sidebar${open ? ' open' : ''}`} role="navigation" aria-label="Main navigation">
      {/* Logo */}
      <div className="sidebar-logo" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <img
          src="/logo.jpeg"
          alt="Samanvaya"
          style={{
            width: 44,
            height: 44,
            borderRadius: 10,
            objectFit: 'cover',
            boxShadow: '0 0 16px rgba(99, 102, 241, 0.5)',
            border: '1.5px solid rgba(255, 255, 255, 0.25)',
            flexShrink: 0
          }}
        />
        <span className="sidebar-logo-text" style={{ fontSize: '1.25rem', fontWeight: 800 }}>Samanvaya</span>
      </div>

      {/* Nav items */}
      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const Icon = ICON_MAP[item.icon] || LayoutDashboard;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
              onClick={() => onClose?.()}
              aria-current={undefined}
            >
              <Icon aria-hidden="true" />
              <span>{item.label}</span>
            </NavLink>
          );
        })}

        {/* Divider */}
        <div style={{ borderTop: '1px solid var(--border)', margin: '8px 0' }} />

        <NavLink
          to="/profile"
          className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}
          onClick={() => onClose?.()}
        >
          <Settings size={18} aria-hidden="true" />
          <span>Profile</span>
        </NavLink>
      </nav>

      {/* Footer */}
      <div className="sidebar-footer">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
          <div className="avatar avatar-sm" aria-hidden="true">
            {user?.name?.charAt(0)?.toUpperCase() || '?'}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.8125rem', fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.name || 'User'}
            </div>
            <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
              {user?.role || ''}
            </div>
          </div>
        </div>
        <button
          className="btn btn-ghost btn-sm w-full"
          onClick={handleLogout}
          style={{ justifyContent: 'flex-start', gap: 8 }}
          aria-label="Log out"
        >
          <LogOut size={16} aria-hidden="true" />
          Log Out
        </button>
      </div>
    </aside>
  );
}
