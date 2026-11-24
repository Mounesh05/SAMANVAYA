import React, { lazy, Suspense, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { projectsApi } from '../../api/projects.api';
import { releasesApi } from '../../api/releases.api';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { ErrorState } from '../../components/common/ErrorState';
import { Input } from '../../components/common/Input';
import { LoadingState } from '../../components/common/LoadingState';
import { Select } from '../../components/common/Select';
import { Table } from '../../components/common/Table';
import { Textarea } from '../../components/common/Textarea';
import { TaskPRAdvisory } from '../../components/github/ManualPRAnalysisPanel';
import { PageHeader } from '../../components/layout/PageHeader';
import { useAuthStore } from '../../store/useAuthStore';
import { useSessionScope } from '../../store/useSessionScope';
import './ReleaseManagementPage.css';

const PAGE_SIZE = 20;
const PRAlgorithmIntelligencePanel = lazy(() => import('../code-quality/PRAlgorithmIntelligencePanel')
  .then((module) => ({ default: module.PRAlgorithmIntelligencePanel })));
const sha = /^[a-f\d]{40}$/i;
const releasePath = (projectId, releaseId) => `/releases/${encodeURIComponent(projectId)}${releaseId ? `/${encodeURIComponent(releaseId)}` : ''}`;
const labels = {
  awaiting_qa: 'Awaiting QA verification', awaiting_qa_verification: 'Awaiting QA verification',
  awaiting_devops: 'Awaiting DevOps review', awaiting_devops_review: 'Awaiting DevOps review',
  evidence_incomplete: 'Evidence incomplete', on_hold: 'On hold', held: 'On hold',
  deployment_failed: 'Deployment failed', not_observed: 'No deployment observed',
  unknown: 'Unknown', verify_qa: 'QA verification', invalidated: 'Review out of date',
  unmerged: 'Unmerged', already_in_baseline: 'Included in baseline', after_target: 'Merged after target',
  outside_comparison: 'Outside candidate ancestry', tree_restored: 'Prior tree restored',
};
const stateLabel = (value) => value ? labels[value] || String(value).replaceAll('_', ' ').replace(/^./, (first) => first.toUpperCase()) : 'Unknown';
const displayTime = (value) => value && !Number.isNaN(Date.parse(value)) ? new Date(value).toLocaleString() : null;

function State({ value }) {
  const tone = ['approved', 'deployed', 'passed', 'success'].includes(value) ? 'success'
    : ['on_hold', 'held', 'failed', 'deployment_failed', 'evidence_incomplete', 'incomplete', 'invalidated'].includes(value) ? 'warning' : 'default';
  return <Badge size="sm" variant={tone}>{stateLabel(value)}</Badge>;
}

function Revision({ value, short = false }) {
  return value ? <code className="release-revision" title={value}>{short ? value.slice(0, 12) : value}</code> : 'Unavailable';
}

function Failures({ errors }) {
  if (!errors?.length) return null;
  const messages = errors.map((item) => typeof item === 'string' ? stateLabel(item)
    : item.message || item.detail || stateLabel(item.code));
  return <ul className="release-list">{[...new Set(messages)].map((message) => <li key={message}>{message}</li>)}</ul>;
}

function Field({ label, value }) {
  return <div><dt>{label}</dt><dd>{value ?? 'Unavailable'}</dd></div>;
}

export function ReleaseManagementPage() {
  const { projectId, releaseId } = useParams();
  const scope = useSessionScope();
  const navigate = useNavigate();
  const projects = useQuery({
    queryKey: ['release-projects', scope], queryFn: () => projectsApi.list(), retry: false,
  });
  if (projects.isPending) return <LoadingState message="Loading projects…" />;
  if (projects.error) return <ErrorState message={projects.error.message} onRetry={projects.refetch} />;
  const options = (projects.data || []).map((project) => ({ value: project.id, label: project.name || project.id }));
  const inScope = options.some((option) => option.value === projectId);
  return <div className="release-page">
    <PageHeader title="Release management" subtitle="Review the exact changes, test reports, and approvals for a deployment candidate." />
    <div className="release-project">
      <Select label="Project" value={inScope ? projectId : ''} options={options}
        onChange={(event) => navigate(event.target.value ? releasePath(event.target.value) : '/releases')} />
    </div>
    {projectId && !inScope ? <p role="alert">This project is unavailable to your account.</p>
      : !options.length ? <p>No projects are available to your account.</p>
        : !projectId ? <p>Select a project to see its release candidates.</p>
          : releaseId ? <ReleaseDetail key={JSON.stringify([scope, projectId, releaseId])} projectId={projectId} releaseId={releaseId} scope={scope} />
            : <ReleaseList key={JSON.stringify([scope, projectId])} projectId={projectId} scope={scope} />}
  </div>;
}

function ReleaseList({ projectId, scope }) {
  const user = useAuthStore((state) => state.user);
  const [search, setSearch] = useSearchParams();
  const pageNumber = Number(search.get('page'));
  const page = Number.isSafeInteger(pageNumber) && pageNumber > 0 ? pageNumber : 1;
  const listKey = ['releases', scope, projectId];
  const query = useQuery({
    queryKey: [...listKey, page], retry: false,
    queryFn: ({ signal }) => releasesApi.list(projectId, { offset: (page - 1) * PAGE_SIZE, limit: PAGE_SIZE }, signal),
  });
  if (query.isPending) return <LoadingState message="Loading releases…" />;
  if (query.error?.status === 404 || query.data?.enabled === false) return <p>Release management is unavailable for this project.</p>;
  if (query.error) return <ErrorState message={query.error.message} onRetry={query.refetch} />;
  const { releases = [], baseline, baseline_unavailable: baselineUnavailable, has_more: hasMore,
    can_create: canCreate, can_initialize_baseline: canInitialize } = query.data;
  const canManage = user?.role === 'DEVOPS' && hasPermission(user, PERMISSIONS.RECORD_RELEASE_DECISION);
  const columns = [
    { key: 'id', header: 'Candidate', render: (row) => <Link to={releasePath(projectId, row.id)}>{row.id}</Link> },
    { key: 'target_sha', header: 'Target commit', render: (row) => <Revision value={row.manifest?.target_sha || row.target_sha} short /> },
    { key: 'kind', header: 'Type', render: (row) => stateLabel(row.manifest?.kind || row.kind) },
    { key: 'scope', header: 'Scope', render: (row) => Number.isInteger(row.pr_count) ? `${row.pr_count} PRs · ${row.task_count} tasks` : 'Unavailable' },
    { key: 'state', header: 'Readiness', render: (row) => <State value={row.state} /> },
    { key: 'created_at', header: 'Created', render: (row) => displayTime(row.created_at) || 'Unavailable' },
  ];
  return <>
    <Card title="Release candidates">
      <Table columns={columns} data={releases} emptyMessage="No release candidates found." />
      {(page > 1 || hasMore || (hasMore == null && releases.length === PAGE_SIZE)) && <nav className="release-controls" aria-label="Release pages">
        <Button variant="secondary" disabled={page === 1 || query.isFetching} onClick={() => setSearch({ page: String(page - 1) })}>Previous</Button>
        <span>Page {page}</span>
        <Button variant="secondary" disabled={query.isFetching || !(hasMore ?? releases.length === PAGE_SIZE)}
          onClick={() => setSearch({ page: String(page + 1) })}>Next</Button>
      </nav>}
    </Card>
    {baselineUnavailable && <p role="status">The production baseline could not be verified. Saved release history remains available.</p>}
    {baseline?.revision && <Card title="Production baseline">
      <dl className="release-facts"><Field label="Verified revision" value={<Revision value={baseline.revision} />} />
        <Field label="Source" value={stateLabel(baseline.source)} /></dl>
    </Card>}
    {(canInitialize ?? (canManage && !baseline?.revision)) && <BaselineForm projectId={projectId} listKey={listKey} />}
    {(canCreate ?? canManage) && <CandidateForm projectId={projectId} baseline={baseline?.revision} listKey={listKey} />}
  </>;
}

function BaselineForm({ projectId, listKey }) {
  const cache = useQueryClient();
  const [error, setError] = useState('');
  const mutation = useMutation({
    mutationFn: (data) => releasesApi.initializeBaseline(projectId, data),
    onSuccess: () => cache.invalidateQueries({ queryKey: listKey }),
  });
  function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const revision = form.elements.revision.value.trim().toLowerCase();
    const reason = form.elements.reason.value.trim();
    if (!sha.test(revision) || !reason) {
      setError('Enter a 40-character commit SHA and explain how you verified the deployment baseline.');
      form.elements[sha.test(revision) ? 'reason' : 'revision'].focus();
      return;
    }
    setError('');
    mutation.mutate({ revision, reason });
  }
  return <Card title="Initialize the production baseline">
    <p className="release-muted">Identify the commit already deployed or approved as the starting point and record how you verified it.</p>
    <form noValidate onSubmit={submit} className="release-form">
      <Input name="revision" label="Baseline commit SHA" required maxLength={40} spellCheck={false} />
      <Textarea name="reason" label="Baseline verification rationale" required maxLength={1000} />
      {(error || mutation.error) && <p role="alert">{error || mutation.error.message}</p>}
      {mutation.isSuccess && <p role="status">Production baseline recorded.</p>}
      <div><Button type="submit" variant="secondary" isLoading={mutation.isPending}>Record baseline</Button></div>
    </form>
  </Card>;
}

