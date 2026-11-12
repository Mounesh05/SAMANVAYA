import { ROLES } from '../utils/constants';
import { PERMISSIONS as P, hasAnyPermission } from '../auth/permissions';

/**
 * Single source of page access (CR-001). The router (<RoleGuard page="...">)
 * and the sidebar both read this table.
 *
 * Each page is guarded in one of two ways:
 *
 *   anyOf      the backend permissions that mean "may use this page"; the user
 *              needs at least one (read from /api/auth/me). No admin bypass:
 *              admin rights are already part of the permission list.
 *   roles      a role list, for pages whose capability has no permission yet.
 *              `convertIn` names the change request that defines it. Until
 *              then the legacy admin bypass still applies to these pages.
 *
 * `menuRoles` (optional) narrows who sees the page in the sidebar. A page is
 * never shown in the menu to someone who cannot open it.
 */
const { CEO, HR, PM, LEAD, DEVELOPER, QA, DEVOPS } = ROLES;
const ALL = Object.values(ROLES);
const DELIVERY = [PM, LEAD, DEVELOPER, QA, DEVOPS];

export const PAGE_ACCESS = Object.freeze({
  // Role dashboards are persona views, deliberately keyed by role.
  developerDashboard: { roles: [DEVELOPER], persona: true },
  leadDashboard: { roles: [LEAD], persona: true },
  pmDashboard: { roles: [PM], persona: true },
  qaDashboard: { roles: [QA, CEO, PM, LEAD, DEVOPS], persona: true },
  devopsDashboard: { roles: [DEVOPS], persona: true },
  hrDashboard: { roles: [HR], persona: true },
  ceoDashboard: { roles: [CEO], persona: true },
  ceoQuality: { roles: [CEO], persona: true },
  ceoRisk: { roles: [CEO], persona: true },
  ceoOrganization: { roles: [CEO], persona: true },

  // Everyone's own data.
  performance: { anyOf: [P.VIEW_OWN_DATA] },
  profile: { anyOf: [P.VIEW_OWN_DATA], menuRoles: [] },

  // Delivery work items: for people who move work through the workflow.
  // CR-001: Sprints are read-only for Developers (no CREATE_SPRINT);
  // Developers propose draft stories (no ACCEPT_STORY).
  sprints: { anyOf: [P.TRANSITION_TASK] },
  stories: { anyOf: [P.TRANSITION_TASK] },
  tasks: { anyOf: [P.TRANSITION_TASK] },
  board: { anyOf: [P.TRANSITION_TASK], menuRoles: [DEVELOPER, LEAD, PM] },

  // CR-001: reporters (Developers) see their own reports; DevOps/Lead/CEO see all.
  incidents: { anyOf: [P.VIEW_INCIDENTS, P.CREATE_INCIDENT] },
  cicdLogs: { anyOf: [P.ANALYZE_CICD_LOGS] },
  pullRequests: { anyOf: [P.ANALYZE_PR_RISK] },

  // People data.
  employees: { anyOf: [P.VIEW_EMPLOYEE_DIRECTORY, P.VIEW_ORGANIZATION_DATA, P.MANAGE_EMPLOYEES] },
  audit: { anyOf: [P.VIEW_AUDIT_LOGS] },
  feedback: { anyOf: [P.VIEW_ROLE_FEEDBACK] },
  // CR-001: a Developer's own AI evaluation is shown on the Performance page.
  evaluation: {
    anyOf: [P.TRIGGER_AI_EVALUATION, P.VIEW_PERFORMANCE_OUTCOMES],
    menuRoles: [CEO, LEAD],
  },

  // Not yet expressed as permissions.
  projects: { roles: [...DELIVERY, CEO, HR], menuRoles: [...DELIVERY, CEO], convertIn: 'CR-005 (PM)' },
  codeQuality: { roles: [DEVELOPER, QA, LEAD, DEVOPS], convertIn: 'CR-002 (QA)' },
  tests: { roles: [QA], convertIn: 'CR-002 (QA)' },
  bugs: { roles: [QA, DEVELOPER, DEVOPS, LEAD, PM, CEO], convertIn: 'CR-002 (QA)' },
  pipelines: { roles: [DEVOPS, QA, LEAD], convertIn: 'CR-003 (DevOps)' },
  deployments: { roles: [DEVOPS, LEAD], convertIn: 'CR-003 (DevOps)' },
  // CR-001: integration setup is not a Developer task; "Sync PR" stays on Pull Requests.
  githubSync: { roles: [CEO, PM, LEAD, DEVOPS], menuRoles: [LEAD, DEVOPS], convertIn: 'CR-003 (DevOps)' },
  // CR-001: Developers cannot list teams (the API refuses); they open their own.
  teams: { roles: [PM, LEAD, HR, CEO], menuRoles: [CEO, LEAD], convertIn: 'CR-004 (Lead)' },
  teamDetail: { roles: [PM, LEAD, DEVELOPER, HR, CEO], menuRoles: [DEVELOPER], convertIn: 'CR-004 (Lead)' },
  // CR-001: Developers request and follow their own transfers.
  transfers: { roles: [HR, LEAD, DEVELOPER], menuRoles: [HR, DEVELOPER], convertIn: 'CR-006 (HR)' },
  // CR-001: org-level exports are blocked for Developers (was open by URL to everyone).
  reports: { roles: ALL.filter((role) => role !== DEVELOPER), menuRoles: [CEO, PM], convertIn: 'CR-007 (CEO)' },
});

function roleOf(user) {
  return user?.role?.toUpperCase();
}

export function canOpenPage(user, page) {
  const entry = PAGE_ACCESS[page];
  const role = roleOf(user);
  if (!entry || !role) return false;
  if (entry.anyOf) return hasAnyPermission(user, entry.anyOf);
  // Role-based pages keep the legacy admin bypass until their change request.
  return Boolean(user?.is_admin) || entry.roles.includes(role);
}

export function showInMenu(user, page) {
  const entry = PAGE_ACCESS[page];
  if (!canOpenPage(user, page)) return false;
  if (!entry.menuRoles) return true;
  if (entry.roles && user?.is_admin) return true;
  return entry.menuRoles.includes(roleOf(user));
}
