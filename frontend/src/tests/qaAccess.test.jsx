/**
 * CR-002: QA access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_qa_access.py.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { canOpenPage, showInMenu } from '../routes/access';
import { canUpdateTask, isSignOffOnly } from '../utils/taskPermissions';
import { useAuthStore } from '../store/useAuthStore';
import { StoriesPage } from '../pages/stories/StoriesPage';
import { PullRequestsPage } from '../pages/pull-requests/PullRequestsPage';
import { storiesApi } from '../api/stories.api';
import { projectsApi } from '../api/projects.api';
import { sprintsApi } from '../api/sprints.api';
import { githubApi } from '../api/github.api';
import { roleUser } from './utils/roleUser';

vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../api/sprints.api', () => ({ sprintsApi: { listByProject: vi.fn() } }));
vi.mock('../api/stories.api', () => ({
  storiesApi: { listBySprint: vi.fn(), create: vi.fn(), updateStatus: vi.fn() },
}));
vi.mock('../api/employees.api', () => ({ employeesApi: { list: vi.fn().mockResolvedValue([]) } }));
vi.mock('../api/roles.api', () => ({ rolesApi: { getMyPRs: vi.fn(), getReviewQueue: vi.fn() } }));
vi.mock('../api/github.api', () => ({
  githubApi: { syncPullRequest: vi.fn(), listProjectPullRequests: vi.fn() },
}));

const QA = roleUser('QA', { employee_id: 'QA-1', name: 'Quinn QA' });

function renderWithClient(ui) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  projectsApi.list.mockResolvedValue([{ id: 'PRJ-1', name: 'CampusConnect' }]);
  sprintsApi.listByProject.mockResolvedValue([{ id: 'SPR-1', name: 'Sprint 1' }]);
});

describe('CR-002 QA pages', () => {
  it('opens the QA-owned pages by permission', () => {
    for (const page of ['tests', 'bugs', 'codeQuality', 'board', 'incidents', 'pullRequests', 'cicdLogs', 'performance']) {
      expect(canOpenPage(QA, page), page).toBe(true);
    }
  });

  it('shows the Board in the QA menu and blocks Reports', () => {
    expect(showInMenu(QA, 'board')).toBe(true);
    expect(canOpenPage(QA, 'reports')).toBe(false);
  });

  it('keeps Tests a QA-only page and Bugs for the six delivery roles', () => {
    for (const role of ['DEVELOPER', 'LEAD', 'PM', 'DEVOPS', 'CEO', 'HR']) {
      expect(canOpenPage(roleUser(role), 'tests'), role).toBe(false);
    }
    for (const role of ['QA', 'DEVELOPER', 'DEVOPS', 'LEAD', 'PM', 'CEO']) {
      expect(canOpenPage(roleUser(role), 'bugs'), role).toBe(true);
    }
    expect(canOpenPage(roleUser('HR'), 'bugs')).toBe(false);
  });
});

describe('CR-002 sign-off rule (tasks and board)', () => {
  const inReview = { id: 'T-1', status: 'review', assignee_id: 'DEV-1' };

  it('lets QA act on work in Review only', () => {
    expect(canUpdateTask(QA, inReview)).toBe(true);
    expect(isSignOffOnly(QA, inReview)).toBe(true);
    expect(canUpdateTask(QA, { ...inReview, status: 'in_progress' })).toBe(false);
  });

  it('does not give developers sign-off on other people\'s work', () => {
    expect(canUpdateTask(roleUser('DEVELOPER', { employee_id: 'DEV-2' }), inReview)).toBe(false);
  });
});

describe('CR-002 story sign-off', () => {
  it('shows Pass and Fail on stories in Review to QA, and sends the right status', async () => {
    storiesApi.listBySprint.mockResolvedValue([
      { id: 'STY-5', title: 'Checkout', status: 'review', assignee_id: 'DEV-1', points: 3 },
      { id: 'STY-6', title: 'Search', status: 'in_progress', assignee_id: 'DEV-1', points: 2 },
    ]);
    storiesApi.updateStatus.mockResolvedValue({});
    useAuthStore.setState({ user: QA, token: 't', isAuthenticated: true });
    const user = userEvent.setup();
    renderWithClient(<StoriesPage />);

    const reviewRow = (await screen.findByText('STY-5')).closest('tr');
    const otherRow = screen.getByText('STY-6').closest('tr');
    expect(within(otherRow).queryByRole('button', { name: 'Pass' })).not.toBeInTheDocument();

    await user.click(within(reviewRow).getByRole('button', { name: 'Fail' }));
    await waitFor(() => expect(storiesApi.updateStatus).toHaveBeenCalledWith('STY-5', 'in_progress'));
    await user.click(within(reviewRow).getByRole('button', { name: 'Pass' }));
    await waitFor(() => expect(storiesApi.updateStatus).toHaveBeenCalledWith('STY-5', 'done'));
  });

  it('does not show Pass or Fail to developers', async () => {
    storiesApi.listBySprint.mockResolvedValue([
      { id: 'STY-5', title: 'Checkout', status: 'review', assignee_id: 'DEV-1', points: 3 },
    ]);
    useAuthStore.setState({ user: roleUser('DEVELOPER', { employee_id: 'DEV-2' }), token: 't', isAuthenticated: true });
    renderWithClient(<StoriesPage />);
    const row = (await screen.findByText('STY-5')).closest('tr');
    expect(within(row).queryByRole('button', { name: 'Pass' })).not.toBeInTheDocument();
  });
});

describe('CR-002 project pull requests', () => {
  it('lists the PRs of the tester\'s project instead of an empty "my PRs"', async () => {
    githubApi.listProjectPullRequests.mockResolvedValue({
      pull_requests: [{ id: 'PR-9', pr_number: 9, title: 'Fix totals', status: 'open', author: 'dana' }],
    });
    useAuthStore.setState({ user: QA, token: 't', isAuthenticated: true });
    renderWithClient(<PullRequestsPage />);
    await waitFor(() => expect(githubApi.listProjectPullRequests).toHaveBeenCalledWith('PRJ-1'));
    expect(await screen.findByText('Fix totals')).toBeInTheDocument();
    expect(screen.getByText('Project Pull Requests')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Sync PR/i })).not.toBeInTheDocument();
  });
});
