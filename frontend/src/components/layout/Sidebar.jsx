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
  Cpu,
  Award,
  MessageSquareQuote,
  FileBarChart,
  Bell,
  Activity,
  User,
  LogOut,
  ChevronLeft,
  ChevronRight,
  GitPullRequest,
  Layers,
  Terminal,
  Bug,
  FlaskConical,
  BookOpen,
  Rocket,
  AlertTriangle,
  History,
} from 'lucide-react';
import { useAuthStore } from '../../store/useAuthStore';
import { useThemeStore } from '../../store/useThemeStore';
import { ROLES, ROLE_LABELS, ROLE_COLORS } from '../../utils/constants';

export function Sidebar() {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar } = useThemeStore();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase();
  const isAdmin = user?.is_admin || false;

  // Define navigation sections based on role
  const getNavItems = () => {
    // 1. Dashboard based on role
    const items = [
      {
        to: `/${(role || 'developer').toLowerCase()}/dashboard`,
        icon: <LayoutDashboard size={19} />,
        label: 'Dashboard',
        roles: Object.values(ROLES),
      },
    ];

    // 2. Work management
    items.push(
      {
        to: '/projects',
        icon: <FolderGit2 size={19} />,
        label: 'Projects',
        roles: [ROLES.PM, ROLES.CEO, ROLES.HR, ROLES.LEAD, ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS],
      },
      {
        to: '/sprints',
        icon: <Layers size={19} />,
        label: 'Sprints',
        roles: [ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.QA, ROLES.DEVOPS],
      },
      {
        to: '/stories',
        icon: <BookOpen size={19} />,
        label: 'Stories',
        roles: [ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER],
      },
      {
        to: '/tasks',
        icon: <ListTodo size={19} />,
        label: 'Tasks',
        roles: [ROLES.DEVELOPER, ROLES.LEAD, ROLES.PM, ROLES.QA, ROLES.DEVOPS],
      },
      {
        to: '/board',
        icon: <KanbanSquare size={19} />,
        label: 'Kanban Board',
        roles: [ROLES.DEVELOPER, ROLES.LEAD, ROLES.PM, ROLES.QA, ROLES.DEVOPS],
      }
    );

    // 3. Organization & People (HR, CEO, Leads)
    if (role === ROLES.HR || role === ROLES.CEO || isAdmin) {
      items.push(
        {
          to: '/employees',
          icon: <Users size={19} />,
          label: 'Employees',
          roles: [ROLES.HR, ROLES.CEO],
        },
        {
          to: '/teams',
          icon: <Building2 size={19} />,
          label: 'Teams',
          roles: [ROLES.HR, ROLES.CEO],
        }
      );
    } else if (role === ROLES.LEAD) {
      items.push({
        to: '/teams',
        icon: <Building2 size={19} />,
        label: 'My Team',
        roles: [ROLES.LEAD],
      });
    }

    // 4. Engineering & Intelligence
    items.push(
      {
        to: '/code-quality',
        icon: <ShieldCheck size={19} />,
        label: 'Code Quality',
        roles: Object.values(ROLES),
      },
      {
        to: '/pull-requests',
        icon: <GitPullRequest size={19} />,
        label: 'Pull Requests',
        roles: [ROLES.DEVELOPER, ROLES.LEAD, ROLES.QA, ROLES.DEVOPS],
      },
      {
        to: '/github/sync',
        icon: <GitPullRequest size={19} />,
        label: 'GitHub Sync',
        roles: [ROLES.DEVELOPER, ROLES.LEAD, ROLES.PM, ROLES.QA, ROLES.DEVOPS],
      },
      {
        to: '/tests',
        icon: <FlaskConical size={19} />,
        label: 'Tests',
        roles: [ROLES.QA, ROLES.LEAD, ROLES.DEVELOPER],
      },
      {
        to: '/bugs',
        icon: <Bug size={19} />,
        label: 'Bugs',
        roles: [ROLES.QA, ROLES.DEVELOPER, ROLES.LEAD],
      },
      {
        to: '/pipelines',
        icon: <Terminal size={19} />,
        label: 'Pipelines',
        roles: [ROLES.DEVOPS, ROLES.QA, ROLES.LEAD],
      },
      {
        to: '/deployments',
        icon: <Rocket size={19} />,
        label: 'Deployments',
        roles: [ROLES.DEVOPS, ROLES.LEAD],
      },
      {
        to: '/incidents',
        icon: <AlertTriangle size={19} />,
        label: 'Incidents',
        roles: [ROLES.DEVOPS, ROLES.LEAD, ROLES.CEO],
      },
      {
        to: '/cicd-logs',
        icon: <Terminal size={19} />,
        label: 'CI/CD Log AI',
        roles: [ROLES.DEVOPS, ROLES.QA, ROLES.LEAD, ROLES.DEVELOPER],
      },
      {
        to: '/evaluation',
        icon: <Cpu size={19} />,
        label: 'AI Evaluation',
        roles: [ROLES.CEO, ROLES.HR, ROLES.LEAD],
      }
    );

    // 5. Performance & Feedback
    items.push(
      {
        to: '/performance',
        icon: <Award size={19} />,
        label: 'Performance',
        roles: Object.values(ROLES),
      },
      {
        to: '/feedback',
        icon: <MessageSquareQuote size={19} />,
        label: 'Role Feedback',
        roles: [ROLES.LEAD, ROLES.PM, ROLES.QA, ROLES.DEVOPS, ROLES.HR, ROLES.CEO],
      },
      {
        to: '/reports',
        icon: <FileBarChart size={19} />,
        label: 'Reports & Trends',
        roles: Object.values(ROLES),
      },
      {
        to: '/audit',
        icon: <History size={19} />,
        label: 'Audit Logs',
        roles: [ROLES.HR, ROLES.CEO],
      }
    );

    // Filter items according to current role
    return items.filter((item) => isAdmin || item.roles.includes(role));
  };

  const navItems = getNavItems();
  const roleColor = ROLE_COLORS[role] || '#3b82f6';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <aside
      style={{
        width: sidebarCollapsed ? '76px' : '260px',
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
                <span className="gradient-text">SAMANVAYA</span>
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
