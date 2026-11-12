/**
 * CR-004: Lead access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_lead_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage, showInMenu } from '../routes/access';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { useAuthStore } from '../store/useAuthStore';
import { TransferDetailPage } from '../pages/transfers/TransferDetailPage';
import { transfersApi } from '../api/transfers.api';
import apiClient from '../api/client';
import { roleUser } from './utils/roleUser';

vi.mock('../api/client', () => ({ default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() } }));

const LEAD = roleUser('LEAD', { employee_id: 'LEAD-1', name: 'Lee Lead', team_id: 'TEAM-A' });

const transfer = (overrides = {}) => ({
  id: 'TRF-1',
  employee_id: 'DEV-A',
  employee_name: 'Dana',
  initiated_by: 'Dana',
  current_team_id: 'TEAM-A',
  requested_team_id: 'TEAM-B',
  current_manager_id: 'LEAD-1',
  receiving_manager_id: 'LEAD-2',
  reason: 'career_growth',
  justification: 'Growth',
  status: 'pending_current_manager_release',
  created_at: '2026-11-12T10:00:00Z',
  ...overrides,
});

function renderDetail() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/transfers/TRF-1']}>
        <Routes>
          <Route path="/transfers/:transferId" element={<TransferDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: LEAD, token: 't', isAuthenticated: true });
});

describe('CR-004 Lead pages', () => {
  it('puts Transfer Requests in the Lead menu and blocks Reports', () => {
    expect(showInMenu(LEAD, 'transfers')).toBe(true);
    expect(canOpenPage(LEAD, 'reports')).toBe(false);
  });

  it('lets Leads create sprints and use the converted Lead permissions', () => {
    expect(hasPermission(LEAD, PERMISSIONS.CREATE_SPRINT)).toBe(true);
    expect(hasPermission(LEAD, PERMISSIONS.SYNC_REPOSITORY_PRS)).toBe(true);
    expect(hasPermission(LEAD, PERMISSIONS.ANALYZE_SPRINT_RISK)).toBe(true);
    expect(hasPermission(LEAD, PERMISSIONS.VERIFY_DEFECTS)).toBe(false);
  });
});

describe('CR-004 transfer approvals', () => {
  it('shows Approve to the current manager at the release stage and sends PATCH', async () => {
    apiClient.get.mockResolvedValue(transfer());
    apiClient.patch.mockResolvedValue(transfer({ status: 'pending_receiving_manager_acceptance' }));
    const user = userEvent.setup();
    renderDetail();

    await user.click(await screen.findByRole('button', { name: /Approve Transfer/i }));
    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith('/transfers/TRF-1/approve', { comments: null }));
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it('hides Approve from a Lead whose stage it is not', async () => {
    apiClient.get.mockResolvedValue(transfer({ status: 'pending_receiving_manager_acceptance' }));
    renderDetail();
    expect(await screen.findByText('Transfer Request: TRF-1')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Approve Transfer/i })).not.toBeInTheDocument();
  });

  it('uses PATCH for every transfer action', async () => {
    await transfersApi.rejectTransfer('TRF-1', { comments: 'no' });
    await transfersApi.flagTransfer('TRF-1', { flag: 'x' });
    await transfersApi.executeTransfer('TRF-1');
    expect(apiClient.patch).toHaveBeenCalledTimes(3);
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
