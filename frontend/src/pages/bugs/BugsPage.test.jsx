import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { qaApi } from '../../api/qa.api';
import { useAuthStore } from '../../store/useAuthStore';
import { roleUser } from '../../tests/utils/roleUser';
import { BugsPage } from './BugsPage';

vi.mock('../../api/qa.api', () => ({
  qaApi: {
    getProjects: vi.fn(),
    getDefects: vi.fn(),
    getDefect: vi.fn(),
    createDefect: vi.fn(),
    updateDefect: vi.fn(),
  },
}));
vi.mock('../../store/useAuthStore', () => ({
  useAuthStore: vi.fn(),
}));

const defect = {
  id: 'QAD-1',
  project_id: 'PRJ-1',
  title: 'Event endpoint rejects valid payload',
  description: 'The endpoint returns an unexpected error.',
  steps_to_reproduce: 'Submit a valid event payload.',
  expected_result: 'The event is created.',
  actual_result: 'The endpoint returns 500.',
  severity: 'high',
  priority: 'high',
  status: 'OPEN',
  reporter_name: 'QA Engineer',
  assignee_id: null,
  history: [{ status: 'OPEN', actor_id: 'DEMO-QA', at: '2026-01-01T10:00:00Z' }],
};

function renderBugsPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <BugsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('BugsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Permissions come from /api/auth/me (backend ROLE_PERMISSIONS for QA).
    useAuthStore.mockReturnValue({ user: roleUser('QA') });
    qaApi.getProjects.mockResolvedValue([{ id: 'PRJ-1', name: 'CampusConnect' }]);
    qaApi.getDefects.mockResolvedValue([defect]);
    qaApi.getDefect.mockResolvedValue(defect);
    qaApi.createDefect.mockResolvedValue({ ...defect, id: 'QAD-2' });
    qaApi.updateDefect.mockImplementation((defectId, updates) => Promise.resolve({
      ...defect,
      ...updates,
      id: defectId,
    }));
  });

  it('creates a project-scoped defect from the QA report form', async () => {
    const user = userEvent.setup();
    renderBugsPage();

    await user.click(await screen.findByRole('button', { name: 'Report Defect' }));
    await user.type(screen.getByLabelText(/^Title/), 'Event creation returns 500');
    await user.type(screen.getByLabelText(/^Description/), 'A valid payload fails unexpectedly.');
    await user.click(screen.getByRole('button', { name: 'Create Defect' }));

    await waitFor(() => {
      expect(qaApi.createDefect).toHaveBeenCalledWith(expect.objectContaining({
        project_id: 'PRJ-1',
        title: 'Event creation returns 500',
        description: 'A valid payload fails unexpectedly.',
        story_id: null,
        task_id: null,
        test_case_id: null,
      }));
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Defect QAD-2 reported.');
  });

  it('allows QA to assign a defect from its detail dialog', async () => {
    const user = userEvent.setup();
    renderBugsPage();

    const row = (await screen.findByText('QAD-1')).closest('tr');
    await user.click(within(row).getByRole('button', { name: 'Details' }));
    await screen.findByText('Status history');
    await user.type(screen.getByLabelText('Assign to employee ID'), 'DEMO-DEV');
    await user.click(screen.getByRole('button', { name: 'Assign' }));

    await waitFor(() => {
      expect(qaApi.updateDefect).toHaveBeenCalledWith('QAD-1', { assignee_id: 'DEMO-DEV' });
    });
    await waitFor(() => {
      expect(screen.getAllByRole('status').some((status) => status.textContent.includes('Defect updated.'))).toBe(true);
    });
  });

  it('lets a developer move an assigned fixed defect to ready for retest', async () => {
    const user = userEvent.setup();
    const fixedDefect = { ...defect, status: 'FIXED', assignee_id: 'DEMO-DEV' };
    const readyForRetest = { ...fixedDefect, status: 'READY_FOR_RETEST' };
    useAuthStore.mockReturnValue({ user: { role: 'DEVELOPER', employee_id: 'DEMO-DEV' } });
    qaApi.getDefects.mockResolvedValueOnce([fixedDefect]).mockResolvedValue([readyForRetest]);
    qaApi.getDefect.mockResolvedValue(fixedDefect);
    qaApi.updateDefect.mockResolvedValue(readyForRetest);
    renderBugsPage();

    const row = (await screen.findByText('QAD-1')).closest('tr');
    await user.click(within(row).getByRole('button', { name: 'Details' }));
    await user.click(await screen.findByRole('button', { name: 'Move to READY FOR RETEST' }));

    await waitFor(() => {
      expect(qaApi.updateDefect).toHaveBeenCalledWith('QAD-1', { status: 'READY_FOR_RETEST' });
    });
    expect(await screen.findByText(/READY_FOR_RETEST/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Move to READY FOR RETEST' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Move to CLOSED' })).not.toBeInTheDocument();
  });
});
