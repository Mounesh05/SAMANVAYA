import React from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Users,
  Building2,
  FolderGit2,
  ListTodo,
  KanbanSquare,
  ShieldCheck,
  ShieldAlert,
  Cpu,
  Award,
  MessageSquareQuote,
  FileBarChart,
  LogOut,
  ChevronLeft,
  GitPullRequest,
  Layers,
  Terminal,
  Bug,
  FlaskConical,
  BookOpen,
  Rocket,
  AlertTriangle,
  CheckSquare,
  History,
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { authApi } from '../../api/auth.api';
import { useThemeStore } from '../../store/useThemeStore';
import { ROLES, ROLE_LABELS, ROLE_COLORS } from '../../utils/constants';
import { showInMenu } from '../../routes/access';
import { hasAnyPermission, hasPermission, PERMISSIONS, TRANSFER_FOR_OTHERS_PERMISSIONS } from '../../auth/permissions';

export function Sidebar() {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useThemeStore();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase();
  // CR-008: labels follow permissions, not the admin flag.
  const managesTeams = hasPermission(user, PERMISSIONS.MANAGE_TEAMS);
  const handlesOthersTransfers = hasAnyPermission(user, TRANSFER_FOR_OTHERS_PERMISSIONS);

  // Menu entries in display order. Who sees each one comes from the shared
  // page-access table (routes/access.js), the same table the router enforces.
  const getNavItems = () => {
    const isHR = role === ROLES.HR;
    const items = [
      { page: 'dashboard', to: `/${(role || 'developer').toLowerCase()}/dashboard`, icon: <LayoutDashboard size={19} />, label: 'Dashboard' },
      { page: 'projects', to: '/projects', icon: <FolderGit2 size={19} />, label: 'Projects' },
      { page: 'sprints', to: '/sprints', icon: <Layers size={19} />, label: 'Sprints' },
      { page: 'stories', to: '/stories', icon: <BookOpen size={19} />, label: 'Stories' },
      { page: 'tasks', to: '/tasks', icon: <ListTodo size={19} />, label: 'Tasks' },
      { page: 'board', to: '/board', icon: <KanbanSquare size={19} />, label: 'Board' },
      { page: 'employees', to: '/employees', icon: <Users size={19} />, label: 'Employees' },
      { page: 'approvals', to: '/approvals', icon: <CheckSquare size={19} />, label: 'Approvals' },
      { page: 'transfers', to: '/transfers', icon: <GitPullRequest size={19} />, label: handlesOthersTransfers ? 'Transfer Requests' : 'My Transfers' },
      { page: 'teams', to: '/teams', icon: <Building2 size={19} />, label: role === ROLES.LEAD && !managesTeams ? 'My Team' : 'Teams' },
      // Developers cannot list teams; "My Team" opens their own team directly.
      ...(role === ROLES.DEVELOPER && user?.team_id && !managesTeams
        ? [{ page: 'teamDetail', to: `/teams/${user.team_id}`, icon: <Building2 size={19} />, label: 'My Team' }]
        : []),
      { page: 'codeQuality', to: '/code-quality', icon: <ShieldCheck size={19} />, label: 'Code Quality' },
      { page: 'pullRequests', to: '/pull-requests', icon: <GitPullRequest size={19} />, label: 'Pull Requests' },
      { page: 'githubSync', to: '/github/sync', icon: <GitPullRequest size={19} />, label: 'GitHub Sync' },
      { page: 'tests', to: '/tests', icon: <FlaskConical size={19} />, label: 'Tests' },
      { page: 'bugs', to: '/bugs', icon: <Bug size={19} />, label: 'Bugs' },
      { page: 'pipelines', to: '/pipelines', icon: <Terminal size={19} />, label: 'Pipelines' },
      { page: 'deployments', to: '/deployments', icon: <Rocket size={19} />, label: 'Deployments' },
      { page: 'incidents', to: '/incidents', icon: <AlertTriangle size={19} />, label: 'Incidents' },
      { page: 'cicdLogs', to: '/cicd-logs', icon: <Terminal size={19} />, label: 'CI/CD Log AI' },
      { page: 'evaluation', to: '/evaluation', icon: <Cpu size={19} />, label: 'AI Evaluation' },
      { page: 'performance', to: '/performance', icon: <Award size={19} />, label: isHR ? 'Performance Outcomes' : 'Performance' },
      { page: 'feedback', to: '/feedback', icon: <MessageSquareQuote size={19} />, label: isHR ? 'Workplace Assessment' : 'Role Feedback' },
      { page: 'reports', to: '/reports', icon: <FileBarChart size={19} />, label: 'Reports & Trends' },
      { page: 'audit', to: '/audit', icon: <History size={19} />, label: 'Audit Logs' },
      { page: 'ceoQuality', to: '/quality', icon: <ShieldCheck size={19} />, label: 'Quality' },
      { page: 'ceoRisk', to: '/risk', icon: <ShieldAlert size={19} />, label: 'Risk' },
      { page: 'ceoOrganization', to: '/organization', icon: <Building2 size={19} />, label: 'Organization' },
    ];

    // Executive pages stay in the CEO's menu only.
    const ceoOnlyMenu = new Set(['ceoQuality', 'ceoRisk', 'ceoOrganization']);
    const knownRole = Object.values(ROLES).includes(role);
    return items.filter((item) =>
      (item.page === 'dashboard' && knownRole)
      || (ceoOnlyMenu.has(item.page) ? role === ROLES.CEO : showInMenu(user, item.page))
    );
  };

  const navItems = getNavItems();
  const roleColor = ROLE_COLORS[role] || '#3b82f6';

  const handleLogout = async () => {
    await authApi.logout();
    logout();
    window.location.replace('/login');
  };

  return (
    <aside
      className={`app-sidebar ${sidebarCollapsed ? 'app-sidebar-collapsed' : ''}`}
      style={{
        width: sidebarCollapsed ? '72px' : '236px',
        height: '100vh',
        backgroundColor: 'var(--bg-secondary)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        position: 'sticky',
        top: 0,
        zIndex: 40,
        transition: 'width var(--transition-base)',
        flexShrink: 0,
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '1.25rem',
          display: 'flex',
          alignItems: 'center',
          justifyContent: sidebarCollapsed ? 'center' : 'space-between',
          borderBottom: '1px solid var(--border-subtle)',
          minHeight: '70px',
        }}
      >
        {!sidebarCollapsed && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #3b82f6 0%, #a855f7 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontWeight: '900',
                fontSize: '1.1rem',
                boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)',
              }}
            >
              S
            </div>
            <div>
              <h2 style={{ fontSize: '1.125rem', fontWeight: '800', letterSpacing: '-0.03em' }}>
                <span className="gradient-text">Samanvaya</span>
              </h2>
              <p style={{ fontSize: '0.675rem', color: 'var(--text-muted)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Engineering AI
              </p>
            </div>
          </div>
        )}

        {sidebarCollapsed && (
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, #3b82f6 0%, #a855f7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: '900',
              fontSize: '1.2rem',
              boxShadow: '0 0 15px rgba(59, 130, 246, 0.4)',
            }}
          >
            S
          </div>
        )}

        <button
          onClick={toggleSidebar}
          style={{
            display: sidebarCollapsed ? 'none' : 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'transparent',
            border: 'none',
            color: 'var(--text-muted)',
            cursor: 'pointer',
            padding: '0.3rem',
            borderRadius: 'var(--radius-sm)',
          }}
          title={sidebarCollapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
        >
          <ChevronLeft size={18} />
        </button>
      </div>

      {/* Navigation Links */}
      <nav
        style={{
          flex: 1,
          padding: '0.85rem 0.65rem',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.25rem',
        }}
      >
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              padding: sidebarCollapsed ? '0.7rem' : '0.65rem 0.85rem',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.875rem',
              fontWeight: isActive ? '700' : '500',
              color: isActive ? '#ffffff' : 'var(--text-secondary)',
              backgroundColor: isActive ? 'var(--primary)' : 'transparent',
              justifyContent: sidebarCollapsed ? 'center' : 'flex-start',
              textDecoration: 'none',
              transition: 'all var(--transition-fast)',
              boxShadow: isActive ? '0 2px 10px rgba(59, 130, 246, 0.3)' : 'none',
            })}
            title={sidebarCollapsed ? item.label : undefined}
          >
            <span style={{ display: 'flex', alignItems: 'center' }}>{item.icon}</span>
            {!sidebarCollapsed && <span>{item.label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* User & Role Footer */}
      <div
        style={{
          padding: '0.85rem 0.75rem',
          borderTop: '1px solid var(--border-subtle)',
          backgroundColor: 'rgba(0, 0, 0, 0.15)',
        }}
      >
        {!sidebarCollapsed ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div
              style={{ display: 'flex', alignItems: 'center', gap: '0.65rem', cursor: 'pointer' }}
              onClick={() => navigate('/profile')}
            >
              <div
                style={{
                  width: '34px',
                  height: '34px',
                  borderRadius: '50%',
                  backgroundColor: `${roleColor}25`,
                  border: `1.5px solid ${roleColor}`,
                  color: roleColor,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontWeight: '700',
                  fontSize: '0.875rem',
                }}
              >
                {user?.name?.charAt(0) || 'U'}
              </div>
              <div style={{ overflow: 'hidden' }}>
                <div style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                  {user?.name || 'User'}
                </div>
                <div style={{ fontSize: '0.725rem', color: roleColor, fontWeight: '600' }}>
                  {ROLE_LABELS[role] || role}
                </div>
              </div>
            </div>

            <button
              onClick={handleLogout}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '0.4rem',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              title="Logout"
            >
              <LogOut size={17} />
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.5rem' }}>
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '50%',
                backgroundColor: `${roleColor}25`,
                border: `1.5px solid ${roleColor}`,
                color: roleColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '700',
                fontSize: '0.875rem',
                cursor: 'pointer',
              }}
              onClick={() => navigate('/profile')}
              title={`${user?.name} (${role})`}
            >
              {user?.name?.charAt(0) || 'U'}
            </div>
            <button
              onClick={handleLogout}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '0.3rem',
              }}
              title="Logout"
            >
              <LogOut size={16} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
