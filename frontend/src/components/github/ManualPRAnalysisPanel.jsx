import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../store/useAuthStore';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { prWorkflowsApi } from '../../api/prWorkflows.api';
import { Card } from '../common/Card';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import { Button } from '../common/Button';

const names = { code_analysis: 'Code', qa_analysis: 'QA' };
const titles = {
  COLLABORATIVE_ADVISORY: 'Two-specialist advisory report',
  PARTIAL_COLLABORATIVE_ADVISORY: 'Partial collaborative advisory',
  PARTIAL_SINGLE_SPECIALIST_ADVISORY: 'Single-specialist advisory — partial',
  INSUFFICIENT_EVIDENCE: 'Insufficient evidence', FAILED: 'Analysis unavailable', STALE_ADVISORY: 'Advisory for an earlier PR revision',
};
const messages = {
  NO_QA_EVIDENCE: 'No matching QA evidence was available.', NO_CODE_EVIDENCE: 'No supported Code evidence was available.',
  RETRY_EXHAUSTED: 'Retry budget exhausted. Partial evidence is retained.',
  MODEL_UNAVAILABLE: 'The model was unavailable.', MODEL_TIMEOUT: 'The model timed out.',
  INVALID_MODEL_OUTPUT: 'The model response could not be validated.',
  AUTHORIZATION_OR_SCOPE_REVOKED: 'Project access or permissions changed.',
  REGISTERED_QA_SOURCE_UNAVAILABLE: 'A registered QA source was unavailable.',
  CI_COUNTS_ARE_RECORDED_SUBMISSIONS_NOT_INDEPENDENT_EXECUTION_PROOF: 'CI counts are recorded submissions; execution was not independently verified.',
  STRUCTURAL_FACTS_DO_NOT_PROVE_CORRECTNESS: 'Structural observations do not establish correctness.',
  MODEL_STATEMENTS_ARE_ADVISORY: 'Model statements remain advisory.',
  CANCELLED_BY_REQUESTER: 'You cancelled this analysis. Nothing produced after cancelling was kept.',
};
const label = (value) => messages[value] || String(value || '').replaceAll('_', ' ').toLowerCase();
const claimLabels = { SUPPORTED: 'Supported structured observation', PROPOSED: 'Proposed interpretation',
  CONFLICTING: 'Conflicting claim', UNSUPPORTED: 'Unsupported claim' };

function errorMessage(error) {
  const status = error?.status ?? error?.response?.status;
  if (status === 403 || status === 401) return 'Access is no longer authorized. Analysis content is hidden.';
  if (status === 404) return 'Manual PR analysis is unavailable or not enabled for this account.';
  if (status === 429) return error?.message || 'Another request is being prepared. Retry shortly.';
  if (status === 409) return error?.message || 'This analysis has already finished.';
  if (status === 503) return 'The analysis service is temporarily unavailable. Please retry.';
  return error?.message || 'Unable to load this advisory analysis.';
}

function useManualAnalysisUser() {
  const user = useAuthStore((state) => state.user);
  if (import.meta.env.VITE_PR_MULTI_AGENT_MANUAL_ENABLED !== 'true' || !user?.employee_id
      || !hasPermission(user, PERMISSIONS.TRIGGER_AI_EVALUATION)
      || !hasPermission(user, PERMISSIONS.VIEW_AI_EVALUATION)) return null;
  return user;
}

export function ManualPRAnalysisPanel() {
  const user = useManualAnalysisUser();
  if (!user) return null;
  return <AnalysisForm key={`${user.employee_id}:${user.org_id || ''}`} user={user} />;
}

export function TaskPRAdvisory({ projectId, pr }) {
  const user = useManualAnalysisUser();
  if (!user?.org_id || !projectId || !pr.repository || !Number.isSafeInteger(pr.number) || pr.number < 1
      || !/^[a-f0-9]{40}$/.test(pr.head_sha || '')) return null;
  const params = { project_id: projectId, repository: pr.repository, pr_number: pr.number, head_sha: pr.head_sha };
  return <AdvisoryLookup key={JSON.stringify([user.employee_id, user.org_id, params])} user={user} params={params} />;
}

