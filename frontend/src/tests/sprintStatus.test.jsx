/**
 * Sprints page: PM and Lead (CREATE_SPRINT) start a planning sprint and
 * complete an active one; other roles only see Plan vs Reality.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { SprintsPage } from '../pages/sprints/SprintsPage';
import { sprintsApi } from '../api/sprints.api';
import { projectsApi } from '../api/projects.api';
import { useAuthStore } from '../store/useAuthStore';
import { roleUser } from './utils/roleUser';

vi.mock('../api/sprints.api', () => ({
  sprintsApi: { listByProject: vi.fn(), getHealth: vi.fn(), create: vi.fn(), changeStatus: vi.fn() },
}));
vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));

const PLANNING = { id: 'SPR-F6DD37EB', name: 'sprint1', status: 'planning', goal: 'Expense Tracker MVP', start_date: '2026-11-15', end_date: '2026-11-16' };
const ACTIVE = { ...PLANNING, id: 'SPR-0A1B2C3D', name: 'sprint2', status: 'active' };

let client;
function renderPage(user) {
  useAuthStore.setState({ user });
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={client}><SprintsPage /></QueryClientProvider></MemoryRouter>);
}
const rowOf = async (name) => (await screen.findByText(name)).closest('tr');

beforeEach(() => {
  vi.resetAllMocks();
  projectsApi.list.mockResolvedValue([{ id: 'PRJ-BFAAEA0A', name: 'Expense Tracker' }]);
  sprintsApi.listByProject.mockResolvedValue([PLANNING, ACTIVE]);
  sprintsApi.changeStatus.mockResolvedValue({});
});
afterEach(() => { cleanup(); client?.clear(); });

it('lets the PM start a planning sprint', async () => {
  renderPage(roleUser('PM', { employee_id: 'E3', name: 'Shreyas K T' }));
  const row = await rowOf('sprint1');
  expect(within(row).queryByRole('button', { name: 'Complete sprint' })).not.toBeInTheDocument();
  fireEvent.click(within(row).getByRole('button', { name: 'Start sprint' }));
  await waitFor(() => expect(sprintsApi.changeStatus).toHaveBeenCalledWith('SPR-F6DD37EB', 'active'));
});

it('asks before completing an active sprint', async () => {
  renderPage(roleUser('LEAD', { employee_id: 'E4', name: 'Arjun M C', team_id: 'T1' }));
  const row = await rowOf('sprint2');
  expect(within(row).queryByRole('button', { name: 'Start sprint' })).not.toBeInTheDocument();
  fireEvent.click(within(row).getByRole('button', { name: 'Complete sprint' }));
  expect(sprintsApi.changeStatus).not.toHaveBeenCalled();
  const dialog = screen.getByText(/cannot be undone/).closest('[role="dialog"]') || document.body;
  const confirm = within(dialog).getAllByRole('button', { name: 'Complete sprint' }).at(-1);
  fireEvent.click(confirm);
  await waitFor(() => expect(sprintsApi.changeStatus).toHaveBeenCalledWith('SPR-0A1B2C3D', 'completed'));
});

it('shows why a start was refused', async () => {
  sprintsApi.changeStatus.mockRejectedValue(new Error('Sprint sprint2 is already active in this project. Complete it first.'));
  renderPage(roleUser('PM', { employee_id: 'E3' }));
  fireEvent.click(within(await rowOf('sprint1')).getByRole('button', { name: 'Start sprint' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('already active in this project');
});

it.each(['CEO', 'HR', 'DEVELOPER', 'QA', 'DEVOPS'])('shows no sprint controls to %s', async (role) => {
  renderPage(roleUser(role, { employee_id: 'E10', team_id: 'T1' }));
  await rowOf('sprint1');
  expect(screen.queryByRole('button', { name: 'Start sprint' })).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Complete sprint' })).not.toBeInTheDocument();
  expect(screen.getAllByRole('button', { name: 'Plan vs Reality' })).toHaveLength(2);
});
