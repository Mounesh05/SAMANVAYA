import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
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

function show(githubUsername = null) {
  useAuthStore.setState({ user: roleUser('DEVELOPER', { employee_id: 'DEV', org_id: 'A', github_username: githubUsername }) });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, retryDelay: 0 } } });
  render(<QueryClientProvider client={client}><MemoryRouter><PullRequestsPage /></MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  projectsApi.list.mockResolvedValue([{ id: 'P1', name: 'Project' }]);
  githubApi.listProjectPullRequests.mockResolvedValue({ pull_requests: [{ id: 'PR1', pr_number: 4,
    title: 'Graph traversal', author_login: 'github-developer', status: 'open', ci_evidence_status: 'unavailable' }] });
  rolesApi.getMyPRs.mockResolvedValue({ pull_requests: [{ id: 'PR2', pr_number: 2, title: 'Personal PR', status: 'open' }] });
});

it('shows scoped project PRs and explains missing identity instead of a misleading empty personal list', async () => {
  show();
  expect(await screen.findByText('Graph traversal')).toBeInTheDocument();
  expect(screen.getByText(/GitHub account is not linked/i)).toBeInTheDocument();
  expect(screen.getByText('github-developer')).toBeInTheDocument();
  expect(screen.getByText('Unavailable')).toBeInTheDocument();
  expect(githubApi.listProjectPullRequests).toHaveBeenCalledWith('P1');
  expect(rolesApi.getMyPRs).not.toHaveBeenCalled();
});

it('preserves the personal view for an explicitly linked developer', async () => {
  show('github-developer');
  expect(await screen.findByText('Personal PR')).toBeInTheDocument();
  expect(screen.getByRole('heading', { name: 'My Pull Requests' })).toBeInTheDocument();
  expect(githubApi.listProjectPullRequests).not.toHaveBeenCalled();
});

it('treats a whitespace-only GitHub identity as unlinked', async () => {
  show('   ');
  expect(await screen.findByText('Graph traversal')).toBeInTheDocument();
  expect(rolesApi.getMyPRs).not.toHaveBeenCalled();
});

it('does not count merged PRs as pending review work', async () => {
  githubApi.listProjectPullRequests.mockResolvedValue({ pull_requests: [
    { id: 'PR1', title: 'Open work', status: 'open', review_status: 'pending' },
    { id: 'PR2', title: 'Merged work', status: 'merged', review_status: 'pending' },
  ] });
  show();
  await screen.findByText('Open work');
  const card = screen.getByText('Pending Review').parentElement;
  expect(within(card).getByText('1')).toBeInTheDocument();
});

it('labels Actions outcomes separately and retains unavailable third-party coverage', async () => {
  githubApi.listProjectPullRequests.mockResolvedValue({ pull_requests: [{ id: 'PR1', title: 'CI evidence', status: 'open',
    ci_status: null, ci_evidence_status: 'partial', github_actions_ci: {status: 'available', reported_outcome: 'success', runs: [{run_id: 10}]} }] });
  show();
  expect(await screen.findByText('Actions: success')).toBeInTheDocument();
  expect(screen.getByText('Other check providers unavailable')).toBeInTheDocument();
  expect(screen.queryByText('passing')).not.toBeInTheDocument();
});

it('shows an empty authorized-project state without claiming personal ownership', async () => {
  projectsApi.list.mockResolvedValue([]);
  show();
  expect(await screen.findByRole('heading', { name: 'Project Pull Requests' })).toBeInTheDocument();
  expect(screen.getByText(/GitHub account is not linked/i)).toBeInTheDocument();
  expect(githubApi.listProjectPullRequests).not.toHaveBeenCalled();
  expect(rolesApi.getMyPRs).not.toHaveBeenCalled();
});

it('shows a denied project response instead of an empty success state', async () => {
  githubApi.listProjectPullRequests.mockRejectedValue(new Error('Access denied'));
  show();
  expect(await screen.findByText('Access denied')).toBeInTheDocument();
  expect(screen.queryByText('Graph traversal')).not.toBeInTheDocument();
});

it('keeps partial CI evidence unknown rather than passing', async () => {
  githubApi.listProjectPullRequests.mockResolvedValue({ pull_requests: [{ id: 'PR1', title: 'Partial CI', status: 'open',
    ci_evidence_status: 'partial', github_actions_ci: { status: 'partial', reported_outcome: 'unknown', runs: [{ run_id: 10 }] } }] });
  show();
  expect(await screen.findByText('Actions: unknown (partial)')).toBeInTheDocument();
  expect(screen.queryByText('passing')).not.toBeInTheDocument();
});
