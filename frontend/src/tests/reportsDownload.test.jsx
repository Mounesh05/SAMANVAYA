/**
 * CR-011: report downloads on the Reports page.
 * Backend counterparts live in backend/tests/test_reports.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage } from '../routes/access';
import { useAuthStore } from '../store/useAuthStore';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { reportsApi } from '../api/reports.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/reports.api', () => ({ reportsApi: { list: vi.fn(), downloadCsv: vi.fn() } }));

function renderReports(user) {
  useAuthStore.setState({ user, token: 't', isAuthenticated: true });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}><MemoryRouter><ReportsPage /></MemoryRouter></QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  URL.createObjectURL = vi.fn(() => 'blob:report');
  URL.revokeObjectURL = vi.fn();
});

describe('CR-011 Reports page', () => {
  it('opens for export holders only', () => {
    for (const role of ['CEO', 'PM', 'HR']) expect(canOpenPage(roleUser(role), 'reports')).toBe(true);
    for (const role of ['DEVELOPER', 'LEAD', 'QA', 'DEVOPS']) expect(canOpenPage(roleUser(role), 'reports')).toBe(false);
  });

  it('offers downloads only for reports the backend lists, after a purpose', async () => {
    reportsApi.list.mockResolvedValue({ reports: [{ type: 'delivery_risk', title: 'Delivery & Risk Governance' }] });
    reportsApi.downloadCsv.mockResolvedValue(new Blob(['a,b\n']));
    renderReports(roleUser('PM'));
    const button = await screen.findByRole('button', { name: /Download CSV/ });
    expect(screen.getAllByRole('button', { name: /Download CSV/ })).toHaveLength(1);
    expect(button).toBeDisabled();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/Purpose for downloading Delivery/), 'Board pack');
    await user.click(button);
    await waitFor(() => expect(reportsApi.downloadCsv).toHaveBeenCalledWith('delivery_risk', { purpose: 'Board pack' }));
    expect(await screen.findByRole('status')).toHaveTextContent('recorded in the audit log');
  });

  it('shows the backend reason when a download is refused', async () => {
    reportsApi.list.mockResolvedValue({ reports: [{ type: 'performance_distribution', title: 'Workforce Performance' }] });
    reportsApi.downloadCsv.mockRejectedValue({
      response: { data: new Blob([JSON.stringify({ detail: 'Choose a period of 12 months or less' })]) },
    });
    renderReports(roleUser('HR'));
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText(/Purpose for downloading Workforce/), 'Calibration');
    await user.click(screen.getByRole('button', { name: /Download CSV/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('12 months');
  });
});
