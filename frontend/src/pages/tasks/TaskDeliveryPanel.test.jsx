import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { prWorkflowsApi } from '../../api/prWorkflows.api';
import { tasksApi } from '../../api/tasks.api';
import { projectsApi } from '../../api/projects.api';
import { sprintsApi } from '../../api/sprints.api';
import { useAuthStore } from '../../store/useAuthStore';
import { roleUser } from '../../tests/utils/roleUser';
import { TasksPage } from './TasksPage';
import { TaskDeliveryPanel } from './TaskDeliveryPanel';

vi.mock('../../api/tasks.api', () => ({ tasksApi: {
  getDelivery: vi.fn(), recordReleaseDecision: vi.fn(), listByProject: vi.fn(), getAvailableTransitions: vi.fn(),
} }));
vi.mock('../../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../../api/sprints.api', () => ({ sprintsApi: { listByProject: vi.fn() } }));
vi.mock('../../api/prWorkflows.api', () => ({ prWorkflowsApi: { lookupReport: vi.fn(), start: vi.fn() } }));

const revision = 'b'.repeat(40);
const delivery = {
  task_id: 'T-1', project_id: 'P-1', revision, revision_kind: 'merge_commit', decision_version: 'first',
  requirement: { title: 'Search products', story: { id: 'S-1', title: 'Catalog search', description: 'Match the nearest available product.' } },
  implementation: { status: 'merged', pull_requests: [{ repository: 'org/catalog', number: 7, title: 'Faster catalog search' }] },
  qa: { status: 'failed', reason: 'The performance suite failed on the merge commit.', runs: [
    { id: 'R1', workflow_run_id: '37', run_attempt: 2, status: 'failed', test_suite: 'performance', tests_failed: 1, provenance: 'github_artifact' },
  ] },
  production: { status: 'unknown', reason: 'No matching production event.' },
  readiness: { status: 'blocked', reason: 'Resolve the failed check.' },
  release_decision: null, qa_verification: null, can_decide: true, can_approve: false, can_verify_qa: false,
};
const approved = {
  decision: 'approve', reason: 'Reviewed the fix', revision,
  recorded_at: '2026-11-23T10:00:00Z', actor_name: 'Maya', is_current: true,
};

function show(component = <TaskDeliveryPanel taskId="T-1" />) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter>{component}</MemoryRouter></QueryClientProvider>);
}

beforeEach(() => {
  vi.resetAllMocks();
  useAuthStore.setState({ user: roleUser('DEVOPS', { employee_id: 'O-1', org_id: 'ORG-1' }) });
  tasksApi.getDelivery.mockResolvedValue(delivery);
});

afterEach(() => vi.unstubAllEnvs());

const head = 'a'.repeat(40);
function prepareAdvisory(role = 'LEAD') {
  vi.stubEnv('VITE_PR_MULTI_AGENT_MANUAL_ENABLED', 'true');
  useAuthStore.setState({ user: roleUser(role, { employee_id: 'A', org_id: 'ORG-1' }) });
  const pr = { ...delivery.implementation.pull_requests[0], head_sha: head, merge_commit_sha: revision };
  tasksApi.getDelivery.mockResolvedValue({ ...delivery, implementation: { ...delivery.implementation, pull_requests: [pr] } });
  return { schema_version: 'pr-multi-agent-report-v2', status: 'PARTIAL_SINGLE_SPECIALIST_ADVISORY',
    scope: { owner_id: 'A', organization_id: 'ORG-1', project_id: delivery.project_id, repository: pr.repository,
      pr_number: pr.number, head_sha: head, base_sha: 'c'.repeat(40) },
    outcomes: [{ specialist: 'code_analysis', status: 'SUCCEEDED', summary: 'Recorded structural observations' }],
    limitations: ['STRUCTURAL_FACTS_DO_NOT_PROVE_CORRECTNESS'] };
}

it('opens an existing advisory for the PR head only after a click and renders its limits', async () => {
  const report = prepareAdvisory();
  prWorkflowsApi.lookupReport.mockResolvedValue(report);
  show();
  const action = await screen.findByRole('button', { name: 'View PR head advisory' });
  expect(prWorkflowsApi.lookupReport).not.toHaveBeenCalled();
  fireEvent.click(action);
  expect(await screen.findByText('Recorded structural observations')).toBeVisible();
  expect(prWorkflowsApi.lookupReport).toHaveBeenCalledWith({
    project_id: 'P-1', repository: 'org/catalog', pr_number: 7, head_sha: head,
  }, expect.any(AbortSignal));
  expect(screen.getByText(head)).toBeVisible();
  expect(screen.getByText('Structural observations do not establish correctness.')).toBeVisible();
  expect(screen.getByText(/QA and DevOps review the merge commit separately/)).toBeVisible();
  expect(prWorkflowsApi.start).not.toHaveBeenCalled();
  expect(tasksApi.recordReleaseDecision).not.toHaveBeenCalled();
});