function CandidateForm({ projectId, baseline, listKey }) {
  const cache = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const mutation = useMutation({
    mutationFn: (data) => releasesApi.create(projectId, data),
    onSuccess: (release) => {
      cache.invalidateQueries({ queryKey: listKey });
      if (release.id) navigate(releasePath(projectId, release.id));
    },
  });
  function submit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const read = (name) => form.elements[name].value.trim();
    const data = {
      baseline_sha: read('baseline_sha').toLowerCase(), target_sha: read('target_sha').toLowerCase(),
      run_id: Number(read('run_id')), artifact_id: Number(read('artifact_id')), kind: read('kind'),
    };
    const invalid = ['baseline_sha', 'target_sha'].find((key) => !sha.test(data[key]))
      || ['run_id', 'artifact_id'].find((key) => !/^\d+$/.test(read(key)) || !Number.isSafeInteger(data[key]) || data[key] < 1);
    if (invalid) {
      setError(invalid.endsWith('_sha') ? 'Enter full 40-character commit SHAs.' : 'Enter positive GitHub run and artifact IDs.');
      form.elements[invalid].focus();
      return;
    }
    setError('');
    mutation.mutate(data);
  }
  return <Card title="Discover a release candidate">
    <p className="release-muted">Use the target commit and the immutable artifact produced by the trusted GitHub workflow.</p>
    <form noValidate onSubmit={submit} className="release-form">
      <div className="release-grid">
        <Input key={baseline ?? 'new'} label="Baseline commit SHA" name="baseline_sha" defaultValue={baseline} required maxLength={40} spellCheck={false} />
        <Input label="Target commit SHA" name="target_sha" required maxLength={40} spellCheck={false} />
        <Input label="GitHub workflow run ID" name="run_id" required inputMode="numeric" maxLength={16} />
        <Input label="GitHub artifact ID" name="artifact_id" required inputMode="numeric" maxLength={16} />
        <Select label="Release type" name="kind" defaultValue="standard" placeholder="" options={[
          { value: 'standard', label: 'Standard release' }, { value: 'hotfix', label: 'Hotfix' }, { value: 'rollback', label: 'Rollback' },
        ]} />
      </div>
      {(error || mutation.error) && <p role="alert">{error || mutation.error.message}</p>}
      <div><Button type="submit" isLoading={mutation.isPending}>Discover candidate</Button></div>
    </form>
  </Card>;
}

