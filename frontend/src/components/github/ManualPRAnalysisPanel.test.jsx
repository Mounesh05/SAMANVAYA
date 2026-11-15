import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../tests/utils/test-utils';
import { useAuthStore } from '../../store/useAuthStore';
import { prWorkflowsApi } from '../../api/prWorkflows.api';
import { ManualPRAnalysisPanel } from './ManualPRAnalysisPanel';
import { withPermissions } from '../../tests/utils/roleUser';

vi.mock('../../api/prWorkflows.api', () => ({ prWorkflowsApi: { projects: vi.fn(), start: vi.fn(), status: vi.fn(), report: vi.fn() } }));

const id = 'a'.repeat(64);
const pending = { schema_version: 'pr-workflow-status-v1', job_id: id, status: 'PENDING', project_id: 'P1',
  repository: 'owner/repo', pr_number: 7, head_sha: 'b'.repeat(40), snapshot_id: 'c'.repeat(64),
  specialists: [{ specialist: 'code_analysis', status: 'WAITING' }, { specialist: 'qa_analysis', status: 'WAITING' }], limitations: [] };
const partial = { schema_version: 'pr-multi-agent-report-v2', status: 'PARTIAL_SINGLE_SPECIALIST_ADVISORY', collaboration: 'SINGLE_SPECIALIST',
  outcomes: [{ specialist: 'code_analysis', status: 'SUCCEEDED', summary: 'Private advisory contribution' },
    { specialist: 'qa_analysis', status: 'SKIPPED', error_code: 'NO_QA_EVIDENCE' }],
  claims: [{ claim_id: 'code-1', specialist: 'code_analysis', assertion_status: 'SUPPORTED', supported_conclusion: 'module.py: function_count = 1',
    draft: { statement: 'Model interpretation stays advisory', evidence_refs: ['e1'] } }],
  snapshot: { references: [{ evidence_id: 'e1', source_reference: 'github://owner/repo/module.py@revision' }] },
  limitations: ['STRUCTURAL_FACTS_DO_NOT_PROVE_CORRECTNESS'] };

function ready(report = partial) {
  prWorkflowsApi.status.mockResolvedValue({ ...pending, status: 'FINALIZED', report_available: true,
    analysis_status: report.status, specialists: report.outcomes });
  prWorkflowsApi.report.mockResolvedValue(report);
}

async function submit() {
  await screen.findByRole('option', { name: 'Project One' });
  fireEvent.change(screen.getByLabelText(/Analysis project/), { target: { value: 'P1' } });
  fireEvent.change(screen.getByLabelText(/Pull request number/), { target: { value: '7' } });
  fireEvent.click(screen.getByRole('button', { name: 'Start advisory analysis' }));
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.stubEnv('VITE_PR_MULTI_AGENT_MANUAL_ENABLED', 'true');
  useAuthStore.setState({ user: withPermissions({ employee_id: 'A', role: 'LEAD', org_id: 'O1' }) });
  prWorkflowsApi.projects.mockResolvedValue({ projects: [{ id: 'P1', name: 'Project One' }] });
  prWorkflowsApi.start.mockResolvedValue({ job_id: id, status: 'PENDING' });
  prWorkflowsApi.status.mockResolvedValue(pending);
});
afterEach(() => { cleanup(); vi.unstubAllEnvs(); useAuthStore.setState({ user: null }); });