function AdvisoryLookup({ user, params }) {
  const [open, setOpen] = useState(false);
  return <div>
    <Button size="sm" variant="ghost" aria-expanded={open} onClick={() => setOpen(!open)}>
      {open ? 'Close PR head advisory' : 'View PR head advisory'}
    </Button>
    {open && <PublishedAdvisory user={user} params={params} />}
  </div>;
}

function PublishedAdvisory({ user, params }) {
  const report = useQuery({
    queryKey: ['manual-pr-head-report', user.employee_id, user.org_id, params],
    queryFn: ({ signal }) => prWorkflowsApi.lookupReport(params, signal), gcTime: 0, retry: false,
    staleTime: 0, refetchOnMount: 'always',
  });
  if (report.isFetching || report.isPending) return <p role="status">Checking for your published advisory…</p>;
  if (report.isError) return <p role="alert">{errorMessage(report.error)}{' '}
    <Button size="sm" variant="ghost" onClick={() => report.refetch()}>Retry</Button></p>;
  if (report.data === null) return <p>No published advisory from your account for this PR head.</p>;
  const scope = report.data?.scope;
  if (scope?.owner_id !== user.employee_id || scope.organization_id !== user.org_id
      || scope.project_id !== params.project_id || scope.repository?.toLowerCase() !== params.repository.toLowerCase()
      || scope.pr_number !== params.pr_number || scope.head_sha !== params.head_sha) {
    return <p role="alert">The advisory source differs from this task’s PR head. Refresh the task evidence.</p>;
  }
  return <div>
    <p>Analyzed PR head <code>{scope.head_sha}</code> against base <code>{scope.base_sha}</code>.</p>
    <p>QA and DevOps review the merge commit separately for release.</p>
    <AdvisoryReport report={report.data} />
  </div>;
}