function ReleaseDetail({ projectId, releaseId, scope }) {
  const queryKey = ['release', scope, projectId, releaseId];
  const query = useQuery({
    queryKey, retry: false, queryFn: ({ signal }) => releasesApi.get(projectId, releaseId, signal),
  });
  if (query.isPending) return <LoadingState message="Loading the release manifest…" />;
  if (query.error) return <ErrorState message={query.error.message} onRetry={query.refetch} />;
  const release = query.data;
  const manifest = release.manifest || {};
  const gate = release.gate;
  const deployment = release.deployment;
  return <>
    <Link to={releasePath(projectId)}>Back to release candidates</Link>
    <Card title={release.id} subtitle={manifest.repository} action={<State value={release.state} />}>
      <dl className="release-facts">
        <Field label="Release type" value={stateLabel(manifest.kind)} />
        <Field label="Environment" value={stateLabel(manifest.environment || release.environment || 'production')} />
        <Field label="Baseline commit" value={<Revision value={manifest.baseline_sha} />} />
        <Field label="Target commit" value={<Revision value={manifest.target_sha} />} />
        <Field label="Manifest digest" value={<Revision value={release.manifest_digest} />} />
        <Field label="Artifact ID" value={manifest.artifact?.id ?? manifest.artifact_id} />
        <Field label="Artifact digest" value={<Revision value={manifest.artifact?.digest} />} />
        <Field label="Workflow run and attempt" value={manifest.artifact?.run_id ? `${manifest.artifact.run_id} · Attempt ${manifest.artifact.run_attempt ?? 'unknown'}` : null} />
        <Field label="Artifact provenance" value={manifest.artifact?.verified === true || manifest.artifact?.workflow_sha256
          ? 'Verified' : stateLabel(manifest.artifact?.provenance || 'unknown')} />
      </dl>
    </Card>
    <div className="release-grid">
      <Card title="Gate eligibility">
        <p>{gate?.allowed === true || release.eligible === true ? 'Eligible for a fresh gate check' : 'Deployment eligibility unconfirmed or blocked'}</p>
        <Failures errors={gate?.reasons || release.blockers} />
      </Card>
      <Card title="Observed deployment">
        <State value={!deployment?.status || deployment.status === 'unknown' ? 'not_observed' : deployment.status} />
        {(deployment?.deployment_id || deployment?.id) && <p>GitHub deployment <code>{deployment.deployment_id || deployment.id}</code></p>}
        {displayTime(deployment?.observed_at || deployment?.updated_at) && <p>{displayTime(deployment.observed_at || deployment.updated_at)}</p>}
      </Card>
    </div>
    <ScopeEvidence manifest={manifest} projectId={projectId} />
    <TestEvidence evidence={release.evidence} repository={manifest.repository} />
    <ReviewActions release={release} projectId={projectId} scope={scope} queryKey={queryKey} />
    <DecisionHistory release={release} projectId={projectId} scope={scope} />
  </>;
}

