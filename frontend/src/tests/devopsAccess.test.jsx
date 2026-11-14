/**
 * CR-003: DevOps access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_devops_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage, showInMenu } from '../routes/access';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { useAuthStore } from '../store/useAuthStore';
import { GitHubSyncPage } from '../pages/github/GitHubSyncPage';
import { githubApi } from '../api/github.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/github.api', () => ({
  githubApi: {
    checkHealth: vi.fn(),
    getProjectConfig: vi.fn(),
    saveProjectConfig: vi.fn(),
    syncPullRequest: vi.fn(),
    provisionQaWorkflow: vi.fn(),
  },
}));

const DEVOPS = roleUser('DEVOPS', { employee_id: 'OPS-1', name: 'Olly Ops' });

function renderPage(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  githubApi.checkHealth.mockResolvedValue({ status: 'ok', token_configured: true });
});

describe('CR-003 DevOps pages', () => {
  it('opens the DevOps pages by permission', () => {
    for (const page of ['pipelines', 'deployments', 'githubSync', 'incidents', 'cicdLogs', 'codeQuality', 'bugs']) {
      expect(canOpenPage(DEVOPS, page), page).toBe(true);
    }
    expect(showInMenu(DEVOPS, 'githubSync')).toBe(true);
  });

  it('blocks Reports for DevOps', () => {
    expect(canOpenPage(DEVOPS, 'reports')).toBe(false);
  });

  it('keeps Pipelines and Deployments for the same roles as before', () => {
    const pipelines = ['DEVOPS', 'QA', 'LEAD', 'DEVELOPER', 'PM', 'HR', 'CEO'].filter((r) => canOpenPage(roleUser(r), 'pipelines'));
    const deployments = ['DEVOPS', 'QA', 'LEAD', 'DEVELOPER', 'PM', 'HR', 'CEO'].filter((r) => canOpenPage(roleUser(r), 'deployments'));
    const githubSync = ['DEVOPS', 'QA', 'LEAD', 'DEVELOPER', 'PM', 'HR', 'CEO'].filter((r) => canOpenPage(roleUser(r), 'githubSync'));
    expect(pipelines.sort()).toEqual(['DEVOPS', 'LEAD', 'QA']);
    expect(deployments.sort()).toEqual(['DEVOPS', 'LEAD']);
    expect(githubSync.sort()).toEqual(['DEVOPS', 'LEAD']); // CR-007: not the CEO; CR-015: not the PM
  });

  it('gives DevOps CI automation and defect reporting, but only own performance', () => {
    expect(hasPermission(DEVOPS, PERMISSIONS.MANAGE_TEST_AUTOMATION)).toBe(true);
    expect(hasPermission(DEVOPS, PERMISSIONS.CREATE_BUG)).toBe(true);
    expect(hasPermission(DEVOPS, PERMISSIONS.VIEW_PROJECT_PERFORMANCE)).toBe(false);
  });
});

describe('CR-003 GitHub Sync actions', () => {
  it('shows DevOps the repository link but not Sync PR (Developer-only)', async () => {
    useAuthStore.setState({ user: DEVOPS, token: 't', isAuthenticated: true });
    renderPage(<GitHubSyncPage />);
    await waitFor(() => expect(githubApi.checkHealth).toHaveBeenCalled());
    expect(await screen.findByText('Project Repository Configuration')).toBeInTheDocument();
    expect(screen.queryByText('Synchronize Single PR')).not.toBeInTheDocument();
  });
});
