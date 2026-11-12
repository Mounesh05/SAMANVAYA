/**
 * CR-001: Developer-facing pages follow the same rules as the backend.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuthStore } from '../store/useAuthStore';
import { ToastProvider } from '../components/common/Toast';
import { PerformancePage } from '../pages/performance/PerformancePage';
import { PullRequestsPage } from '../pages/pull-requests/PullRequestsPage';
import { GlobalSearchModal } from '../components/layout/GlobalSearchModal';
import { performanceApi } from '../api/performance.api';
import { employeesApi } from '../api/employees.api';
import { rolesApi } from '../api/roles.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/performance.api', () => ({
  performanceApi: { getDeveloperDashboard: vi.fn(), evaluateDeveloper: vi.fn() },
}));
vi.mock('../api/employees.api', () => ({ employeesApi: { list: vi.fn() } }));
vi.mock('../api/roles.api', () => ({ rolesApi: { getMyPRs: vi.fn(), getReviewQueue: vi.fn() } }));
vi.mock('../api/github.api', () => ({ githubApi: { syncPullRequest: vi.fn() } }));

const DEVELOPER = roleUser('DEVELOPER', { employee_id: 'DEV-1', name: 'Dana Dev', team_id: 'TEAM-A' });

function renderAt(ui, path = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  performanceApi.getDeveloperDashboard.mockResolvedValue({ current_performance: null, historical_trend: [] });
  employeesApi.list.mockResolvedValue([]);
  rolesApi.getMyPRs.mockResolvedValue({ prs: [] });
  rolesApi.getReviewQueue.mockResolvedValue({ prs: [] });
});

describe('CR-001 Developer performance', () => {
  it('shows only the developer\'s own record, even when the URL asks for someone else', async () => {
    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    renderAt(<PerformancePage />, '/performance?developer=DEV-2');
    await waitFor(() => expect(performanceApi.getDeveloperDashboard).toHaveBeenCalled());
    expect(performanceApi.getDeveloperDashboard.mock.calls.every(([id]) => id === 'DEV-1')).toBe(true);
    expect(employeesApi.list).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: /Run|Evaluate/i })).not.toBeInTheDocument();
  });
});

describe('CR-001 Pull Requests', () => {
  it('offers Sync PR to SYNC_PR holders only', async () => {
    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    const { unmount } = renderAt(<PullRequestsPage />, '/pull-requests');
    expect(await screen.findByRole('button', { name: /Sync PR/i })).toBeInTheDocument();
    unmount();

    useAuthStore.setState({ user: roleUser('QA'), token: 't', isAuthenticated: true });
    renderAt(<PullRequestsPage />, '/pull-requests');
    await waitFor(() => expect(rolesApi.getMyPRs).toHaveBeenCalled());
    expect(screen.queryByRole('button', { name: /Sync PR/i })).not.toBeInTheDocument();
  });
});

describe('CR-001 global search', () => {
  it('never offers a Developer a page the router would refuse', () => {
    useAuthStore.setState({ user: DEVELOPER, token: 't', isAuthenticated: true });
    renderAt(<GlobalSearchModal isOpen onClose={() => {}} />);
    expect(screen.queryByText('GitHub PR Synchronizer')).not.toBeInTheDocument();
    expect(screen.queryByText('Reports & Analytics')).not.toBeInTheDocument();
    expect(screen.queryByText('Teams Management')).not.toBeInTheDocument();
    expect(screen.getByText('Tasks & Backlog')).toBeInTheDocument();
    expect(screen.getByText('Performance Dashboard')).toBeInTheDocument();
  });

  it('keeps HR\'s people pages in search', () => {
    useAuthStore.setState({ user: roleUser('HR'), token: 't', isAuthenticated: true });
    renderAt(<GlobalSearchModal isOpen onClose={() => {}} />);
    expect(screen.getByText('Employees Directory')).toBeInTheDocument();
    expect(screen.getByText('Teams Management')).toBeInTheDocument();
  });
});
