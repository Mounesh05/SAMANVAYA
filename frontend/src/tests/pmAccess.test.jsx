/**
 * CR-005: PM access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_pm_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '../store/useAuthStore';
import { TransferDetailPage } from '../pages/transfers/TransferDetailPage';
import apiClient from '../api/client';
import { roleUser } from './utils/roleUser';

vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const PM = roleUser('PM', { employee_id: 'PM-1', name: 'Pat PM' });

const transfer = (status) => ({
  id: 'TRF-2',
  employee_id: 'DEV-A',
  employee_name: 'Dana',
  initiated_by: 'Dana',
  current_team_id: 'TEAM-A',
  requested_team_id: 'TEAM-B',
  current_manager_id: 'LEAD-1',
  receiving_manager_id: 'LEAD-2',
  reason: 'project_needs',
  justification: 'Needed on payments',
  status,
  created_at: '2026-11-12T10:00:00Z',
});

function renderDetail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/transfers/TRF-2']}>
        <Routes>
          <Route path="/transfers/:transferId" element={<TransferDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: PM, token: 't', isAuthenticated: true });
});

describe('CR-005 transfer management stage', () => {
  it('shows PMs Approve at the management stage and sends PATCH', async () => {
    apiClient.get.mockResolvedValue(transfer('pending_management_approval'));
    apiClient.patch.mockResolvedValue(transfer('pending_hr_review'));
    const user = userEvent.setup();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: /Approve Transfer/i }));
    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith('/transfers/TRF-2/approve', { comments: null }));
  });

  it('never shows PMs the Execute button (CEO-only on the backend)', async () => {
    apiClient.get.mockResolvedValue(transfer('approved'));
    renderDetail();
    expect(await screen.findByText('Transfer Request: TRF-2')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Execute/i })).not.toBeInTheDocument();
  });

  it('shows Execute to the CEO for an approved transfer', async () => {
    useAuthStore.setState({ user: roleUser('CEO', { employee_id: 'CEO-1' }), token: 't', isAuthenticated: true });
    apiClient.get.mockResolvedValue(transfer('approved'));
    renderDetail();
    expect(await screen.findByRole('button', { name: /Execute/i })).toBeInTheDocument();
  });
});
