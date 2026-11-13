/**
 * CR-014: incident detail and triage. Backend counterparts live in
 * backend/tests/test_incident_triage.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { IncidentDetail } from '../pages/incidents/IncidentDetail';
import { incidentsApi } from '../api/incidents.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/incidents.api', () => ({ incidentsApi: { get: vi.fn(), triage: vi.fn() } }));

const incident = (overrides = {}) => ({
  id: 'INC-1', project_id: 'P1', title: 'Checkout down', description: '500s on checkout', severity: 'high',
  status: 'open', reporter_id: 'DEV-1', timeline: [{ at: '2026-11-13T08:00:00Z', by: 'DEV-1', action: 'reported', changes: {} }],
  ...overrides,
});

function renderDetail(canTriage) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}><IncidentDetail incidentId="INC-1" canTriage={canTriage} /></QueryClientProvider>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe('CR-014 triage rights', () => {
  it('belongs to DevOps, Lead and PM', () => {
    for (const role of ['DEVOPS', 'LEAD', 'PM']) expect(hasPermission(roleUser(role), PERMISSIONS.TRIAGE_INCIDENT)).toBe(true);
    for (const role of ['CEO', 'DEVELOPER', 'QA', 'HR']) expect(hasPermission(roleUser(role), PERMISSIONS.TRIAGE_INCIDENT)).toBe(false);
    expect(hasPermission(roleUser('PM'), PERMISSIONS.VIEW_INCIDENTS)).toBe(true);
  });
});

describe('CR-014 incident detail', () => {
  it('offers only the next allowed step and sends it', async () => {
    incidentsApi.get.mockResolvedValue(incident());
    incidentsApi.triage.mockResolvedValue(incident({ status: 'investigating' }));
    renderDetail(true);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Acknowledge' }));
    expect(screen.queryByRole('button', { name: 'Close' })).not.toBeInTheDocument();
    await waitFor(() => expect(incidentsApi.triage).toHaveBeenCalledWith('INC-1', { status: 'investigating' }));
  });

  it('needs a resolution summary before resolving', async () => {
    incidentsApi.get.mockResolvedValue(incident({ status: 'investigating' }));
    incidentsApi.triage.mockResolvedValue(incident({ status: 'resolved' }));
    renderDetail(true);
    const user = userEvent.setup();
    const resolve = await screen.findByRole('button', { name: 'Resolve' });
    expect(resolve).toBeDisabled();
    await user.type(screen.getByLabelText('Resolution summary'), 'Rolled back');
    await user.click(resolve);
    await waitFor(() => expect(incidentsApi.triage).toHaveBeenCalledWith('INC-1', { status: 'resolved', resolution_summary: 'Rolled back' }));
  });

  it('needs a post-incident review to close a high incident', async () => {
    incidentsApi.get.mockResolvedValue(incident({ status: 'resolved', resolution_summary: 'Rolled back' }));
    incidentsApi.triage.mockResolvedValue(incident({ status: 'closed' }));
    renderDetail(true);
    const user = userEvent.setup();
    const close = await screen.findByRole('button', { name: 'Close' });
    expect(close).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Reopen' })).toBeEnabled();
    await user.type(screen.getByLabelText('Post-incident review'), 'Cause: config');
    await user.click(close);
    await waitFor(() => expect(incidentsApi.triage).toHaveBeenCalledWith('INC-1', { status: 'closed', postmortem: 'Cause: config' }));
  });

  it('is read-only for viewers and shows the timeline', async () => {
    incidentsApi.get.mockResolvedValue(incident());
    renderDetail(false);
    expect(await screen.findByText('reported')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Acknowledge' })).not.toBeInTheDocument();
    expect(screen.queryByLabelText('Owner employee ID')).not.toBeInTheDocument();
  });

  it('shows the backend reason when a change is refused', async () => {
    incidentsApi.get.mockResolvedValue(incident({ status: 'investigating' }));
    incidentsApi.triage.mockRejectedValue({ response: { data: { detail: 'The owner must be a member of the incident\'s project' } } });
    renderDetail(true);
    const user = userEvent.setup();
    await user.type(await screen.findByLabelText('Owner employee ID'), 'HR-1');
    await user.click(screen.getByRole('button', { name: 'Assign' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('member of the incident');
  });
});