function AnalysisForm({ user }) {
  const [project, setProject] = useState('');
  const [pr, setPr] = useState('');
  const [jobId, setJobId] = useState('');
  const [existingId, setExistingId] = useState('');
  const [validation, setValidation] = useState('');
  const [workflowRun, setWorkflowRun] = useState('');
  const imported = useMutation({ mutationFn: (request) => prWorkflowsApi.importActionsResults(project, request) });
  const identity = [user.employee_id, user.org_id];
  const projects = useQuery({ queryKey: ['manual-pr-projects', ...identity], queryFn: ({ signal }) => prWorkflowsApi.projects(signal),
    retry: false, gcTime: 0 });
  const start = useMutation({ mutationFn: (request) => prWorkflowsApi.start(request), onSuccess: (job) => setJobId(job.job_id) });
  const status = useQuery({ queryKey: ['manual-pr-status', ...identity, jobId], enabled: !!jobId,
    queryFn: ({ signal }) => prWorkflowsApi.status(jobId, signal), retry: false, gcTime: 0,
    refetchInterval: (query) => query.state.error || ['FINALIZED', 'FAILED', 'CANCELLED'].includes(query.state.data?.status) ? false : 2000 });
  // AI-02: the requester can stop a queued or running analysis.
  const cancel = useMutation({ mutationFn: () => prWorkflowsApi.cancel(jobId), onSuccess: () => status.refetch() });
  const report = useQuery({ queryKey: ['manual-pr-report', ...identity, jobId],
    enabled: !!jobId && !!status.data?.report_available && !status.isError,
    queryFn: ({ signal }) => prWorkflowsApi.report(jobId, signal), retry: false, gcTime: 0 });
  const error = validation || (start.error ? errorMessage(start.error) : '')
    || (status.error ? errorMessage(status.error) : '') || (report.error ? errorMessage(report.error) : '')
    || (cancel.error ? errorMessage(cancel.error) : '');
  const options = (projects.data?.projects || []).map((item) => ({ value: item.id, label: item.name }));
  const data = error ? null : status.data;
  const analysis = error ? null : report.data;

  function submit(event) {
    event.preventDefault();
    const number = Number(pr);
    if (!project || !Number.isSafeInteger(number) || number < 1) {
      setValidation('Choose a project and enter a positive pull request number.');
      return;
    }
    setValidation(''); setJobId('');
    start.mutate({ project_id: project, pr_number: number });
  }

  async function refresh() {
    const current = await status.refetch();
    if (!current.isError && current.data?.report_available) await report.refetch();
  }

  return <Card title="Manual PR analysis" style={{ marginTop: '1.5rem' }}>
    <p>AI-assisted advisory analysis for review. Select a project’s connected repository and a pull request.</p>
    <form aria-label="Manual PR analysis" onSubmit={submit} noValidate
      style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', alignItems: 'end', margin: '1rem 0' }}>
      <Select label="Analysis project" value={project} options={options} disabled={start.isPending || projects.isPending || projects.isError}
        onChange={(event) => { setProject(event.target.value); setJobId(''); start.reset(); imported.reset(); setValidation(''); }} required />
      <Input label="Pull request number" type="number" min="1" value={pr} disabled={start.isPending}
        onChange={(event) => setPr(event.target.value)} required />
      <Button type="submit" disabled={start.isPending || projects.isPending || projects.isError}>Start advisory analysis</Button>
    </form>
    {hasPermission(user, PERMISSIONS.MANAGE_TEST_AUTOMATION) && <section aria-label="Published QA evidence">
      <p>Import existing GitHub Actions JUnit and coverage artifacts before starting a new analysis. This reads published reports; it does not run tests or change GitHub. Existing immutable reports are not rewritten.</p>
      <Input label="GitHub Actions run ID" value={workflowRun} inputMode="numeric" onChange={(event) => setWorkflowRun(event.target.value)} />
      <Button variant="secondary" disabled={imported.isPending || !project || !pr} onClick={() => {
        const number = Number(pr), run = Number(workflowRun);
        if (!Number.isSafeInteger(number) || number < 1 || !Number.isSafeInteger(run) || run < 1) {
          setValidation('Enter a positive PR number and GitHub Actions run ID.'); return;
        }
        setValidation(''); imported.mutate({ pr_number: number, workflow_run_id: run });
      }}>Import published QA results</Button>
      {imported.isPending && <p role="status">Verifying published QA artifacts…</p>}
      {imported.isError && <p role="alert">{imported.error?.message || 'Published QA reports unavailable.'}</p>}
      {imported.data && <p role="status">Imported {imported.data.test_run_ids.length} published test report(s). Coverage: {imported.data.coverage_status}. Counts remain CI-reported evidence, not independent proof.</p>}
    </section>}
    {projects.isPending && <p role="status">Loading authorized projects…</p>}
    {projects.isError && <p role="alert">{errorMessage(projects.error)}</p>}
    {projects.data?.truncated && <p>Showing the first 100 authorized projects.</p>}
    {start.isPending && <p role="status">Preparing the pinned analysis…</p>}
    <details>
      <summary>Open a previous analysis</summary>
      <form onSubmit={(event) => {
        event.preventDefault();
        if (!/^[a-f0-9]{64}$/.test(existingId.trim())) { setValidation('Enter a valid analysis ID.'); return; }
        setValidation(''); start.reset(); setJobId(existingId.trim());
      }}>
        <Input label="Existing analysis ID" value={existingId} onChange={(event) => setExistingId(event.target.value)} disabled={start.isPending} />
        <Button type="submit" disabled={start.isPending}>Open analysis</Button>
      </form>
    </details>
    {error && <p role="alert">{error}</p>}
    {jobId && <div style={{ marginTop: '1rem', overflowWrap: 'anywhere' }}>
      <p>Analysis ID: <code>{jobId}</code></p>
      <Button variant="secondary" onClick={refresh} disabled={status.isFetching}>Refresh analysis</Button>
      {['PENDING', 'RUNNING', 'RETRY_WAIT'].includes(status.data?.status) &&
        <Button variant="ghost" onClick={() => cancel.mutate()} disabled={cancel.isPending}>
          {cancel.isPending ? 'Cancelling…' : 'Cancel analysis'}</Button>}
    </div>}
    {jobId && status.isPending && !status.isError && <p role="status">Loading analysis…</p>}
    {data && <section aria-label="Analysis progress" style={{ marginTop: '1rem', overflowWrap: 'anywhere' }}>
      <p role="status">{({ PENDING: 'Queued for advisory analysis', RUNNING: 'Analyzing the pinned revision',
        RETRY_WAIT: 'Waiting to retry advisory analysis', FAILED: 'Analysis stopped', FINALIZED: 'Advisory report ready',
        CANCELLED: 'Analysis cancelled' })[data.status]}</p>
      <p>{data.repository} · PR #{data.pr_number} · Revision <code>{data.head_sha}</code></p>
      <p>Evidence snapshot: <code>{data.snapshot_id}</code></p>
      <ul>{data.specialists?.map((step) => <li key={step.specialist}>{names[step.specialist]}: {label(step.status)}
        {step.error_code && <> — {label(step.error_code)}</>}</li>)}</ul>
      {data.status !== 'FINALIZED' && data.failure_reason && <p>{label(data.failure_reason)}</p>}
      {data.limitations?.length > 0 && <ul>{data.limitations.map((item) => <li key={item}>{label(item)}</li>)}</ul>}
    </section>}
    {data?.report_available && report.isPending && <p role="status">Loading advisory report…</p>}
    {analysis && <AdvisoryReport report={analysis} />}
  </Card>;
}