it.each([{ head_sha: revision }, { owner_id: 'other' }, { organization_id: 'foreign' }, { project_id: 'P2' }])(
  'hides advisory content when its stored scope disagrees: %o', async (change) => {
    const report = prepareAdvisory();
    prWorkflowsApi.lookupReport.mockResolvedValue({ ...report, scope: { ...report.scope, ...change } });
    show();
    fireEvent.click(await screen.findByRole('button', { name: 'View PR head advisory' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('advisory source differs');
    expect(screen.queryByText('Recorded structural observations')).not.toBeInTheDocument();
  });

it('shows an empty advisory without submitting a job', async () => {
  prepareAdvisory();
  prWorkflowsApi.lookupReport.mockResolvedValue(null);
  show();
  fireEvent.click(await screen.findByRole('button', { name: 'View PR head advisory' }));
  expect(await screen.findByText(/No published advisory from your account/)).toBeVisible();
  expect(prWorkflowsApi.start).not.toHaveBeenCalled();
});

it('hides the advisory controls for a task reviewer without manual analysis permissions', async () => {
  prepareAdvisory('DEVELOPER');
  show();
  await screen.findByText('Merged');
  expect(screen.queryByRole('button', { name: 'View PR head advisory' })).not.toBeInTheDocument();
  expect(prWorkflowsApi.lookupReport).not.toHaveBeenCalled();
});

it('opens delivery evidence from a normal task row and keeps merged, failed QA and unknown production distinct', async () => {
  projectsApi.list.mockResolvedValue([{ id: 'P-1', name: 'Catalog' }]);
  sprintsApi.listByProject.mockResolvedValue([]);
  tasksApi.listByProject.mockResolvedValue([{ id: 'T-1', title: 'Search products', status: 'done' }]);
  tasksApi.getAvailableTransitions.mockResolvedValue({ allowed_statuses: [] });
  show(<TasksPage />);
  fireEvent.click(await screen.findByText('Search products'));
  expect(await screen.findByText('Merged')).toBeVisible();
  expect(screen.getByText('Failed', { exact: true })).toBeVisible();
  expect(screen.getByText('No matching production event.')).toBeVisible();
  expect(screen.getByText(/Developer addresses the failing checks/)).toBeVisible();
  expect(screen.getByText('Match the nearest available product.')).toBeVisible();
  expect(screen.getByRole('link', { name: /Faster catalog search/ })).toHaveAttribute('href', 'https://github.com/org/catalog/pull/7');
  fireEvent.click(screen.getByText('Test reports (1)'));
  expect(screen.getByText(/Imported GitHub artifact/)).toBeVisible();
  expect(screen.getByRole('link', { name: 'Run 37 (attempt 2)' })).toHaveAttribute('href', 'https://github.com/org/catalog/actions/runs/37/attempts/2');
  expect(screen.queryByRole('button', { name: 'Record release approval' })).not.toBeInTheDocument();
});

it('records a reasoned hold against the reviewed evidence and reads back the decision', async () => {
  tasksApi.recordReleaseDecision.mockResolvedValue({});
  tasksApi.getDelivery.mockResolvedValueOnce(delivery).mockResolvedValue({
    ...delivery, decision_version: 'second', release_decision: { ...approved, decision: 'hold', reason: 'Wait for QA' },
  });
  show();
  const hold = await screen.findByRole('button', { name: 'Record hold' });
  expect(hold).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Decision reason'), { target: { value: ' Wait for QA ' } });
  fireEvent.click(hold);
  await waitFor(() => expect(tasksApi.recordReleaseDecision).toHaveBeenCalledWith('T-1', {
    decision: 'hold', revision, decision_version: 'first', reason: 'Wait for QA',
  }));
  expect(await screen.findByText('Release held')).toBeVisible();
  expect(screen.getByText('Wait for QA')).toBeVisible();
});

it('shows an obsolete approval as history and offers no decision controls for a read-only viewer', async () => {
  tasksApi.getDelivery.mockResolvedValue({
    ...delivery, revision: null, revision_kind: null, can_decide: false, qa: { status: 'unknown', runs: [] },
    readiness: { status: 'unknown', reason: 'No linked revision.' },
    release_decision: { ...approved, is_current: false },
  });
  show();
  expect(await screen.findByText('Previous decision · Release approved')).toBeVisible();
  expect(screen.getByText(/Team Lead confirms which pull request/)).toBeVisible();
  expect(screen.queryByRole('button', { name: /Record (hold|release approval)/ })).not.toBeInTheDocument();
});

it('requires QA to explicitly verify coverage and never offers DevOps approval to that reviewer', async () => {
  tasksApi.getDelivery.mockResolvedValue({
    ...delivery, qa: { status: 'passed', runs: [] }, can_verify_qa: true, can_decide: false,
    readiness: { status: 'awaiting_review', reason: 'QA must confirm required checks.' },
  });
  show();
  fireEvent.change(await screen.findByLabelText('Verification note'), { target: { value: 'Reviewed the search acceptance cases' } });
  fireEvent.click(screen.getByRole('button', { name: 'Verify QA coverage' }));
  await waitFor(() => expect(tasksApi.recordReleaseDecision).toHaveBeenCalledWith('T-1', {
    reason: 'Reviewed the search acceptance cases', decision: 'verify_qa', revision, decision_version: 'first',
  }));
  expect(screen.queryByRole('button', { name: 'Record release approval' })).not.toBeInTheDocument();
});

it('refreshes on a stale approval conflict and requires a fresh review after evidence changes', async () => {
  const green = { ...delivery, can_approve: true, qa: { status: 'passed', runs: [] },
    readiness: { status: 'awaiting_review' }, qa_verification: { ...approved, decision: 'verify_qa' } };
  tasksApi.getDelivery.mockResolvedValueOnce(green).mockResolvedValue({ ...delivery, decision_version: 'second' });
  tasksApi.recordReleaseDecision.mockRejectedValue(Object.assign(new Error('Stale'), { status: 409 }));
  show();
  fireEvent.change(await screen.findByLabelText('Decision reason'), { target: { value: 'Reviewed results' } });
  fireEvent.click(screen.getByRole('button', { name: 'Record release approval' }));
  expect(await screen.findByText(/evidence or decision changed/)).toBeVisible();
  expect(screen.getByLabelText('Decision reason')).toHaveValue('');
  expect(screen.queryByRole('button', { name: 'Record release approval' })).not.toBeInTheDocument();
  expect(screen.getByText('No matching production event.')).toBeVisible();
});

it('suppresses previously loaded evidence and controls when a refresh loses access', async () => {
  tasksApi.getDelivery.mockResolvedValueOnce(delivery).mockRejectedValue(new Error('Project access denied'));
  show();
  await screen.findByRole('button', { name: 'Record hold' });
  fireEvent.click(screen.getByRole('button', { name: 'Refresh evidence' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Project access denied');
  expect(screen.queryByText('Merged')).not.toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Record hold' })).not.toBeInTheDocument();
});

it('directs a blocked release with passing reports back to CI review', async () => {
  tasksApi.getDelivery.mockResolvedValue({ ...delivery, qa: { status: 'passed', runs: [] },
    readiness: { status: 'blocked', reason: 'Required CI checks are pending.' } });
  show();
  expect(await screen.findByText(/Team Lead reviews the release blocker/)).toBeVisible();
  expect(screen.getByText('Required CI checks are pending.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Record release approval' })).not.toBeInTheDocument();
});

it('reads back an approved release after QA verification and distinguishes an observed deployment from permission to deploy', async () => {
  const green = {
    ...delivery, qa: { status: 'passed', runs: [] }, readiness: { status: 'awaiting_review', reason: 'QA must confirm required checks.' },
    qa_verification: { ...approved, actor_name: 'Remi', decision: 'verify_qa' }, can_approve: true,
  };
  tasksApi.recordReleaseDecision.mockResolvedValue({});
  tasksApi.getDelivery.mockResolvedValueOnce(green).mockResolvedValueOnce({
    ...green, decision_version: 'second', release_decision: approved,
  }).mockResolvedValue({ ...green, decision_version: 'third', production: { status: 'deployed', observed_at: '2026-11-23T10:10:00Z' },
    release_decision: { ...approved, decision: 'hold' } });
  show();
  fireEvent.change(await screen.findByLabelText('Decision reason'), { target: { value: 'Reviewed the fix' } });
  fireEvent.click(screen.getByRole('button', { name: 'Record release approval' }));
  expect(await screen.findByText('Release approved')).toBeVisible();
  expect(screen.getByText(/DevOps confirms the production deployment/)).toBeVisible();
  expect(screen.queryByText('QA must confirm required checks.')).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Refresh evidence' }));
  expect(await screen.findByText(/deployment against the recorded hold/)).toBeVisible();
  expect(screen.getByText('Deployment reported')).toBeVisible();
});
