import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { PullRequestsPage } from './PullRequestsPage';
import { useAuthStore } from '../../store/useAuthStore';
import { roleUser } from '../../tests/utils/roleUser';
import { projectsApi } from '../../api/projects.api';
import { githubApi } from '../../api/github.api';
import { rolesApi } from '../../api/roles.api';

vi.mock('../../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../../api/github.api', () => ({ githubApi: { listProjectPullRequests: vi.fn(), syncPullRequest: vi.fn() } }));
vi.mock('../../api/roles.api', () => ({ rolesApi: { getMyPRs: vi.fn(), getReviewQueue: vi.fn() } }));
vi.mock('../code-quality/PRAlgorithmIntelligencePanel', () => ({ PRAlgorithmIntelligencePanel: () => null }));

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: roleUser('DEVELOPER', { employee_id: 'DEV', org_id: 'A' }) });
  projectsApi.list.mockResolvedValue([{ id: 'P1', name: 'Project' }]);
  githubApi.listProjectPullRequests.mockResolvedValue({ pull_requests: [{ id: 'PR1', title: 'CI evidence', status: 'open',
    ci_status: null, ci_evidence_status: 'partial', github_actions_ci: {
      status: 'available', reported_outcome: 'success', runs: [{ run_id: 10 }],
    } }] });
  rolesApi.getMyPRs.mockResolvedValue({ pull_requests: [] });
});

it('labels Actions outcomes separately and retains unavailable third-party coverage', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PullRequestsPage /></MemoryRouter></QueryClientProvider>);
  expect(await screen.findByText('Actions: success')).toBeInTheDocument();
  expect(screen.getByText('Other check providers unavailable')).toBeInTheDocument();
  expect(screen.queryByText('passing')).not.toBeInTheDocument();
});
