import React from 'react';
import { beforeEach, expect, it, vi } from 'vitest';
import { Route, Routes } from 'react-router-dom';
import { fireEvent, renderWithProviders, screen, waitFor, within } from '../../tests/utils/test-utils';
import { projectsApi } from '../../api/projects.api';
import { algorithmsApi } from '../../api/algorithms.api';
import { releasesApi } from '../../api/releases.api';
import { PERMISSIONS } from '../../auth/permissions';
import { canOpenPage, showInMenu } from '../../routes/access';
import { useAuthStore } from '../../store/useAuthStore';
import { ReleaseManagementPage } from './ReleaseManagementPage';

vi.mock('../../api/projects.api');
vi.mock('../../api/algorithms.api');
vi.mock('../../api/releases.api');
const revision = '1'.repeat(40);
const baseline = '0'.repeat(40);
const manifest = {
  repository: 'example/platform', baseline_sha: baseline, target_sha: revision, kind: 'hotfix', complete: true,
  artifact: { id: 92, digest: 'abcd', run_id: 80, run_attempt: 2, verified: true },
  pull_requests: [
    { number: 11, title: 'Add search', merge_commit_sha: revision, task_ids: ['TSK-A'] },
    { number: 12, title: 'Update retries', merge_commit_sha: revision, task_ids: ['TSK-B'] },
  ],
  tasks: [
    { id: 'TSK-A', title: 'Implement search', story: { title: 'Search', acceptance_criteria: ['Return matching records'] }, status: 'done' },
    { id: 'TSK-B', title: 'Retry failed requests', status: 'in_progress', assignee_id: 'developer-1' },
  ],
};
const candidate = {
  id: 'REL-A', version: 2, manifest, manifest_digest: 'manifest-2', state: 'awaiting_qa',
  blockers: ['Combined workflow evidence has not arrived.'],
  evidence: { qa: { status: 'unknown', runs: [] }, coverage_status: 'missing' },
  evidence_digest: 'evidence-2', can: {}, history: [],
};
const setRole = (role) => useAuthStore.setState({user: {
  employee_id: role, role, org_id: 'org',
  permissions: role === 'DEVOPS' ? [PERMISSIONS.RECORD_RELEASE_DECISION] : [],
}});
const view = (route) => renderWithProviders(
  <Routes><Route path="/releases/:projectId?/:releaseId?" element={<ReleaseManagementPage />} /></Routes>, {route},
);

beforeEach(() => {
  vi.resetAllMocks();
  setRole('DEVOPS');
  projectsApi.list.mockResolvedValue([{ id: 'PRJ-A', name: 'Example project' }]);
  releasesApi.list.mockResolvedValue({ enabled: true, releases: [candidate], baseline: { revision: baseline, source: 'observed' } });
  releasesApi.get.mockResolvedValue(candidate);
});

it('opens the exact candidate from the list and renders multiple PRs and tasks with missing combined evidence', async () => {
  view('/releases/PRJ-A');
  fireEvent.click(await screen.findByRole('link', { name: 'REL-A' }));
  expect(await screen.findByRole('link', { name: '#11 Add search' })).toHaveAttribute('href', 'https://github.com/example/platform/pull/11');
  expect(screen.getByRole('link', { name: '#12 Update retries' })).toBeVisible();
  expect(screen.getByRole('link', { name: 'Implement search' })).toHaveAttribute('href', '/tasks?project=PRJ-A&task=TSK-A');
  expect(screen.getByRole('link', { name: 'Retry failed requests' })).toBeVisible();
  expect(screen.getByText('Return matching records')).toBeVisible();
  expect(screen.getByText('Coverage unavailable')).toBeVisible();
  expect(screen.getByText('No test reports for this exact target commit.')).toBeVisible();
  expect(screen.getByText('No deployment observed')).toBeVisible();
});

