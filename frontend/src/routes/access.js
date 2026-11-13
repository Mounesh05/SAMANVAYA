import { ROLES } from '../utils/constants';
import { PERMISSIONS as P, hasAnyPermission, TEAM_LIST_PERMISSIONS, TRANSFER_FOR_OTHERS_PERMISSIONS } from '../auth/permissions';

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
 *              `convertIn` names what would let it become permission-based.
 *              CR-008 removed the admin bypass: admins get only what their
 *              role and admin permissions give.
 *
 * `menuRoles` (optional) narrows who sees the page in the sidebar, and
 * `menuAnyOf` (optional) adds permission holders to it. A page is never shown
 * in the menu to someone who cannot open it.
 */
const { CEO, HR, PM, LEAD, DEVELOPER, QA, DEVOPS } = ROLES;
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
  // CR-002: QA works the Review column, so the Board is in their menu.
  board: { anyOf: [P.TRANSITION_TASK], menuRoles: [DEVELOPER, LEAD, PM, QA] },

  // CR-001: reporters (Developers) see their own reports; DevOps/Lead/CEO see all.
  incidents: { anyOf: [P.VIEW_INCIDENTS, P.CREATE_INCIDENT] },
  // CR-010: people who request or approve account changes (admins, HR).
  approvals: { anyOf: [P.MANAGE_EMPLOYEES, P.MANAGE_USERS] },
  cicdLogs: { anyOf: [P.ANALYZE_CICD_LOGS] },
  pullRequests: { anyOf: [P.ANALYZE_PR_RISK] },

  // Quality (CR-002).
  codeQuality: { anyOf: [P.VIEW_CODE_QUALITY] },
  tests: { anyOf: [P.MANAGE_TEST_CASES] },
  bugs: { anyOf: [P.VIEW_DEFECTS] },

  // Delivery infrastructure (CR-003): data is limited to the user's projects.
  pipelines: { anyOf: [P.VIEW_PIPELINES] },
  deployments: { anyOf: [P.VIEW_DEPLOYMENTS] },
  // Repository links and CI setup. CR-001: not a Developer task; "Sync PR"
  // stays on Pull Requests.
  githubSync: { anyOf: [P.MANAGE_REPOSITORY_LINK], menuRoles: [LEAD, DEVOPS] },

  // People data.
  employees: { anyOf: [P.VIEW_EMPLOYEE_DIRECTORY, P.VIEW_ORGANIZATION_DATA, P.MANAGE_EMPLOYEES] },
  audit: { anyOf: [P.VIEW_AUDIT_LOGS] },
  feedback: { anyOf: [P.VIEW_ROLE_FEEDBACK] },
  // CR-001: a Developer's own AI evaluation is shown on the Performance page.
  // CR-006: HR sees outcomes on Performance; the backend refuses HR every
  // evaluation read, so outcome access no longer opens this page.
  evaluation: { anyOf: [P.TRIGGER_AI_EVALUATION], menuRoles: [CEO, LEAD] },

  // Not yet expressed as permissions.
  projects: { roles: [...DELIVERY, CEO, HR], menuRoles: [...DELIVERY, CEO], convertIn: 'CR-005 (PM)' },
  // CR-001: Developers cannot list teams (the API refuses); they open their own.
  // CR-008: mirrors GET /api/teams; admins manage teams through MANAGE_TEAMS.
  teams: { anyOf: [...TEAM_LIST_PERMISSIONS, P.MANAGE_TEAMS], menuRoles: [CEO, LEAD], menuAnyOf: [P.MANAGE_TEAMS] },
  teamDetail: { roles: [PM, LEAD, DEVELOPER, HR, CEO], menuRoles: [DEVELOPER], convertIn: 'CR-004 (Lead)' },
  // CR-001: Developers request and follow their own transfers.
  // CR-004: Leads approve transfers at their manager stage, so it's in their menu.
  // CR-008: everyone who can request a transfer or act on others' requests.
  transfers: { anyOf: [P.REQUEST_TRANSFER, ...TRANSFER_FOR_OTHERS_PERMISSIONS], menuRoles: [HR, DEVELOPER, LEAD] },
  // CR-001..004: blocked for Developers, QA, DevOps and Leads. Its CSV exports are
  // made-up numbers until real reporting arrives in CR-007.
  // CR-011: report downloads need EXPORT_DATA (CEO, PM, HR and admins); each
  // report also needs the matching view right, checked by the backend.
  reports: { anyOf: [P.EXPORT_DATA], menuRoles: [CEO, PM, HR] },
});

function roleOf(user) {
  return user?.role?.toUpperCase();
}

export function canOpenPage(user, page) {
  const entry = PAGE_ACCESS[page];
  const role = roleOf(user);
  if (!entry || !role) return false;
  if (entry.anyOf) return hasAnyPermission(user, entry.anyOf);
  return entry.roles.includes(role);  // CR-008: no admin bypass
}

export function showInMenu(user, page) {
  const entry = PAGE_ACCESS[page];
  if (!canOpenPage(user, page)) return false;
  if (!entry.menuRoles) return true;
  if (entry.menuAnyOf && hasAnyPermission(user, entry.menuAnyOf)) return true;
  return entry.menuRoles.includes(roleOf(user));
}