function validRepository(repository) {
  return typeof repository === 'string' && /^[\w.-]+\/[\w.-]+$/.test(repository)
    && repository.split('/').every((part) => part !== '.' && part !== '..');
}

function TaskRequirements({ task }) {
  const story = task.story;
  const criteria = task.acceptance_criteria ?? story?.acceptance_criteria;
  return <div>
    {story?.title && <strong>{story.title}</strong>}
    {Array.isArray(criteria) ? (criteria.length ? <ul className="release-list">{criteria.map((item, index) => <li key={index}>{typeof item === 'string' ? item : item.description || item.text || item.title}</li>)}</ul> : <p>Acceptance criteria unavailable</p>)
      : <p>{criteria || story?.description || 'Acceptance criteria unavailable'}</p>}
  </div>;
}

function ScopeEvidence({ manifest, projectId }) {
  const prRows = manifest.pull_requests || [];
  const taskRows = manifest.tasks || [];
  const prColumns = [
    { key: 'number', header: 'Pull request', render: (row) => {
      const number = row.number ?? row.pr_number;
      const label = `#${number} ${row.title || ''}`.trim();
      return validRepository(manifest.repository) && Number.isSafeInteger(number)
        ? <a href={`https://github.com/${manifest.repository}/pull/${number}`} target="_blank" rel="noreferrer">{label}</a> : label;
    } },
    { key: 'merge_commit_sha', header: 'Merge revision', render: (row) => <Revision value={row.merge_commit_sha} short /> },
    { key: 'task_ids', header: 'Linked tasks', render: (row) => (row.task_ids || []).join(', ') || 'Missing task link' },
    { key: 'advisory', header: 'PR evidence', render: (row) => <ChangeEvidence projectId={projectId} repository={manifest.repository} pr={row} /> },
  ];
  const taskColumns = [
    { key: 'id', header: 'Task', render: (row) => <Link to={`/tasks?${new URLSearchParams({ project: projectId, task: row.id })}`}>{row.title || row.id}</Link> },
    { key: 'story', header: 'Requirements', render: (row) => <TaskRequirements task={row} /> },
    { key: 'assignee_id', header: 'Assignee', render: (row) => row.assignee_name || row.assignee_id || 'Unassigned' },
    { key: 'status', header: 'Status', render: (row) => <State value={row.status} /> },
    { key: 'pr_numbers', header: 'Linked pull requests', render: (row) => row.pr_numbers?.map((number) => `#${number}`).join(', ') || 'Unavailable' },
  ];
  return <>
    <Card title="Release scope" action={<State value={manifest.complete ? 'complete' : 'incomplete'} />}>
      <Failures errors={manifest.blockers} />
      <Table columns={prColumns} data={prRows} keyExtractor={(pr) => pr.number ?? pr.pr_number} emptyMessage="No included pull requests were established." />
      {!!manifest.excluded_pull_requests?.length && <details>
        <summary>Excluded pull requests ({manifest.excluded_pull_requests.length})</summary>
        <ul className="release-list">{manifest.excluded_pull_requests.map((pr) => <li key={pr.number}>
          PR #{pr.number} · {stateLabel(pr.reason)}
        </li>)}</ul>
      </details>}
      {!!manifest.unmapped_commits?.length && <details><summary>Unmapped commits ({manifest.unmapped_commits.length})</summary>
        <ul className="release-list">{manifest.unmapped_commits.map((commit, index) => <li key={index}><Revision value={commit.sha || commit} /></li>)}</ul>
      </details>}
      {!!manifest.reverts?.length && <details><summary>Revert evidence ({manifest.reverts.length})</summary>
        <ul className="release-list">{manifest.reverts.map((revert, index) => <li key={index}>
          {typeof revert === 'string' ? revert : <><Revision value={revert.revision} short />
            {' · References '}<Revision value={revert.referenced_revision} short />{' · '}{stateLabel(revert.status)}</>}
        </li>)}</ul>
      </details>}
    </Card>
    <Card title="Included tasks and requirements">
      <Table columns={taskColumns} data={taskRows} emptyMessage="No authorized tasks were found for this candidate." />
    </Card>
  </>;
}

