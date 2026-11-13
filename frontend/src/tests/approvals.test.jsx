/**
 * CR-010: two-person approval, as the UI presents it.
 * Backend counterparts live in backend/tests/test_two_person_approval.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage } from '../routes/access';
import { useAuthStore } from '../store/useAuthStore';
import { ApprovalsPage } from '../pages/approvals/ApprovalsPage';
import { EmployeesPage } from '../pages/employees/EmployeesPage';
import { approvalsApi } from '../api/approvals.api';
import { employeesApi } from '../api/employees.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/approvals.api', () => ({
  approvalsApi: { listPending: vi.fn(), listMine: vi.fn(), approve: vi.fn(), reject: vi.fn() },
}));
vi.mock('../api/employees.api', () => ({
  employeesApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
}));
vi.mock('../api/teams.api', () => ({ teamsApi: { list: vi.fn().mockResolvedValue([]) } }));

const ADMIN = roleUser('DEVELOPER', { employee_id: 'ADM-1', is_admin: true });
const REQUEST = {
  id: 'APPROVAL-1', kind: 'employee_change', description: 'Grant admin rights to Dana (DEV-1)',
  requested_by: 'ADM-2', approvers: ['ADM-1'], created_at: '2026-11-13T07:00:00Z', expires_at: '2026-11-14T07:00:00Z',
  change: { employee_id: 'DEV-1', fields: { is_admin: true } },
};

function renderPage(page, user = ADMIN) {
  useAuthStore.setState({ user, token: 't', isAuthenticated: true });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}><MemoryRouter>{page}</MemoryRouter></QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  approvalsApi.listPending.mockResolvedValue({ approvals: [REQUEST] });
  approvalsApi.listMine.mockResolvedValue({ approvals: [] });
});

describe('CR-010 page access', () => {
  it('opens for admins and employee managers only', () => {
    expect(canOpenPage(ADMIN, 'approvals')).toBe(true);
    expect(canOpenPage(roleUser('HR'), 'approvals')).toBe(true);
    for (const role of ['DEVELOPER', 'LEAD', 'PM', 'QA', 'DEVOPS', 'CEO']) {
      expect(canOpenPage(roleUser(role), 'approvals')).toBe(false);
    }
  });
});

describe('CR-010 Approvals page', () => {
  it('approves a waiting request', async () => {
    approvalsApi.approve.mockResolvedValue({ success: true, applied: true });
    renderPage(<ApprovalsPage />);
    expect(await screen.findByText(/Grant admin rights to Dana/)).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(approvalsApi.approve).toHaveBeenCalledWith('APPROVAL-1'));
    expect(await screen.findByRole('status')).toHaveTextContent('Approved and applied');
  });

  it('needs a reason to reject', async () => {
    approvalsApi.reject.mockResolvedValue({ success: true });
    renderPage(<ApprovalsPage />);
    const reject = await screen.findByRole('button', { name: 'Reject' });
    expect(reject).toBeDisabled();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText('Reason for rejecting APPROVAL-1'), 'Not needed');
    await user.click(reject);
    await waitFor(() => expect(approvalsApi.reject).toHaveBeenCalledWith('APPROVAL-1', 'Not needed'));
  });

  it('shows why an approved change could not be applied', async () => {
    approvalsApi.approve.mockRejectedValue({ response: { data: { detail: 'Approved, but the change could not be applied: last admin' } } });
    renderPage(<ApprovalsPage />);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Approve' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be applied');
  });
});

describe('CR-010 Employees page', () => {
  it('says a change was sent for approval and marks the row', async () => {
    employeesApi.list.mockResolvedValue([
      { employee_id: 'DEV-1', name: 'Dana', email: 'd@x.test', role: 'DEVELOPER', dept: 'Eng', is_active: true, is_admin: false },
      { employee_id: 'DEV-2', name: 'Eli', email: 'e@x.test', role: 'DEVELOPER', dept: 'Eng', is_active: true, is_admin: false },
    ]);
    employeesApi.update.mockResolvedValue({ status: 'pending_approval', approval_id: 'APPROVAL-9' });
    renderPage(<EmployeesPage />);
    expect(await screen.findByText(/pending approval/)).toBeInTheDocument();  // DEV-1 from REQUEST
    await userEvent.setup().click(screen.getByRole('button', { name: 'Make Eli an admin' }));
    expect(await screen.findByText(/Sent for approval \(APPROVAL-9\)/)).toBeInTheDocument();
  });
});
