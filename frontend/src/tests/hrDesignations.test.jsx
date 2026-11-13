/**
 * CR-009: HR designation field, as the UI presents it.
 * Backend counterparts live in backend/tests/test_hr_designation_field.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { useAuthStore } from '../store/useAuthStore';
import { designationLabel } from '../utils/constants';
import { EmployeesPage } from '../pages/employees/EmployeesPage';
import { employeesApi } from '../api/employees.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/employees.api', () => ({
  employeesApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));
vi.mock('../api/teams.api', () => ({ teamsApi: { list: vi.fn().mockResolvedValue([]) } }));

const ADMIN = roleUser('DEVELOPER', { employee_id: 'ADM-1', is_admin: true });
const HR = roleUser('HR', { employee_id: 'HR-1' });
const EMPLOYEES = [
  { employee_id: 'HR-2', name: 'Hana', email: 'h@x.test', role: 'HR', dept: 'People', is_active: true, is_admin: false, designation: null },
  { employee_id: 'HR-3', name: 'Omar', email: 'o@x.test', role: 'HR', dept: 'People', is_active: true, is_admin: false, designation: 'HR_OPERATIONS' },
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

async function openEdit(name) {
  const row = (await screen.findByText(name)).closest('tr');
  await userEvent.setup().click(row.querySelector('button[title="Edit Employee"]'));
  return screen.findByLabelText('HR designation');
}

beforeEach(() => {
  vi.clearAllMocks();
  employeesApi.list.mockResolvedValue(EMPLOYEES);
  employeesApi.update.mockResolvedValue(EMPLOYEES[0]);
});

describe('CR-009 designation rights and labels', () => {
  it('lets admins assign designations, not base HR', () => {
    expect(hasPermission(ADMIN, PERMISSIONS.MANAGE_HR_DESIGNATIONS)).toBe(true);
    expect(hasPermission(HR, PERMISSIONS.MANAGE_HR_DESIGNATIONS)).toBe(false);
  });

  it('shows readable names and leaves other text alone', () => {
    expect(designationLabel('HR_OPERATIONS')).toBe('HR Operations');
    expect(designationLabel('Chief Executive')).toBe('Chief Executive');
    expect(designationLabel(null)).toBe('');
  });
});

describe('CR-009 Employees page', () => {
  it('shows the designation in the list', async () => {
    renderEmployees(ADMIN);
    expect(await screen.findByText(/HR Operations/)).toBeInTheDocument();
  });

  it('lets an admin assign a designation and sends only that change', async () => {
    renderEmployees(ADMIN);
    const select = await openEdit('Hana');
    expect(select).not.toBeDisabled();
    const user = userEvent.setup();
    await user.selectOptions(select, 'RECRUITER');
    await user.click(screen.getByRole('button', { name: /save|update/i }));
    await waitFor(() => expect(employeesApi.update).toHaveBeenCalledWith('HR-2', expect.objectContaining({ designation: 'RECRUITER' })));
  });

  it('shows base HR the designation read-only and never sends it', async () => {
    renderEmployees(HR);
    const select = await openEdit('Omar');
    expect(select).toBeDisabled();
    await userEvent.setup().click(screen.getByRole('button', { name: /save|update/i }));
    await waitFor(() => expect(employeesApi.update).toHaveBeenCalled());
    expect(employeesApi.update.mock.calls[0][1]).not.toHaveProperty('designation');
  });
});