function ChangeEvidence({ pr, projectId, repository }) {
  const [expanded, setExpanded] = useState(false);
  const scope = useSessionScope();
  const user = useAuthStore((state) => state.user);
  const number = pr.number ?? pr.pr_number;
  const source = { projectId, repository, head: pr.head_sha, number };
  const canReadCode = pr.local_pr_id && sha.test(pr.head_sha) && validRepository(repository)
    && hasPermission(user, PERMISSIONS.VIEW_CODE_QUALITY);
  return <>
    <TaskPRAdvisory projectId={projectId} pr={{ ...pr, number, repository }} />
    {canReadCode && <details onToggle={(event) => setExpanded(event.currentTarget.open)}>
      <summary>Code and algorithm evidence</summary>
      {expanded && <Suspense fallback={<LoadingState message="Loading PR evidence…" />}>
        <PRAlgorithmIntelligencePanel key={JSON.stringify([scope, source])} prId={pr.local_pr_id} source={source} />
      </Suspense>}
    </details>}
  </>;
}

function TestEvidence({ evidence, repository }) {
  const qa = evidence?.qa;
  const coverage = evidence?.coverage_status ?? qa?.coverage_status;
  const runs = qa?.runs ?? evidence?.runs ?? [];
  const columns = [
    { key: 'test_suite', header: 'Suite', render: (row) => row.test_suite || row.suite || 'Unknown suite' },
    { key: 'workflow_run_id', header: 'GitHub run', render: (row) => /^\d+$/.test(String(row.workflow_run_id)) && validRepository(repository)
      ? <a href={`https://github.com/${repository}/actions/runs/${row.workflow_run_id}`} target="_blank" rel="noreferrer">{row.workflow_run_id}</a>
      : 'Unavailable' },
    { key: 'attempt', header: 'Attempt', render: (row) => row.run_attempt ?? row.attempt ?? 'Unavailable' },
    { key: 'status', header: 'Result', render: (row) => <State value={row.status} /> },
    { key: 'tests_passed', header: 'Passed', render: (row) => row.tests_passed ?? 'Unavailable' },
    { key: 'tests_failed', header: 'Failed', render: (row) => row.tests_failed ?? 'Unavailable' },
    { key: 'tests_skipped', header: 'Skipped', render: (row) => row.tests_skipped ?? 'Unavailable' },
  ];
  const percentage = evidence?.coverage?.coverage_percentage;
  return <Card title="Combined release tests" action={<State value={qa?.status || (typeof qa === 'string' ? qa : 'unknown')} />}>
    {qa?.reason && <p>{qa.reason}</p>}
    <p>{coverage === 'reported' && Number.isFinite(percentage) ? `Reported coverage · ${percentage.toFixed(1)}%` : 'Coverage unavailable'}</p>
    <Table columns={columns} data={runs} emptyMessage="No test reports for this exact target commit." />
  </Card>;
}

