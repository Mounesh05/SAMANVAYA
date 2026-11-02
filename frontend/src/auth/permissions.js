/**
 * RBAC constants — seven roles and their permission sets.
 * Frontend checks are for UX only. Backend remains authoritative.
 */

export const ROLES = {
  DEVELOPER: 'DEVELOPER',
  LEAD: 'LEAD',
  PM: 'PM',
  QA: 'QA',
  DEVOPS: 'DEVOPS',
  HR: 'HR',
  CEO: 'CEO',
};

export const PERMISSIONS = {
  // Organization
  VIEW_ORGANIZATION: 'view_organization',
  MANAGE_EMPLOYEES: 'manage_employees',
  MANAGE_TEAMS: 'manage_teams',
  VIEW_ALL_PERFORMANCE: 'view_all_performance',

  // Projects
  CREATE_PROJECT: 'create_project',
  MANAGE_PROJECT: 'manage_project',
  VIEW_PROJECT: 'view_project',

  // Sprints / Stories / Tasks
  MANAGE_SPRINT: 'manage_sprint',
  MANAGE_STORY: 'manage_story',
  MANAGE_TASK: 'manage_task',
  VIEW_TASK: 'view_task',

  // Code Quality
  VIEW_TEAM_CODE_QUALITY: 'view_team_code_quality',
  VIEW_PROJECT_CODE_QUALITY: 'view_project_code_quality',

  // DevOps
  MANAGE_CICD: 'manage_cicd',
  VIEW_DEPLOYMENTS: 'view_deployments',
  MANAGE_INCIDENTS: 'manage_incidents',

  // Feedback / Evaluation
  SUBMIT_FEEDBACK: 'submit_feedback',
  TRIGGER_EVALUATION: 'trigger_evaluation',
  VIEW_ALL_FEEDBACK: 'view_all_feedback',

  // Reports
  VIEW_TEAM_REPORTS: 'view_team_reports',
  VIEW_PROJECT_REPORTS: 'view_project_reports',
  VIEW_ORG_REPORTS: 'view_org_reports',
};

/** Map role → permissions for UX gating */
export const ROLE_PERMISSIONS = {
  [ROLES.DEVELOPER]: [
    PERMISSIONS.VIEW_TASK,
    PERMISSIONS.MANAGE_TASK,
  ],
  [ROLES.LEAD]: [
    PERMISSIONS.VIEW_TASK,
    PERMISSIONS.MANAGE_TASK,
    PERMISSIONS.MANAGE_STORY,
    PERMISSIONS.VIEW_TEAM_CODE_QUALITY,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.TRIGGER_EVALUATION,
    PERMISSIONS.VIEW_TEAM_REPORTS,
  ],
  [ROLES.PM]: [
    PERMISSIONS.CREATE_PROJECT,
    PERMISSIONS.MANAGE_PROJECT,
    PERMISSIONS.VIEW_PROJECT,
    PERMISSIONS.MANAGE_SPRINT,
    PERMISSIONS.MANAGE_STORY,
    PERMISSIONS.MANAGE_TASK,
    PERMISSIONS.VIEW_PROJECT_CODE_QUALITY,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.TRIGGER_EVALUATION,
    PERMISSIONS.VIEW_PROJECT_REPORTS,
  ],
  [ROLES.QA]: [
    PERMISSIONS.VIEW_TASK,
    PERMISSIONS.VIEW_PROJECT_CODE_QUALITY,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.VIEW_TEAM_REPORTS,
  ],
  [ROLES.DEVOPS]: [
    PERMISSIONS.MANAGE_CICD,
    PERMISSIONS.VIEW_DEPLOYMENTS,
    PERMISSIONS.MANAGE_INCIDENTS,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.VIEW_PROJECT_REPORTS,
  ],
  [ROLES.HR]: [
    PERMISSIONS.MANAGE_EMPLOYEES,
    PERMISSIONS.MANAGE_TEAMS,
    PERMISSIONS.VIEW_ORGANIZATION,
    PERMISSIONS.VIEW_ALL_PERFORMANCE,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.TRIGGER_EVALUATION,
    PERMISSIONS.VIEW_ALL_FEEDBACK,
    PERMISSIONS.VIEW_ORG_REPORTS,
  ],
  [ROLES.CEO]: [
    PERMISSIONS.VIEW_ORGANIZATION,
    PERMISSIONS.CREATE_PROJECT,
    PERMISSIONS.VIEW_ALL_PERFORMANCE,
    PERMISSIONS.SUBMIT_FEEDBACK,
    PERMISSIONS.TRIGGER_EVALUATION,
    PERMISSIONS.VIEW_ALL_FEEDBACK,
    PERMISSIONS.VIEW_ORG_REPORTS,
    PERMISSIONS.VIEW_DEPLOYMENTS,
  ],
};

