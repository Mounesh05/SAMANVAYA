/**
 * CR-006: HR access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_hr_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage } from '../routes/access';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { useAuthStore } from '../store/useAuthStore';
import { TransferDetailPage } from '../pages/transfers/TransferDetailPage';
import apiClient from '../api/client';
import { roleUser } from './utils/roleUser';

vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const HR = roleUser('HR', { employee_id: 'HR-1', name: 'Hana HR' });

const transfer = (status) => ({
  id: 'TRF-3', employee_id: 'DEV-A', employee_name: 'Dana', initiated_by: 'Dana',
  current_team_id: 'TEAM-A', requested_team_id: 'TEAM-B', current_manager_id: 'LEAD-1',
  receiving_manager_id: 'LEAD-2', reason: 'career_growth', justification: 'Growth', status,
  created_at: '2026-11-12T10:00:00Z',
});

function renderDetail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/transfers/TRF-3']}>
        <Routes>
          <Route path="/transfers/:transferId" element={<TransferDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: HR, token: 't', isAuthenticated: true });
});

describe('CR-006 HR permissions and pages', () => {
  it('lets HR execute transfers and keeps the AI Evaluation page closed', () => {
    expect(hasPermission(HR, PERMISSIONS.EXECUTE_TRANSFER)).toBe(true);
    expect(canOpenPage(HR, 'evaluation')).toBe(false);
    expect(canOpenPage(HR, 'performance')).toBe(true);
  });
});

describe('CR-006 transfer HR stages', () => {
  it.each(['pending_hr_validation', 'pending_hr_review'])('shows HR Approve at %s and sends PATCH', async (status) => {
    apiClient.get.mockResolvedValue(transfer(status));
    apiClient.patch.mockResolvedValue(transfer('approved'));
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole('button', { name: /Approve Transfer/i }));
    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith('/transfers/TRF-3/approve', { comments: null }));
  });

  it('sends the flag field the backend requires', async () => {
    apiClient.get.mockResolvedValue(transfer('pending_hr_validation'));
    apiClient.patch.mockResolvedValue(transfer('pending_hr_validation'));
    const user = userEvent.setup();
    renderDetail();
    await user.click(await screen.findByRole('button', { name: /Flag/i }));
    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith(
      '/transfers/TRF-3/flag', { flag: 'needs_hr_review', comments: null },
    ));
  });

  it('shows HR no HR buttons at a manager stage', async () => {
    apiClient.get.mockResolvedValue(transfer('pending_current_manager_release'));
    renderDetail();
    expect(await screen.findByText('Transfer Request: TRF-3')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve Transfer/i })).not.toBeInTheDocument();
  });
});
