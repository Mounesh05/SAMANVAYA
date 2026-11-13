import React, { useState } from 'react';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { useMutation } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';

const pretty = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
const editor = { width: '100%', minHeight: '8rem', background: 'var(--bg-input)', color: 'var(--text-primary)' };

export function RequirementsSection({ report }) {
  if (!report) return null;
  return <section aria-label="Discovered requirements">
    <h3>Requirements evidence</h3>
    {report.project_id && <p>Project: {report.project_id}</p>}
    <p>Approved applicable requirements can constrain decisions. Observations and suggestions do not establish production limits. Unknown budgets keep recommendations conditional.</p>
    {[
      ['established', 'Established requirements'], ['observations', 'Observed workload characteristics'],
      ['suggestions', 'Suggestions needing confirmation'], ['unknown', 'Unknown critical requirements'],
      ['conflicts', 'Requirement conflicts'], ['excluded', 'Excluded or superseded evidence'],
    ].map(([key, label]) => <details key={key} open={key === 'conflicts' && report[key]?.length > 0}>
      <summary>{label} ({report[key]?.length || 0})</summary>
      <ul>{(report[key] || []).map((row, i) => <li key={row.id || i}>
        <p>{row.type || row.status || ''} {row.authority_status || ''} {row.applicability_status || ''}: {row.description || row.reason}</p>
        {row.value !== undefined && <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{pretty(row.value)} {row.unit || ''} {row.metric || ''}</pre>}
        {row.scope && <p>Scope: {pretty(row.scope)}</p>}
        {row.source_revision && <p>Source revision: {row.source_revision}</p>}
        <p>{(row.evidence_refs || []).join(' · ')}</p>
      </li>)}</ul>
    </details>)}
    <ul>{(report.limitations || []).map((text, i) => <li key={i}>{text}</li>)}</ul>
    <small>Method: {report.method} · Evidence fingerprint: {report.fingerprint}</small>
  </section>;
}

export function RequirementsPanel() {
  const user = useAuthStore(state => state.user);
  const [project, setProject] = useState('');
  const [context, setContext] = useState('');
  const [source, setSource] = useState('');
  const [reviewSource, setReviewSource] = useState('');
  const [rationale, setRationale] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [error, setError] = useState('');
  const discovery = useMutation({ mutationFn: body => algorithmsApi.discoverRequirements(body) });
  const sources = useMutation({ mutationFn: () => algorithmsApi.getRequirementSources(project.trim()) });
  const proposal = useMutation({ mutationFn: body => algorithmsApi.proposeRequirementSource(body) });
  const approval = useMutation({ mutationFn: doc => algorithmsApi.approveRequirementSource(doc.source_id, {
    expected_fingerprint: doc.payload_fingerprint, source_reference: reviewSource, rationale, scope_reviewed: reviewed,
  }), onSuccess: () => { sources.mutate(); parse(context, value => discovery.mutate({ project_id: project.trim(), context: value })); } });
  // Same checks as the backend (permissions, not role names).
  const canReview = hasPermission(user, PERMISSIONS.APPROVE_ENGINEERING_CONTRACTS);
  const canSubmit = hasPermission(user, PERMISSIONS.USE_ENGINEERING_INTELLIGENCE);
  const errors = [error, discovery.error?.message, sources.error?.message, proposal.error?.message, approval.error?.message].filter(Boolean);
  const parse = (text, action) => { try { setError(''); action(text ? JSON.parse(text) : {}); } catch { setError('Provide valid JSON.'); } };
  return <Card title="Automatic requirement discovery" subtitle="Discover established constraints and preserve uncertain requirements" style={{ marginBottom: '1.75rem' }}>
    <Input label="Requirements project ID" value={project} onChange={e => setProject(e.target.value)} />
    <p>Approved project policy is imported automatically. Specific contract, discovery, task, story, PR and historical run references can add context. Unrelated records are excluded.</p>
    <details><summary>Optional evidence references</summary>
      <label>Requirement context JSON<textarea aria-label="Requirement context JSON" style={editor} value={context} onChange={e => setContext(e.target.value)} placeholder={'{"contract_ids": [], "discovery_run_ids": [], "task_ids": [], "story_ids": [], "pr_ids": []}'} /></label>
    </details>
    <Button disabled={!canSubmit || !project.trim() || discovery.isPending} onClick={() => parse(context, value => discovery.mutate({ project_id: project.trim(), context: value }))}>Discover requirements</Button>
    <RequirementsSection report={discovery.data} />
    <details><summary>Confirm a specific structured requirement source</summary>
      <p>Only use this when a missing requirement has an explicit source. Provide source_reference, source_revision and requirements with id, type, key, value, description and optional scope. A memory limit needs integer bytes and a recognized peak metric; latency needs seconds and elapsed_invocation_seconds. A separate authorized reviewer approves the exact revision.</p>
      <label>Requirement source JSON<textarea aria-label="Requirement source JSON" style={editor} value={source} onChange={e => setSource(e.target.value)} /></label>
      <Button disabled={!canSubmit || !project.trim() || !source.trim()} onClick={() => parse(source, value => proposal.mutate({ ...value, project_id: project.trim() }))}>Propose requirement source</Button>
      {proposal.data && <p role="status">{proposal.data.source_id}: {proposal.data.status}</p>}
      <Button disabled={!canSubmit || !project.trim()} onClick={() => sources.mutate()}>Load requirement sources</Button>
      {canReview && <>
        <Input label="Requirement review source" value={reviewSource} onChange={e => setReviewSource(e.target.value)} />
        <Input label="Requirement review rationale" value={rationale} onChange={e => setRationale(e.target.value)} />
        <label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the source authority, values, units and applicability of this revision.</label>
      </>}
      {(sources.data?.sources || []).map(doc => <div key={doc.source_id}>
        <p>{doc.source_id}: {doc.status}</p>
        <details><summary>Review exact requirement source</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{pretty(doc)}</pre></details>
        {canReview && doc.status === 'PROPOSED' && doc.proposed_by !== (user?.employee_id || user?.sub) && <Button
          disabled={!reviewed || !reviewSource.trim() || !rationale.trim() || approval.isPending}
          onClick={() => approval.mutate(doc)}>Approve requirement source {doc.source_id}</Button>}
      </div>)}
    </details>
    {errors.map((text, i) => <p role="alert" key={i}>{text}</p>)}
  </Card>;
}