/** Sidebar navigation items per role */
export const ROLE_NAV = {
  [ROLES.DEVELOPER]: [
    { label: 'Dashboard', to: '/developer/dashboard', icon: 'LayoutDashboard' },
    { label: 'My Tasks', to: '/developer/tasks', icon: 'CheckSquare' },
    { label: 'Board', to: '/developer/board', icon: 'Kanban' },
    { label: 'Projects', to: '/developer/projects', icon: 'FolderKanban' },
    { label: 'Sprints', to: '/developer/sprints', icon: 'Zap' },
    { label: 'Pull Requests', to: '/developer/pull-requests', icon: 'GitPullRequest' },
    { label: 'Code Quality', to: '/developer/code-quality', icon: 'ShieldCheck' },
    { label: 'Performance', to: '/developer/performance', icon: 'TrendingUp' },
  ],
  [ROLES.LEAD]: [
    { label: 'Dashboard', to: '/lead/dashboard', icon: 'LayoutDashboard' },
    { label: 'My Team', to: '/lead/team', icon: 'Users' },
    { label: 'Performance', to: '/lead/performance', icon: 'TrendingUp' },
    { label: 'Code Quality', to: '/lead/code-quality', icon: 'ShieldCheck' },
    { label: 'Feedback', to: '/lead/feedback', icon: 'MessageSquare' },
  ],
  [ROLES.PM]: [
    { label: 'Dashboard', to: '/pm/dashboard', icon: 'LayoutDashboard' },
    { label: 'Projects', to: '/pm/projects', icon: 'FolderKanban' },
    { label: 'Analytics', to: '/pm/analytics', icon: 'BarChart3' },
    { label: 'Performance', to: '/pm/performance', icon: 'TrendingUp' },
    { label: 'Feedback', to: '/pm/feedback', icon: 'MessageSquare' },
  ],
  [ROLES.QA]: [
    { label: 'Dashboard', to: '/qa/dashboard', icon: 'LayoutDashboard' },
    { label: 'Tests', to: '/qa/tests', icon: 'TestTube' },
    { label: 'Bugs', to: '/qa/bugs', icon: 'Bug' },
    { label: 'Code Quality', to: '/qa/code-quality', icon: 'ShieldCheck' },
    { label: 'Feedback', to: '/qa/feedback', icon: 'MessageSquare' },
  ],
  [ROLES.DEVOPS]: [
    { label: 'Dashboard', to: '/devops/dashboard', icon: 'LayoutDashboard' },
    { label: 'Pipelines', to: '/devops/pipelines', icon: 'GitBranch' },
    { label: 'Deployments', to: '/devops/deployments', icon: 'Rocket' },
    { label: 'Incidents', to: '/devops/incidents', icon: 'AlertTriangle' },
    { label: 'Code Quality', to: '/devops/code-quality', icon: 'ShieldCheck' },
    { label: 'Feedback', to: '/devops/feedback', icon: 'MessageSquare' },
  ],
  [ROLES.HR]: [
    { label: 'Dashboard', to: '/hr/dashboard', icon: 'LayoutDashboard' },
    { label: 'Employees', to: '/hr/employees', icon: 'UserCircle' },
    { label: 'Teams', to: '/hr/teams', icon: 'Users' },
    { label: 'Performance', to: '/hr/performance', icon: 'TrendingUp' },
    { label: 'Feedback', to: '/hr/feedback', icon: 'MessageSquare' },
    { label: 'Reports', to: '/hr/reports', icon: 'FileBarChart' },
  ],
  [ROLES.CEO]: [
    { label: 'Dashboard', to: '/ceo/dashboard', icon: 'LayoutDashboard' },
    { label: 'Organization', to: '/ceo/organization', icon: 'Building2' },
    { label: 'Projects', to: '/ceo/projects', icon: 'FolderKanban' },
    { label: 'Teams', to: '/ceo/teams', icon: 'Users' },
    { label: 'Performance', to: '/ceo/performance', icon: 'TrendingUp' },
    { label: 'Risk', to: '/ceo/risk', icon: 'AlertCircle' },
    { label: 'Reports', to: '/ceo/reports', icon: 'FileBarChart' },
  ],
};

/** Return the home route for a given role */
export function getRoleDashboardPath(role) {
  const r = role?.toUpperCase();
  const map = {
    DEVELOPER: '/developer/dashboard',
    LEAD: '/lead/dashboard',
    PM: '/pm/dashboard',
    QA: '/qa/dashboard',
    DEVOPS: '/devops/dashboard',
    HR: '/hr/dashboard',
    CEO: '/ceo/dashboard',
  };
  return map[r] || '/login';
}