describe('manual PR advisory panel', () => {
  it('does not render or request data when the build flag is off', () => {
    vi.stubEnv('VITE_PR_MULTI_AGENT_MANUAL_ENABLED', 'false');
    renderWithProviders(<ManualPRAnalysisPanel />);
    expect(screen.queryByText('Manual PR analysis')).not.toBeInTheDocument();
    expect(prWorkflowsApi.projects).not.toHaveBeenCalled();
    expect(prWorkflowsApi.start).not.toHaveBeenCalled();
  });

  it.each([{ role: 'HR', is_admin: true }, { role: 'DEVELOPER' }])('excludes ineligible accounts: $role', (change) => {
    useAuthStore.setState({ user: withPermissions({ employee_id: 'A', org_id: 'O1', ...change }) });
    renderWithProviders(<ManualPRAnalysisPanel />);
    expect(prWorkflowsApi.projects).not.toHaveBeenCalled();
    expect(screen.queryByText('Manual PR analysis')).not.toBeInTheDocument();
  });

  it('submits only project and PR identifiers and shows queued progress', async () => {
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    await screen.findByText('Queued for advisory analysis');
    expect(prWorkflowsApi.start).toHaveBeenCalledWith({ project_id: 'P1', pr_number: 7 });
    expect(prWorkflowsApi.projects).toHaveBeenCalled();
    expect(screen.getByText(/AI-assisted advisory analysis/)).toBeVisible();
    expect(prWorkflowsApi.report).not.toHaveBeenCalled();
  });

  it('shows preparation/loading while submission is outstanding', async () => {
    prWorkflowsApi.start.mockReturnValue(new Promise(() => {}));
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    expect(await screen.findByText('Preparing the pinned analysis…')).toBeVisible();
    expect(screen.getByLabelText(/Analysis project/)).toBeDisabled();
  });

  it('keeps single-specialist results explicitly partial with evidence and missing QA', async () => {
    ready();
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    expect(await screen.findByText('Single-specialist advisory — partial')).toBeVisible();
    expect(screen.getByText('Supported structured observation')).toBeVisible();
    expect(screen.getByText('module.py: function_count = 1')).toBeVisible();
    expect(within(screen.getByRole('region', { name: 'AI-assisted advisory report' })).getByText(/No matching QA evidence/)).toBeVisible();
    expect(screen.getByText('github://owner/repo/module.py@revision')).toBeVisible();
    expect(screen.queryByText('Two-specialist advisory report')).not.toBeInTheDocument();
  });

  it('shows two contributions, proposals, conflicts and safe plain-text claims', async () => {
    ready({ ...partial, status: 'PARTIAL_COLLABORATIVE_ADVISORY', collaboration: 'TWO_SPECIALIST',
      outcomes: [...partial.outcomes.slice(0, 1), { specialist: 'qa_analysis', status: 'SUCCEEDED', summary: 'QA contribution' }],
      claims: [{ ...partial.claims[0], assertion_status: 'PROPOSED', supported_conclusion: null },
        { ...partial.claims[0], claim_id: 'qa-1', specialist: 'qa_analysis', assertion_status: 'CONFLICTING', supported_conclusion: null,
          draft: { statement: '<script>deploy()</script>', evidence_refs: ['e1'] }, conflicts_with: ['code-1'] }] });
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    await screen.findByText('Partial collaborative advisory');
    expect(screen.getByText('Proposed interpretation')).toBeVisible();
    expect(screen.getByText('Conflicting claim')).toBeVisible();
    expect(screen.getByText('AI statement: <script>deploy()</script>')).toBeVisible();
    expect(document.querySelector('script')).toBeNull();
    expect(screen.getByText('QA contribution')).toBeVisible();
  });

  it('shows retry exhaustion without attempting to fetch a nonexistent report', async () => {
    prWorkflowsApi.status.mockResolvedValue({ ...pending, status: 'FAILED', failure_reason: 'RETRY_EXHAUSTED' });
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    expect(await screen.findByText('Analysis stopped')).toBeVisible();
    expect(screen.getByText(/Retry budget exhausted/)).toBeVisible();
    expect(prWorkflowsApi.report).not.toHaveBeenCalled();
  });

  it('loads an existing analysis without another submission', async () => {
    ready({ ...partial, status: 'COLLABORATIVE_ADVISORY', collaboration: 'TWO_SPECIALIST',
      outcomes: [partial.outcomes[0], { specialist: 'qa_analysis', status: 'SUCCEEDED', summary: 'QA advisory' }] });
    renderWithProviders(<ManualPRAnalysisPanel />);
    fireEvent.change(screen.getByLabelText('Existing analysis ID'), { target: { value: id } });
    fireEvent.click(screen.getByRole('button', { name: 'Open analysis' }));
    expect(await screen.findByText('Two-specialist advisory report')).toBeVisible();
    expect(prWorkflowsApi.start).not.toHaveBeenCalled();
  });

  it('hides cached advisory data after an authorization error on refresh', async () => {
    ready();
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    await screen.findByText('Private advisory contribution');
    prWorkflowsApi.status.mockRejectedValue(Object.assign(new Error('Access revoked'), { response: { status: 403 } }));
    fireEvent.click(screen.getByRole('button', { name: 'Refresh analysis' }));
    await screen.findByRole('alert');
    await waitFor(() => expect(screen.queryByText('Private advisory contribution')).not.toBeInTheDocument());
    expect(screen.queryByText('github://owner/repo/module.py@revision')).not.toBeInTheDocument();
  });

  it('surfaces the backend-disabled response and leaves the original workflow untouched', async () => {
    prWorkflowsApi.start.mockRejectedValue(Object.assign(new Error('disabled'), { response: { status: 404 } }));
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    expect(await screen.findByRole('alert')).toHaveTextContent(/unavailable or not enabled/);
    expect(prWorkflowsApi.status).not.toHaveBeenCalled();
  });

  it.each([
    ['FAILED', 'Analysis unavailable'], ['INSUFFICIENT_EVIDENCE', 'Insufficient evidence'],
    ['STALE_ADVISORY', 'Advisory for an earlier PR revision'],
  ])('labels a finalized %s analysis without implying collaboration', async (status, title) => {
    ready({ ...partial, status });
    renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    expect(await screen.findByText(title)).toBeVisible();
    expect(screen.queryByText('Two-specialist advisory report')).not.toBeInTheDocument();
  });

  it('validates project, PR and historical ID before making requests', async () => {
    renderWithProviders(<ManualPRAnalysisPanel />);
    await screen.findByRole('option', { name: 'Project One' });
    fireEvent.click(screen.getByRole('button', { name: 'Start advisory analysis' }));
    expect(await screen.findByRole('alert')).toHaveTextContent(/positive pull request number/);
    expect(prWorkflowsApi.start).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('Existing analysis ID'), { target: { value: 'foreign/not-a-job' } });
    fireEvent.click(screen.getByRole('button', { name: 'Open analysis' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter a valid analysis ID.');
    expect(prWorkflowsApi.status).not.toHaveBeenCalled();
  });

  it('does not reuse one account’s analysis when the signed-in identity changes', async () => {
    ready();
    const view = renderWithProviders(<ManualPRAnalysisPanel />);
    await submit();
    await screen.findByText('Private advisory contribution');
    view.unmount();
    useAuthStore.setState({ user: withPermissions({ employee_id: 'B', role: 'LEAD', org_id: 'O2' }) });
    renderWithProviders(<ManualPRAnalysisPanel />);
    expect(screen.queryByText('Private advisory contribution')).not.toBeInTheDocument();
    expect(screen.queryByText('Analysis ID:')).not.toBeInTheDocument();
  });
});