const actions = {
  submit: 'Submit for QA review', verify_qa: 'Record QA verification', approve: 'Approve release',
  hold: 'Place release on hold', refresh: 'Refresh candidate evidence', supersede: 'Supersede candidate',
};
const confirmations = {
  submit: 'Confirm QA submission', verify_qa: 'Confirm QA verification', approve: 'Confirm approval',
  hold: 'Confirm hold', refresh: 'Confirm evidence refresh', supersede: 'Confirm supersession',
};

function ReviewActions({ release, projectId, scope, queryKey }) {
  const cache = useQueryClient();
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [selection, setSelection] = useState(null);
  const [attested, setAttested] = useState(false);
  const reviewInput = useRef(null);
  const allowed = Object.keys(actions).filter((action) => release.can?.[action] === true);
  const mutation = useMutation({
    mutationFn: (data) => releasesApi.act(projectId, release.id, data),
    onSettled: () => cache.invalidateQueries({ queryKey }),
    onSuccess: () => {
      setReason('');
      setSelection(null);
      setAttested(false);
      cache.invalidateQueries({ queryKey: ['releases', scope, projectId] });
    },
  });
  function select(action) {
    setSelection({ action, version: release.version, evidence_digest: release.evidence_digest ?? undefined });
    setAttested(false);
    setError('');
    mutation.reset();
  }
  const stale = selection && (selection.version !== release.version || selection.evidence_digest !== (release.evidence_digest ?? undefined));
  const ready = selection && !stale && allowed.includes(selection.action);
  const verification = selection?.action === 'verify_qa';
  const reviewedTasks = release.manifest?.tasks?.map(({ id }) => id) ?? [];
  function submit(event) {
    event.preventDefault();
    if (!ready || mutation.isPending || (verification && (!attested || !reviewedTasks.length))) return;
    if (!reason.trim()) {
      setError('Enter a rationale for this decision.');
      reviewInput.current?.focus();
      return;
    }
    setError('');
    mutation.mutate({
      ...selection, reason: reason.trim(),
      ...(verification && { verified_task_ids: reviewedTasks }),
    });
  }
  if (!allowed.length && !selection && !mutation.error && !mutation.isSuccess) return null;
  const conflict = mutation.error?.status === 409 || mutation.error?.response?.status === 409;
  return <Card title="Release review">
    <div className="release-controls">
      {allowed.map((action) => <Button key={action} variant="secondary" aria-pressed={selection?.action === action} disabled={mutation.isPending}
        onClick={() => select(action)}>{actions[action]}</Button>)}
    </div>
    <form noValidate onSubmit={submit} className="release-form">
      {(allowed.length > 0 || Boolean(reason)) && <Textarea ref={reviewInput} label="Review rationale" value={reason}
        onChange={(event) => setReason(event.target.value)} maxLength={1000} error={error} disabled={!selection || mutation.isPending} required />}
      {verification && <label className="release-checkbox">
        <input type="checkbox" checked={attested} disabled={!ready || mutation.isPending || !reviewedTasks.length}
          onChange={(event) => setAttested(event.target.checked)} />
        I reviewed all {reviewedTasks.length} included tasks and their requirements against the combined test evidence.
      </label>}
      {ready && !conflict && <div><Button type="submit" disabled={verification && (!attested || !reviewedTasks.length)}
        isLoading={mutation.isPending}>{confirmations[selection.action]}</Button></div>}
      {(conflict || stale) ? <p role="alert">This candidate changed. Review the refreshed evidence and select the action again.</p>
        : mutation.error && <p role="alert">{mutation.error.message}</p>}
      {mutation.isSuccess && <p role="status">Release action recorded.</p>}
    </form>
  </Card>;
}