it('discovers candidates with an exact baseline, build run, artifact, and release type', async () => {
  releasesApi.create.mockResolvedValue(candidate);
  view('/releases/PRJ-A');
  fireEvent.change(await screen.findByLabelText(/^Target commit SHA/), { target: { value: revision } });
  fireEvent.change(screen.getByLabelText(/^GitHub workflow run ID/), { target: { value: '80' } });
  fireEvent.change(screen.getByLabelText(/^GitHub artifact ID/), { target: { value: '92' } });
  fireEvent.change(screen.getByLabelText('Release type'), { target: { value: 'hotfix' } });
  fireEvent.click(screen.getByRole('button', { name: 'Discover candidate' }));
  await waitFor(() => expect(releasesApi.create).toHaveBeenCalledWith('PRJ-A', {
    baseline_sha: baseline, target_sha: revision, run_id: 80, artifact_id: 92, kind: 'hotfix',
  }));
  expect(await screen.findByRole('heading', { name: 'Observed deployment' })).toBeVisible();
});

it('records QA verification for the reviewed version and keeps deployment observation separate', async () => {
  setRole('QA');
  releasesApi.get.mockResolvedValue({ ...candidate, can: { verify_qa: true }, evidence: {
    qa: { status: 'passed', runs: [{ id: 'qa-a', run_attempt: 2, test_suite: 'integration', status: 'passed', tests_passed: 23 }] },
    coverage_status: 'missing',
  }, deployment: { status: 'deployed', id: 87 }});
  releasesApi.act.mockResolvedValue({});
  view('/releases/PRJ-A/REL-A');
  fireEvent.click(await screen.findByRole('button', { name: 'Record QA verification' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Review rationale' }), { target: { value: 'Reviewed the exact release build.' } });
  expect(screen.getByRole('button', { name: 'Confirm QA verification' })).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox', { name: /reviewed all 2 included tasks/i }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm QA verification' }));
  await waitFor(() => expect(releasesApi.act).toHaveBeenCalledWith('PRJ-A', 'REL-A', {
    action: 'verify_qa', version: 2, evidence_digest: 'evidence-2', reason: 'Reviewed the exact release build.', verified_task_ids: ['TSK-A', 'TSK-B'],
  }));
  expect(screen.getByText('integration')).toBeVisible();
  expect(screen.getByText('Deployed')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Approve release' })).toBeNull();
});

it('refreshes stale evidence after a conflict and retains the rationale until another explicit confirmation', async () => {
  releasesApi.get.mockResolvedValueOnce({ ...candidate, can: { approve: true, hold: true } })
    .mockResolvedValue({ ...candidate, can: { hold: true }, version: 3, evidence_digest: 'evidence-3' });
  releasesApi.act.mockRejectedValueOnce(Object.assign(new Error('Conflict'), { status: 409 }));
  view('/releases/PRJ-A/REL-A');
  fireEvent.click(await screen.findByRole('button', { name: 'Approve release' }));
  fireEvent.change(screen.getByRole('textbox', { name: 'Review rationale' }), { target: { value: 'Reviewed deployment.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Confirm approval' }));
  expect(await screen.findByText(/This candidate changed/)).toBeVisible();
  expect(screen.getByRole('textbox', { name: 'Review rationale' })).toHaveValue('Reviewed deployment.');
  expect(screen.queryByRole('button', { name: 'Confirm approval' })).toBeNull();
  await waitFor(() => expect(screen.queryByRole('button', { name: 'Approve release' })).toBeNull());
  releasesApi.act.mockResolvedValueOnce({});
  fireEvent.click(screen.getByRole('button', { name: 'Place release on hold' }));
  fireEvent.click(screen.getByRole('button', { name: 'Confirm hold' }));
  await waitFor(() => expect(releasesApi.act).toHaveBeenLastCalledWith('PRJ-A', 'REL-A', {
    action: 'hold', version: 3, evidence_digest: 'evidence-3', reason: 'Reviewed deployment.',
  }));
});

it('filters release navigation by role and exposes access errors without rendering evidence', async () => {
  expect(canOpenPage({ role: 'HR', is_admin: true }, 'releases')).toBe(false);
  expect(showInMenu({ role: 'CEO' }, 'releases')).toBe(false);
  expect(showInMenu({ role: 'DEVELOPER' }, 'releases')).toBe(true);
  releasesApi.get.mockRejectedValue(Object.assign(new Error('Project release access denied'), { status: 403 }));
  view('/releases/PRJ-A/REL-A');
  expect(await screen.findByText('Project release access denied')).toBeVisible();
  expect(screen.queryByRole('link', { name: '#11 Add search' })).toBeNull();
});

it('reports disabled and empty release lists without exposing authoring actions', async () => {
  setRole('PM');
  releasesApi.list.mockResolvedValue({ enabled: true, releases: [] });
  const results = view('/releases/PRJ-A');
  const table = await screen.findByRole('table');
  expect(within(table).getByText('No release candidates found.')).toBeVisible();
  expect(screen.queryByRole('button', { name: 'Discover candidate' })).toBeNull();
  results.unmount();
  releasesApi.list.mockResolvedValue({ enabled: false, releases: [] });
  view('/releases/PRJ-A');
  expect(await screen.findByText('Release management is unavailable for this project.')).toBeVisible();
});

it('paginates decision history and exposes the original approval with its revision', async () => {
  releasesApi.get.mockResolvedValue({
    ...candidate,
    history: Array.from({ length: 25 }, (_, index) => ({
      version: index + 2, manifest_digest: 'new-manifest', record: { action: 'refresh', actor_id: 'ops', reason: `Refresh ${index + 2}` },
    })),
  });
  releasesApi.history.mockResolvedValue({
    has_more: false, history: [{ version: 1, manifest_digest: 'old-manifest', record: { action: 'approve', actor_id: 'original-reviewer', reason: 'Original review' } }],
  });
  view('/releases/PRJ-A/REL-A');
  const nav = await screen.findByRole('navigation', { name: 'Release history pages' });
  fireEvent.click(within(nav).getByRole('button', { name: 'Next' }));
  expect(await screen.findByText('Original review')).toBeVisible();
  expect(screen.getByText('original-reviewer')).toBeVisible();
  expect(screen.getByText('old-manifest')).toBeVisible();
  expect(releasesApi.history).toHaveBeenCalledWith('PRJ-A', 'REL-A', { offset: 25, limit: 25 }, expect.any(AbortSignal));
  expect(within(nav).getByRole('button', { name: 'Next' })).toBeDisabled();
});

it('shows engineering evidence only for the exact repository, project, PR, and revision', async () => {
  useAuthStore.setState({ user: {
    employee_id: 'lead', role: 'LEAD', org_id: 'org', permissions: [PERMISSIONS.VIEW_CODE_QUALITY],
  } });
  const scoped = {
    repository: manifest.repository, project_id: 'PRJ-A', head_sha: revision, pr_number: 11,
    run_id: 'alg-1', reason: 'Exact revision evidence', status: 'completed',
  };
  const pr = { ...manifest.pull_requests[0], head_sha: revision, local_pr_id: 'PR-11' };
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [
    scoped, { ...scoped, run_id: 'stale', head_sha: baseline, reason: 'Old head evidence' },
    { ...scoped, run_id: 'other-project', project_id: 'OTHER', reason: 'Foreign project evidence' },
  ] });
  releasesApi.get.mockResolvedValue({ ...candidate, manifest: { ...manifest, pull_requests: [pr] } });
  view('/releases/PRJ-A/REL-A');
  const disclosure = await screen.findByText('Code and algorithm evidence');
  const details = disclosure.closest('details');
  details.open = true;
  fireEvent(details, new Event('toggle'));
  expect(await screen.findByText('Exact revision evidence')).toBeVisible();
  expect(algorithmsApi.getPRIntelligence).toHaveBeenCalledWith({ pr_id: 'PR-11' });
  expect(screen.queryByText('Old head evidence')).toBeNull();
  expect(screen.queryByText('Foreign project evidence')).toBeNull();
});
