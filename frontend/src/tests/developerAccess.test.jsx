/**
 * CR-001: Developer access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_developer_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PAGE_ACCESS, canOpenPage, showInMenu } from '../routes/access';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { useAuthStore } from '../store/useAuthStore';
import { Sidebar } from '../components/layout/Sidebar';
import { StoriesPage } from '../pages/stories/StoriesPage';
import { TransferRequestForm } from '../pages/transfers/TransferRequestForm';
import { storiesApi } from '../api/stories.api';
import { projectsApi } from '../api/projects.api';
import { sprintsApi } from '../api/sprints.api';
import { employeesApi } from '../api/employees.api';
import { teamsApi } from '../api/teams.api';
import { transfersApi } from '../api/transfers.api';
import { roleUser } from './utils/roleUser';
import rolePermissions from './fixtures/rolePermissions.json';

vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../api/sprints.api', () => ({ sprintsApi: { listByProject: vi.fn() } }));
vi.mock('../api/stories.api', () => ({
  storiesApi: { listBySprint: vi.fn(), create: vi.fn(), updateStatus: vi.fn() },
}));
vi.mock('../api/employees.api', () => ({ employeesApi: { list: vi.fn() } }));
vi.mock('../api/teams.api', () => ({ teamsApi: { directory: vi.fn() } }));
vi.mock('../api/transfers.api', () => ({ transfersApi: { createTransfer: vi.fn() } }));

// What /api/auth/me returns for a Developer under CR-001.
// Users exactly as /api/auth/me returns them (fixture checked against the backend).
const DEVELOPER = roleUser('DEVELOPER', { employee_id: 'DEV-1', name: 'Dana Dev', team_id: 'TEAM-A' });
const LEAD = {
  employee_id: 'LEAD-1',
  name: 'Lee Lead',
  role: 'LEAD',
  team_id: 'TEAM-A',
  is_admin: false,
  permissions: ['ACCEPT_STORY', 'CREATE_STORY', 'CREATE_TASK', 'MOVE_TASK', 'APPROVE_TRANSFER_AS_MANAGER'],
};

function renderWithClient(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('CR-001 page access table', () => {
  it('blocks Developer URLs for integration setup, AI Evaluation, Reports and the team list', () => {
    for (const page of ['githubSync', 'evaluation', 'reports', 'teams', 'feedback', 'employees']) {
      expect(canOpenPage(DEVELOPER, page), page).toBe(false);
    }
  });

  it('opens the Developer pages the change request keeps or adds', () => {
    for (const page of [
      'developerDashboard', 'projects', 'sprints', 'stories', 'tasks', 'board', 'bugs',
      'codeQuality', 'pullRequests', 'cicdLogs', 'performance', 'profile', 'transfers', 'teamDetail',
      'incidents',
    ]) {
      expect(canOpenPage(DEVELOPER, page), page).toBe(true);
    }
  });

  it('keeps other roles on Reports as before', () => {
    expect(canOpenPage({ role: 'CEO' }, 'reports')).toBe(true);
    expect(canOpenPage({ role: 'QA' }, 'reports')).toBe(true);
    expect(showInMenu({ role: 'QA' }, 'reports')).toBe(false);
  });

  it('never lists a role in the menu for a page that role cannot open', () => {
    for (const [page, entry] of Object.entries(PAGE_ACCESS)) {
      for (const role of entry.menuRoles ?? []) {
        expect(canOpenPage(roleUser(role), page), `${page} shows ${role} a link it would refuse`).toBe(true);
      }
    }
  });

  it('guards each page either by permissions or by roles with a named follow-up', () => {
    for (const [page, entry] of Object.entries(PAGE_ACCESS)) {
      if (entry.anyOf) {
        for (const permission of entry.anyOf) expect(PERMISSIONS[permission], `${page}: ${permission}`).toBe(permission);
      } else {
        expect(entry.persona || entry.convertIn, `${page} needs persona or convertIn`).toBeTruthy();
      }
    }
  });

  it('keeps every other role on the same permission-guarded pages as before CR-001', () => {
    // Page -> roles that could open it before CR-001 (admins aside).
    const before = {
      performance: ['CEO', 'HR', 'PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'],
      sprints: ['PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'],
      stories: ['PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'],
      tasks: ['PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'],
      board: ['PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'],
      incidents: ['DEVOPS', 'LEAD', 'CEO'],
      cicdLogs: ['DEVOPS', 'QA', 'LEAD', 'DEVELOPER'],
      pullRequests: ['DEVELOPER', 'LEAD', 'QA', 'DEVOPS'],
      employees: ['HR', 'CEO'],
      audit: ['HR', 'CEO'],
      feedback: ['LEAD', 'PM', 'QA', 'DEVOPS', 'HR', 'CEO'],
      evaluation: ['CEO', 'HR', 'LEAD', 'DEVELOPER'],
    };
    // Intended CR-001 changes, Developer only.
    const developerChanges = { incidents: true, evaluation: false };
    for (const [page, roles] of Object.entries(before)) {
      for (const role of Object.keys(rolePermissions).filter((r) => !r.startsWith('_'))) {
        const expected = role === 'DEVELOPER' && page in developerChanges
          ? developerChanges[page]
          : roles.includes(role);
        expect(canOpenPage(roleUser(role), page), `${role} on ${page}`).toBe(expected);
      }
    }
  });
});

describe('CR-001 permission helper', () => {
  it('reads only the backend-issued permission list and has no admin shortcut', () => {
    expect(hasPermission(DEVELOPER, PERMISSIONS.CREATE_TASK)).toBe(true);
    expect(hasPermission(DEVELOPER, PERMISSIONS.ACCEPT_STORY)).toBe(false);
    expect(hasPermission({ role: 'CEO', is_admin: true, permissions: [] }, PERMISSIONS.MANAGE_USERS)).toBe(false);
    expect(hasPermission({ role: 'PM' }, PERMISSIONS.CREATE_PROJECT)).toBe(false);
  });
});

describe('CR-001 Developer sidebar', () => {
  beforeEach(() => useAuthStore.getState().logout());

  it('links "My Team" to the developer\'s own team and offers My Transfers', () => {
    useAuthStore.getState().setAuth('token', DEVELOPER);
    render(<MemoryRouter><Sidebar /></MemoryRouter>);
    expect(screen.getByRole('link', { name: /My Team/i })).toHaveAttribute('href', '/teams/TEAM-A');
    expect(screen.getByRole('link', { name: /My Transfers/i })).toHaveAttribute('href', '/transfers');
    expect(screen.queryByRole('link', { name: /GitHub Sync/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /AI Evaluation/i })).not.toBeInTheDocument();
  });
});

describe('CR-001 draft stories', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    projectsApi.list.mockResolvedValue([{ id: 'PRJ-1', name: 'CampusConnect' }]);
    sprintsApi.listByProject.mockResolvedValue([{ id: 'SPR-1', name: 'Sprint 1' }]);
    employeesApi.list.mockResolvedValue([]);
  });

  it('lets a Developer propose a draft assigned to themselves without loading the employee list', async () => {
    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    storiesApi.listBySprint.mockResolvedValue([]);
    storiesApi.create.mockResolvedValue({ id: 'STY-1', status: 'draft' });
    const user = userEvent.setup();
    renderWithClient(<StoriesPage />);
    await waitFor(() => expect(storiesApi.listBySprint).toHaveBeenCalledWith('SPR-1'));
    await screen.findByText(/No stories found/);

    await user.click(await screen.findByRole('button', { name: 'Propose Story' }));
    await user.type(screen.getByPlaceholderText('Describe the user story'), 'Export sprint report');
    await user.click(screen.getByRole('button', { name: 'Submit Draft' }));

    await waitFor(() => expect(storiesApi.create).toHaveBeenCalled());
    expect(storiesApi.create.mock.calls[0][0]).toMatchObject({
      title: 'Export sprint report', assignee_id: 'DEV-1', project_id: 'PRJ-1', sprint_id: 'SPR-1', points: 3,
    });
    expect(employeesApi.list).not.toHaveBeenCalled();
  });

  it('shows Accept on drafts only to backlog owners', async () => {
    storiesApi.listBySprint.mockResolvedValue([
      { id: 'STY-9', title: 'Proposed idea', status: 'draft', assignee_id: 'DEV-1', points: 2 },
    ]);
    storiesApi.updateStatus.mockResolvedValue({});

    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    const { unmount } = renderWithClient(<StoriesPage />);
    const devRow = (await screen.findByText('STY-9')).closest('tr');
    expect(within(devRow).queryByRole('button', { name: 'Accept' })).not.toBeInTheDocument();
    unmount();

    useAuthStore.setState({ user: LEAD, token: 't', isAuthenticated: true });
    const user = userEvent.setup();
    renderWithClient(<StoriesPage />);
    const leadRow = (await screen.findByText('STY-9')).closest('tr');
    await user.click(within(leadRow).getByRole('button', { name: 'Accept' }));
    await waitFor(() => expect(storiesApi.updateStatus).toHaveBeenCalledWith('STY-9', 'todo'));
  });
});

describe('CR-001 transfer request', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    teamsApi.directory.mockResolvedValue([
      { team_id: 'TEAM-A', name: 'Platform' },
      { team_id: 'TEAM-B', name: 'Payments' },
    ]);
  });

  it('files a Developer\'s own request with the fields the backend expects', async () => {
    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    transfersApi.createTransfer.mockResolvedValue({ id: 'TRF-1' });
    const user = userEvent.setup();
    renderWithClient(<TransferRequestForm />);

    expect(await screen.findByLabelText(/Employee/)).toHaveValue('Dana Dev (DEV-1)');
    expect(screen.queryByRole('option', { name: /Platform/ })).not.toBeInTheDocument(); // own team
    await user.selectOptions(screen.getByLabelText(/Target Team/), 'TEAM-B');
    await user.selectOptions(screen.getByLabelText(/Reason/), 'career_growth');
    await user.type(screen.getByLabelText(/Details/), 'I want to work on payments infrastructure.');
    await user.click(screen.getByRole('button', { name: 'Submit Transfer Request' }));

    await waitFor(() => expect(transfersApi.createTransfer).toHaveBeenCalled());
    expect(transfersApi.createTransfer.mock.calls[0][0]).toEqual({
      employee_id: 'DEV-1',
      requested_team_id: 'TEAM-B',
      reason: 'career_growth',
      justification: 'I want to work on payments infrastructure.',
    });
    expect(employeesApi.list).not.toHaveBeenCalled();
  });
});