function DecisionHistory({ release, projectId, scope }) {
  const [page, setPage] = useState(1);
  const history = useQuery({
    queryKey: ['release-history', scope, projectId, release.id, release.version, page], enabled: page > 1, retry: false,
    queryFn: ({ signal }) => releasesApi.history(projectId, release.id, { offset: (page - 1) * 25, limit: 25 }, signal),
  });
  const firstPage = release.history || [];
  const entries = (page === 1 ? firstPage : history.data?.history) || [];
  const rows = entries.map((entry) => ({ ...(entry.record || entry), version: entry.version, manifest_digest: entry.manifest_digest }));
  const columns = [
    { key: 'action', header: 'Decision', render: (row) => stateLabel(row.action || row.decision) },
    { key: 'actor', header: 'Reviewer', render: (row) => row.actor_name || row.actor_id || row.reviewer_id || 'Unavailable' },
    { key: 'at', header: 'Recorded', render: (row) => displayTime(row.at || row.created_at || row.recorded_at) || 'Unavailable' },
    { key: 'reason', header: 'Rationale' },
    { key: 'manifest_digest', header: 'Manifest revision', render: (row) => <Revision value={row.manifest_digest} short /> },
  ];
  return <Card title="Review history">
    {release.qa_verification && <p>QA verification · {release.qa_verification.is_current ? 'Current' : 'Out of date'}</p>}
    {release.release_decision && <p>DevOps decision · {stateLabel(release.release_decision.action || release.release_decision.decision)}
      {release.release_decision.is_current === false && ' · Out of date'}</p>}
    {page > 1 && history.isPending ? <LoadingState message="Loading review history…" />
      : history.error && page > 1 ? <ErrorState message={history.error.message} onRetry={history.refetch} />
        : <Table columns={columns} data={rows} emptyMessage="No release decisions have been recorded." />}
    {(page > 1 || firstPage.length >= 25) && <nav className="release-controls" aria-label="Release history pages">
      <Button disabled={page === 1} variant="secondary" onClick={() => setPage(page - 1)}>Previous</Button>
      <span>Page {page}</span>
      <Button disabled={page > 1 && !history.data?.has_more} variant="secondary" onClick={() => setPage(page + 1)}>Next</Button>
    </nav>}
  </Card>;
}
