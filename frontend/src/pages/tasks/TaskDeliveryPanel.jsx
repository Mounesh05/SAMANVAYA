import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { tasksApi } from '../../api/tasks.api';
import { Badge } from '../../components/common/Badge';
import { Button } from '../../components/common/Button';
import { Textarea } from '../../components/common/Textarea';
import { TaskPRAdvisory } from '../../components/github/ManualPRAnalysisPanel';
import { useSessionScope } from '../../store/useSessionScope';
import './taskDelivery.css';

const statuses = {
  unknown: ['Unconfirmed', 'default'],
  open: ['PR open', 'primary'],
  closed: ['Closed without merge', 'default'],
  merged: ['Merged', 'success'],
  multiple: ['Multiple linked PRs', 'warning'],
  passed: ['Reports passed', 'success'],
  failed: ['Failed', 'danger'],
  deployed: ['Deployment reported', 'success'],
};

const reportSources = {
  project_ci_token: 'Project CI submission',
  github_artifact: 'Imported GitHub artifact',
  legacy_submission: 'Legacy CI submission',
};

function nextStep(record) {
  if (record.production.status === 'failed') return 'DevOps reviews the failed deployment.';
  if (record.release_decision?.is_current && record.release_decision.decision === 'hold') {
    if (record.production.status === 'deployed') return 'DevOps reviews the reported deployment against the recorded hold.';
    return 'DevOps coordinates follow-up on the recorded hold.';
  }
  if (record.qa.status === 'failed') return 'Developer addresses the failing checks with QA.';
  if (record.readiness.status === 'blocked') return 'Team Lead reviews the release blocker.';
  if (!record.revision) return 'Team Lead confirms which pull request delivers this task.';
  if (record.implementation.status !== 'merged') return 'Team Lead reviews the implementation.';
  if (record.revision_kind !== 'merge_commit') return 'Team Lead confirms the merged commit for release review.';
  if (record.qa.status !== 'passed') return 'QA obtains test evidence for this revision.';
  if (!record.qa_verification?.is_current) return 'QA verifies that the reports cover the acceptance criteria.';
  if (record.release_decision?.is_current && record.release_decision.decision === 'approve') {
    if (record.production.status === 'deployed') return 'PM reviews the delivered scope.';
    return 'DevOps confirms the production deployment.';
  }
  if (record.production.status === 'deployed') return 'DevOps reviews the approval history for the reported deployment.';
  return 'DevOps reviews the evidence and records a release decision.';
}

function Stage({ name, stage, children }) {
  const [label, tone] = statuses[stage.status] || statuses.unknown;
  return <div className="delivery-stage">
    <dt>{name}</dt>
    <dd>
      <Badge size="sm" variant={tone}>{label}</Badge>
      {stage.reason && <p>{stage.reason}</p>}
      {children}
    </dd>
  </div>;
}

function SourceLink({ repository, path, number, attempt, children }) {
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository || '') || !/^\d+$/.test(String(number))) {
    return children;
  }
  const suffix = Number.isInteger(attempt) && attempt > 0 ? `/attempts/${attempt}` : '';
  return <a href={`https://github.com/${repository}/${path}/${number}${suffix}`} target="_blank" rel="noreferrer">{children}</a>;
}

function DecisionRecord({ record, verification = false }) {
  if (!record) return <p>{verification ? 'Awaiting QA verification.' : 'No release decision recorded.'}</p>;
  let label = verification ? 'QA verified coverage' : record.decision === 'approve' ? 'Release approved' : 'Release held';
  if (!record.is_current) label = `Previous decision · ${label}`;
  return <div className="delivery-decision">
    <strong>{label}</strong>
    <p>{record.actor_name || record.actor_id} · <time dateTime={record.recorded_at}>{new Date(record.recorded_at).toLocaleString()}</time>
      {' · '}<code title={record.revision}>{record.revision?.slice(0, 12)}</code></p>
    {!record.is_current && <p>Review the current evidence before using this decision.</p>}
    <p>{record.reason}</p>
  </div>;
}

function DecisionActions({ record, busy, submit }) {
  const [reason, setReason] = useState('');
  const canVerify = record.can_verify_qa === true;
  const canDecide = record.can_decide === true;
  if (!record.revision || !record.decision_version || (!canDecide && !canVerify)) return null;
  const disabled = busy || !reason.trim();
  const act = (decision) => submit({
    decision, reason: reason.trim(), revision: record.revision, decision_version: record.decision_version,
  });
  return <div className="delivery-actions">
    <Textarea label={canVerify ? 'Verification note' : 'Decision reason'} rows={2} maxLength={1000} required
      helperText={canVerify ? 'Identify the acceptance criteria covered by the reports for this revision.' : 'This records your decision. Deployment is a separate operation.'}
      value={reason} onChange={(event) => setReason(event.target.value)} disabled={busy} />
    <div className="delivery-buttons">
      {canVerify && <Button size="sm" disabled={disabled} onClick={() => act('verify_qa')}>Verify QA coverage</Button>}
      {canDecide && <Button size="sm" variant="secondary" disabled={disabled} onClick={() => act('hold')}>Record hold</Button>}
      {canDecide && record.can_approve === true && <Button size="sm" disabled={disabled} onClick={() => act('approve')}>Record release approval</Button>}
    </div>
  </div>;
}

