import React from 'react';
import './Shell.css';
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
  PanelLeftClose,
  PanelLeftOpen,
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
import { ROLES, ROLE_LABELS } from '../../utils/constants';
import { canOpenPage, showInMenu } from '../../routes/access';
import { hasAnyPermission, hasPermission, PERMISSIONS, TEAM_LIST_PERMISSIONS, TRANSFER_FOR_OTHERS_PERMISSIONS } from '../../auth/permissions';

// Menu sections, in order. Each page key belongs to one section; a section
// with nothing the person can open is left out.
const NAV_SECTIONS = [
  { title: 'Overview', pages: ['dashboard'] },
  { title: 'Delivery', pages: ['projects', 'sprints', 'stories', 'tasks', 'board', 'releases'] },
  { title: 'Engineering', pages: ['codeQuality', 'algorithmIntelligence', 'pullRequests', 'githubSync', 'tests', 'bugs', 'pipelines', 'deployments', 'incidents', 'cicdLogs'] },
  { title: 'People', pages: ['employees', 'approvals', 'transfers', 'teams', 'teamDetail', 'evaluation', 'performance', 'feedback'] },
  { title: 'Insights', pages: ['reports', 'audit', 'ceoQuality', 'ceoRisk', 'ceoOrganization'] },
];

export function Sidebar() {
  const { user, logout } = useAuthStore();
  const { sidebarCollapsed, toggleSidebar, setSidebarCollapsed } = useThemeStore();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase();
  // Labels and shortcuts follow permissions, not role names.
  const handlesOthersTransfers = hasAnyPermission(user, TRANSFER_FOR_OTHERS_PERMISSIONS);
  // "My Team": can see only one's own team (VIEW_TEAM_DATA without wider team rights).
  const ownTeamOnly = hasPermission(user, PERMISSIONS.VIEW_TEAM_DATA) && !hasAnyPermission(user, [
    ...TEAM_LIST_PERMISSIONS.filter((p) => p !== PERMISSIONS.VIEW_TEAM_DATA), PERMISSIONS.MANAGE_TEAMS,
  ]);
  const reviewsPerformanceOutcomes = hasPermission(user, PERMISSIONS.VIEW_PERFORMANCE_OUTCOMES);
  const submitsHrAssessments = hasPermission(user, PERMISSIONS.SUBMIT_HR_FEEDBACK);

  // Menu entries in display order. Who sees each one comes from the shared
  // page-access table (routes/access.js), the same table the router enforces.
  const getNavItems = () => {
    const items = [
      { page: 'dashboard', to: `/${(role || 'developer').toLowerCase()}/dashboard`, icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
      { page: 'projects', to: '/projects', icon: <FolderGit2 size={18} />, label: 'Projects' },
      { page: 'sprints', to: '/sprints', icon: <Layers size={18} />, label: 'Sprints' },
      { page: 'stories', to: '/stories', icon: <BookOpen size={18} />, label: 'Stories' },
      { page: 'tasks', to: '/tasks', icon: <ListTodo size={18} />, label: 'Tasks' },
      { page: 'board', to: '/board', icon: <KanbanSquare size={18} />, label: 'Board' },
      { page: 'employees', to: '/employees', icon: <Users size={18} />, label: 'Employees' },
      { page: 'approvals', to: '/approvals', icon: <CheckSquare size={18} />, label: 'Approvals' },
      { page: 'transfers', to: '/transfers', icon: <GitPullRequest size={18} />, label: handlesOthersTransfers ? 'Transfer Requests' : 'My Transfers' },
      { page: 'teams', to: '/teams', icon: <Building2 size={18} />, label: ownTeamOnly ? 'My Team' : 'Teams' },
      // People who can't list teams but can open their own get a direct "My Team" link.
      ...(user?.team_id && !canOpenPage(user, 'teams') && canOpenPage(user, 'teamDetail')
        ? [{ page: 'teamDetail', to: `/teams/${user.team_id}`, icon: <Building2 size={18} />, label: 'My Team' }]
        : []),
      { page: 'codeQuality', to: '/code-quality', icon: <ShieldCheck size={18} />, label: 'Code Quality' },
      { page: 'algorithmIntelligence', to: '/algorithm-intelligence', icon: <Cpu size={18} />, label: 'Algorithm Intelligence' },
      { page: 'pullRequests', to: '/pull-requests', icon: <GitPullRequest size={18} />, label: 'Pull Requests' },
      { page: 'githubSync', to: '/github/sync', icon: <GitPullRequest size={18} />, label: 'GitHub Sync' },
      { page: 'tests', to: '/tests', icon: <FlaskConical size={18} />, label: 'Tests' },
      { page: 'bugs', to: '/bugs', icon: <Bug size={18} />, label: 'Bugs' },
      { page: 'pipelines', to: '/pipelines', icon: <Terminal size={18} />, label: 'Pipelines' },
      { page: 'deployments', to: '/deployments', icon: <Rocket size={18} />, label: 'Deployments' },
      { page: 'releases', to: '/releases', icon: <Rocket size={18} />, label: 'Releases' },
      { page: 'incidents', to: '/incidents', icon: <AlertTriangle size={18} />, label: 'Incidents' },
      { page: 'cicdLogs', to: '/cicd-logs', icon: <Terminal size={18} />, label: 'CI/CD Log AI' },
      { page: 'evaluation', to: '/evaluation', icon: <Cpu size={18} />, label: 'AI Evaluation' },
      { page: 'performance', to: '/performance', icon: <Award size={18} />, label: reviewsPerformanceOutcomes ? 'Performance Outcomes' : 'Performance' },
      { page: 'feedback', to: '/feedback', icon: <MessageSquareQuote size={18} />, label: submitsHrAssessments ? 'Workplace feedback' : 'Assigned feedback' },
      { page: 'reports', to: '/reports', icon: <FileBarChart size={18} />, label: 'Reports & Trends' },
      { page: 'audit', to: '/audit', icon: <History size={18} />, label: 'Audit Logs' },
      { page: 'ceoQuality', to: '/quality', icon: <ShieldCheck size={18} />, label: 'Quality' },
      { page: 'ceoRisk', to: '/risk', icon: <ShieldAlert size={18} />, label: 'Risk' },
      { page: 'ceoOrganization', to: '/organization', icon: <Building2 size={18} />, label: 'Organization' },
    ];

    // The dashboard link opens the user's own role dashboard (a persona view);
    // every other entry follows the shared page-access table.
    const knownRole = Object.values(ROLES).includes(role);
    return items.filter((item) => (item.page === 'dashboard' ? knownRole : showInMenu(user, item.page)));
  };

  const navItems = getNavItems();
  const sections = NAV_SECTIONS
    .map((section) => ({ ...section, items: navItems.filter((item) => section.pages.includes(item.page)) }))
    .filter((section) => section.items.length > 0);

  const roleLabel = ROLE_LABELS[role] || role || '';
  const initials = (user?.name || '')
    .split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('') || 'U';
  const isPhone = () => window.matchMedia?.('(max-width: 700px)').matches;
  const closeOnPhone = () => { if (isPhone()) setSidebarCollapsed(true); };

  const handleLogout = async () => {
    await authApi.logout();
    logout();
    window.location.replace('/login');
  };

  return (
    <>
      {!sidebarCollapsed && <div className="sb-backdrop" onClick={toggleSidebar} aria-hidden="true" />}
      <aside
        className={`app-sidebar ${sidebarCollapsed ? 'app-sidebar-collapsed' : ''}`}
        aria-label="Main menu"
      >
        <NavLink to={navItems[0]?.to || '/'} className="sb-brand" title="Samanvaya" onClick={closeOnPhone}>
          <span className="sb-mark" aria-hidden="true">S</span>
          {!sidebarCollapsed && (
            <span className="sb-name">
              Samanvaya
            </span>
          )}
        </NavLink>

        <nav className="sb-nav">
          {sections.map((section) => (
            <div className="sb-section" key={section.title}>
              <div className="sb-section-title">{section.title}</div>
              <ul className="sb-list">
                {section.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      className="sb-link"
                      title={sidebarCollapsed ? item.label : undefined}
                      onClick={closeOnPhone}
                    >
                      {item.icon}
                      {!sidebarCollapsed && <span className="sb-label">{item.label}</span>}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="sb-footer">
          <button
            type="button"
            className="sb-icon-button sb-collapse"
            onClick={toggleSidebar}
            aria-label={sidebarCollapsed ? 'Expand menu' : 'Collapse menu'}
            title={sidebarCollapsed ? 'Expand menu' : 'Collapse menu'}
          >
            {sidebarCollapsed ? <PanelLeftOpen size={17} /> : <PanelLeftClose size={17} />}
            {!sidebarCollapsed && <span>Collapse</span>}
          </button>
          <div className="sb-user">
            <button
              type="button"
              className="sb-user-main"
              onClick={() => { closeOnPhone(); navigate('/profile'); }}
              title={sidebarCollapsed ? `${user?.name || 'User'} · ${roleLabel}` : 'Your profile'}
            >
              <span className="shell-avatar" aria-hidden="true">{initials}</span>
              {!sidebarCollapsed && (
                <span style={{ minWidth: 0 }}>
                  <span className="sb-user-name" style={{ display: 'block' }}>{user?.name || 'User'}</span>
                  <span className="sb-user-role" style={{ display: 'block' }}>{roleLabel}</span>
                </span>
              )}
            </button>
            <button type="button" className="sb-icon-button" onClick={handleLogout} aria-label="Sign out" title="Sign out">
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
    </>
  );
}
