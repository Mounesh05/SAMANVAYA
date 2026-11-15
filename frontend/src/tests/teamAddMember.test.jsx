/**
 * Team page "Add member": admins (ASSIGN_PROJECT) place employees who have no
 * team yet. Everyone else sees no button; people in another team, CEO and HR
 * are never offered.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { TeamDetailPage } from '../pages/teams/TeamDetailPage';
import { teamsApi } from '../api/teams.api';
import { employeesApi } from '../api/employees.api';
import { useAuthStore } from '../store/useAuthStore';
import { roleUser } from './utils/roleUser';
import { canOpenPage } from '../routes/access';

vi.mock('../api/teams.api', () => ({
  teamsApi: { getById: vi.fn(), getMembers: vi.fn(), addMember: vi.fn() },
}));
vi.mock('../api/employees.api', () => ({ employeesApi: { list: vi.fn() } }));

const TEAM = { team_id: 'T1', name: 'Expense Tracker Team', team_lead_name: 'Arjun MC', project_ids: [] };
const LEAD = { employee_id: 'E4', name: 'Arjun MC', role: 'LEAD', email: 'lead@example.com', team_id: 'T1', is_team_lead: true };
const EMPLOYEES = [
  { employee_id: 'E1', name: 'Mallikarjuna C', role: 'CEO', team_id: null, is_active: true },
  { employee_id: 'E3', name: 'Shreyas K T', role: 'PM', team_id: '', is_active: true },
  LEAD,
  { employee_id: 'E5', name: 'Arjun S R', role: 'DEVELOPER', team_id: '', is_active: true },
  { employee_id: 'E7', name: 'Kiran P', role: 'DEVELOPER', team_id: 'T2', is_active: true },
  { employee_id: 'E8', name: 'Ravi N', role: 'HR', team_id: null, is_active: true },
  { employee_id: 'E9', name: 'Deepa V', role: 'QA', team_id: '', is_active: false },
];

let client;
function renderPage(user) {
  useAuthStore.setState({ user });
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={['/teams/T1']}>
      <QueryClientProvider client={client}>
        <Routes><Route path="/teams/:teamId" element={<TeamDetailPage />} /></Routes>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.resetAllMocks();
  teamsApi.getById.mockResolvedValue(TEAM);
  teamsApi.getMembers.mockResolvedValue([LEAD]);
  employeesApi.list.mockResolvedValue(EMPLOYEES);
  teamsApi.addMember.mockResolvedValue({ message: 'ok' });
});
afterEach(() => { cleanup(); client?.clear(); });

it('lets an admin add an employee who has no team', async () => {
  renderPage(roleUser('DEVOPS', { employee_id: 'E2', name: 'Mounesh S D', is_admin: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add member' }));

  const select = await screen.findByLabelText('Employee');
  const offered = [...select.querySelectorAll('option')].map((o) => o.value).filter(Boolean);
  // No CEO/HR, nobody already in a team, no inactive employee.
  expect(offered).toEqual(['E3', 'E5']);
  expect(screen.getByRole('button', { name: 'Add to team' })).toBeDisabled();

  fireEvent.change(select, { target: { value: 'E5' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add to team' }));
  await waitFor(() => expect(teamsApi.addMember).toHaveBeenCalledWith('T1', 'E5'));
  await waitFor(() => expect(screen.queryByLabelText('Employee')).not.toBeInTheDocument());
  expect(employeesApi.list).toHaveBeenCalledWith({ is_active: true });
});

it('shows the server message when adding fails', async () => {
  teamsApi.addMember.mockRejectedValue(new Error('Insufficient permissions to assign team members'));
  renderPage(roleUser('DEVOPS', { employee_id: 'E2', is_admin: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add member' }));
  fireEvent.change(await screen.findByLabelText('Employee'), { target: { value: 'E3' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add to team' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Insufficient permissions to assign team members');
});

it('explains when nobody is free to add', async () => {
  employeesApi.list.mockResolvedValue([LEAD, EMPLOYEES[4]]);
  renderPage(roleUser('DEVOPS', { employee_id: 'E2', is_admin: true }));
  fireEvent.click(await screen.findByRole('button', { name: 'Add member' }));
  expect(await screen.findByText(/Everyone is already in a team/)).toBeInTheDocument();
});

it.each(['CEO', 'PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS', 'HR'])('hides the button from a non-admin %s', async (role) => {
  renderPage(roleUser(role, { employee_id: 'E10', team_id: 'T1' }));
  expect(await screen.findByText('Expense Tracker Team')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Add member' })).not.toBeInTheDocument();
  expect(employeesApi.list).not.toHaveBeenCalled();
});

it.each(['CEO', 'HR', 'PM', 'LEAD', 'DEVELOPER', 'QA', 'DEVOPS'])('lets a %s open the team page, as the backend does', (role) => {
  expect(canOpenPage(roleUser(role, { employee_id: 'E10', team_id: 'T1' }), 'teamDetail')).toBe(true);
});

it('lets a DevOps admin open a team to add members', () => {
  expect(canOpenPage(roleUser('DEVOPS', { employee_id: 'E2', is_admin: true }), 'teamDetail')).toBe(true);
});