export function TaskDeliveryPanel({ taskId }) {
  const scope = useSessionScope();
  const client = useQueryClient();
  const queryKey = ['task-delivery', scope, taskId];
  const query = useQuery({
    queryKey, queryFn: () => tasksApi.getDelivery(taskId), staleTime: 0, refetchOnMount: 'always',
  });
  const save = useMutation({
    mutationFn: (payload) => tasksApi.recordReleaseDecision(taskId, payload),
    retry: false,
    onSettled: () => client.invalidateQueries({ queryKey, exact: true }),
  });
  const record = query.data;
  const prs = record?.implementation?.pull_requests || [];
  const runs = record?.qa?.runs || [];
  const story = record?.requirement?.story;
  return <section aria-label="Delivery evidence" className="task-delivery">
    <div className="delivery-header">
      <h4>Delivery evidence</h4>
      <Button size="sm" variant="ghost" disabled={query.isFetching || save.isPending} onClick={() => query.refetch()}>Refresh evidence</Button>
    </div>
    {query.isError ? <p role="alert">Could not load delivery evidence. {query.error.message}</p>
      : !record ? <p role="status">Loading delivery evidence…</p>
      : <>
        {record.revision && <p>{record.revision_kind === 'merge_commit' ? 'Merge commit' : 'PR head commit'} <code title={record.revision}>{record.revision.slice(0, 12)}</code></p>}
        <dl className="delivery-stages">
          {story && <div className="delivery-stage"><dt>Linked story</dt><dd>
            <strong>{story.title || story.id}</strong>
            {story.description && <p className="delivery-requirement">{story.description}</p>}
          </dd></div>}
          <Stage name="Implementation" stage={record.implementation}>
            {!!prs.length && <ul>{prs.map((pr) =>
              <li key={`${pr.repository}/${pr.number}`}>
                <SourceLink repository={pr.repository} path="pull" number={pr.number}>
                  {pr.repository} #{pr.number} {pr.title}
                </SourceLink>
                <TaskPRAdvisory projectId={record.project_id} pr={pr} />
              </li>)}</ul>}
          </Stage>
          <Stage name="QA evidence" stage={record.qa}>
            {!!runs.length && <details><summary>Test reports ({runs.length})</summary>
              <ul>{runs.map((run) => <li key={run.id}>
                {run.test_suite || 'Test report'} · {run.status}
                {reportSources[run.provenance] && <> · {reportSources[run.provenance]}</>}
                {run.tests_passed != null && <> · {run.tests_passed} passed</>}
                {run.tests_failed != null && <> · {run.tests_failed} failed</>}
                {run.tests_skipped != null && <> · {run.tests_skipped} skipped</>}
                {run.workflow_run_id && <> · <SourceLink repository={prs.length === 1 ? prs[0].repository : null} path="actions/runs" number={run.workflow_run_id} attempt={run.run_attempt}>
                  Run {run.workflow_run_id}{run.run_attempt && ` (attempt ${run.run_attempt})`}
                </SourceLink></>}
              </li>)}</ul>
            </details>}
            <DecisionRecord record={record.qa_verification} verification />
          </Stage>
          <Stage name="Production" stage={record.production}>
            {record.production.observed_at && <time dateTime={record.production.observed_at}>
              {new Date(record.production.observed_at).toLocaleString()}
            </time>}
          </Stage>
          <div className="delivery-stage"><dt>Release decision</dt><dd><DecisionRecord record={record.release_decision} /></dd></div>
        </dl>
        <p><strong>Next step</strong> · {nextStep(record)}</p>
        {record.readiness?.reason && record.readiness.status !== 'awaiting_review' && <p>{record.readiness.reason}</p>}
        <DecisionActions key={record.decision_version} record={record} busy={save.isPending || query.isFetching} submit={save.mutate} />
        {save.isError && <p role="alert">{save.error.status === 409
          ? 'The evidence or decision changed. Review the refreshed record before submitting again.'
          : `Could not record your decision. ${save.error.message}`}</p>}
        {save.isSuccess && <p role="status">Your decision was recorded.</p>}
      </>}
  </section>;
}