function AdvisoryReport({ report }) {
  if (report.schema_version !== 'pr-multi-agent-report-v2' || !titles[report.status]) {
    return <p role="alert">Unsupported advisory report format.</p>;
  }
  const references = new Map((report.snapshot?.references || []).map((item) => [item.evidence_id, item.source_reference]));
  return <section aria-label="AI-assisted advisory report" style={{ marginTop: '1rem', overflowWrap: 'anywhere' }}>
    <h3>{titles[report.status]}</h3>
    <p>AI-assisted advisory analysis. Publication records the report; it does not approve a change.</p>
    {report.outcomes?.map((outcome) => <div key={outcome.specialist}>
      <h4>{names[outcome.specialist]} contribution — {label(outcome.status)}</h4>
      {outcome.summary && <p>{outcome.summary}</p>}
      {outcome.error_code && <p>{label(outcome.error_code)}</p>}
      {outcome.limitations?.map((item) => <p key={item}>{label(item)}</p>)}
    </div>)}
    <h4>Claims and evidence</h4>
    <ul>{report.claims?.map((claim) => <li key={claim.claim_id} style={{ marginBottom: '1rem' }}>
      <strong>{claimLabels[claim.assertion_status] || 'Unsupported claim'}</strong> · {names[claim.specialist]}
      {claim.supported_conclusion && <p>{claim.supported_conclusion}</p>}
      <p>AI statement: {claim.draft?.statement}</p>
      {claim.reason && <p>{label(claim.reason)}</p>}
      {claim.conflicts_with?.length > 0 && <p>Conflicts with: {claim.conflicts_with.join(', ')}</p>}
      <ul>{claim.draft?.evidence_refs?.map((reference) => <li key={reference}><code>{references.get(reference) || 'Source unavailable'}</code></li>)}</ul>
    </li>)}</ul>
    <h4>Limitations and unavailable evidence</h4>
    <ul>{report.limitations?.map((item) => <li key={item}>{label(item)}</li>)}</ul>
  </section>;
}
