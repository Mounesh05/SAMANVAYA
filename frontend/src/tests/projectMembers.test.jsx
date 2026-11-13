/**
 * CR-013: project Members panel. Backend counterparts live in
 * backend/tests/test_pm_projects.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ProjectMembersPanel } from '../pages/projects/ProjectMembersPanel';
import { projectsApi } from '../api/projects.api';

vi.mock('../api/projects.api', () => ({
  projectsApi: { listMembers: vi.fn(), addMember: vi.fn(), removeMember: vi.fn() },
}));

const MEMBERS = [
  { employee_id: 'PM-1', name: 'Priya', role: 'PM', link: 'assigned' },
  { employee_id: 'DEV-1', name: 'Dana', role: 'DEVELOPER', link: 'assigned' },
  { employee_id: 'DEV-T', name: 'Theo', role: 'DEVELOPER', link: 'team' },
];

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={queryClient}><ProjectMembersPanel projectId="P1" /></QueryClientProvider>);
}

beforeEach(() => vi.clearAllMocks());

describe('CR-013 Members panel', () => {
  it('lets a manager add and remove assigned members', async () => {
    projectsApi.listMembers.mockResolvedValue({ members: MEMBERS, can_manage: true });
    projectsApi.addMember.mockResolvedValue({ changed: true });
    projectsApi.removeMember.mockResolvedValue({ changed: true });
    renderPanel();
    const user = userEvent.setup();
    expect(await screen.findByText('Theo')).toBeInTheDocument();
    // Team members are on the project through their team, so there is no Remove for them.
    expect(screen.queryByRole('button', { name: /Remove Theo/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Remove Dana/ }));
    await waitFor(() => expect(projectsApi.removeMember).toHaveBeenCalledWith('P1', 'DEV-1'));
    await user.type(screen.getByLabelText('Employee ID to add'), 'DEV-2');
    await user.click(screen.getByRole('button', { name: 'Add member' }));
    await waitFor(() => expect(projectsApi.addMember).toHaveBeenCalledWith('P1', 'DEV-2'));
  });

  it('is read-only for people who cannot manage the project', async () => {
    projectsApi.listMembers.mockResolvedValue({ members: MEMBERS, can_manage: false });
    renderPanel();
    expect(await screen.findByText('Dana')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Add member' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Remove/ })).not.toBeInTheDocument();
  });

  it('shows the backend reason when a change is refused', async () => {
    projectsApi.listMembers.mockResolvedValue({ members: MEMBERS, can_manage: true });
    projectsApi.addMember.mockRejectedValue({ response: { data: { detail: 'Only the CEO or an admin can assign project managers' } } });
    renderPanel();
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Employee ID to add'), 'PM-2');
    await user.click(screen.getByRole('button', { name: 'Add member' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('assign project managers');
  });
});
