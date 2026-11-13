/**
 * CR-008: Platform Admin, as the UI presents it.
 * Backend counterparts live in backend/tests/test_admin_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { canOpenPage, showInMenu } from '../routes/access';
import { useAuthStore } from '../store/useAuthStore';
import { EmployeesPage } from '../pages/employees/EmployeesPage';
import { employeesApi } from '../api/employees.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/employees.api', () => ({
  employeesApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));
vi.mock('../api/teams.api', () => ({ teamsApi: { list: vi.fn().mockResolvedValue([]) } }));

const DEV_ADMIN = roleUser('DEVELOPER', { employee_id: 'ADM-1', is_admin: true });
const HR = roleUser('HR', { employee_id: 'HR-1' });
const EMPLOYEES = [
  { employee_id: 'CEO-1', name: 'Chief', email: 'c@x.test', role: 'CEO', dept: 'Executive', is_active: true, is_admin: true },
  { employee_id: 'DEV-1', name: 'Dana', email: 'd@x.test', role: 'DEVELOPER', dept: 'Engineering', is_active: true, is_admin: false },
  { employee_id: 'ADM-1', name: 'Ada', email: 'a@x.test', role: 'DEVELOPER', dept: 'IT', is_active: true, is_admin: true },
];

function renderEmployees(user) {
  useAuthStore.setState({ user, token: 't', isAuthenticated: true });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter><EmployeesPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  employeesApi.list.mockResolvedValue(EMPLOYEES);
});

describe('CR-008 admin rights and pages', () => {
  it('gives admins platform rights, not people decisions', () => {
    expect(hasPermission(DEV_ADMIN, PERMISSIONS.MANAGE_TEAMS)).toBe(true);
    expect(hasPermission(DEV_ADMIN, PERMISSIONS.TRIGGER_AI_EVALUATION)).toBe(false);
    expect(hasPermission(DEV_ADMIN, PERMISSIONS.MANAGE_EVALUATION_POLICY)).toBe(false);
  });

  it('opens no extra role-based page just for being admin', () => {
    expect(canOpenPage(DEV_ADMIN, 'reports')).toBe(false);
    expect(canOpenPage(DEV_ADMIN, 'ceoRisk')).toBe(false);
    expect(canOpenPage(DEV_ADMIN, 'evaluation')).toBe(false);
  });

  it('keeps Teams for admins through MANAGE_TEAMS, in the menu too', () => {
    expect(canOpenPage(DEV_ADMIN, 'teams')).toBe(true);
    expect(showInMenu(DEV_ADMIN, 'teams')).toBe(true);
  });

  it('keeps Teams and Transfers open for the roles that had them', () => {
    for (const role of ['PM', 'LEAD', 'HR', 'CEO']) expect(canOpenPage(roleUser(role), 'teams')).toBe(true);
    for (const role of ['HR', 'LEAD', 'DEVELOPER']) expect(canOpenPage(roleUser(role), 'transfers')).toBe(true);
  });
});

describe('CR-008 Employees page admin control', () => {
  it('lets an admin make someone an admin', async () => {
    employeesApi.update.mockResolvedValue({ ...EMPLOYEES[1], is_admin: true });
    renderEmployees(DEV_ADMIN);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Make Dana an admin' }));
    await waitFor(() => expect(employeesApi.update).toHaveBeenCalledWith('DEV-1', { is_admin: true }));
  });

  it("offers removing the CEO's admin rights, but not your own", async () => {
    renderEmployees(DEV_ADMIN);
    expect(await screen.findByRole('button', { name: 'Remove admin rights from Chief' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /admin rights from Ada|Make Ada an admin/ })).not.toBeInTheDocument();
  });

  it('shows the backend refusal for the last admin', async () => {
    employeesApi.update.mockRejectedValue({ response: { data: { detail: 'This is the last active admin.' } } });
    renderEmployees(DEV_ADMIN);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Remove admin rights from Chief' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('last active admin');
  });

  it('never shows the admin control to HR', async () => {
    renderEmployees(HR);
    expect(await screen.findByText('Dana')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /an admin|admin rights/ })).not.toBeInTheDocument();
  });
});
