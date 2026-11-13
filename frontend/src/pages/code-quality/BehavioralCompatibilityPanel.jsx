import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { BehavioralCompatibilitySection } from './BehavioralCompatibilitySection';
import { RequirementsSection } from './RequirementsPanel';

const editorStyle = { width: '100%', minHeight: '8rem', background: 'var(--bg-input)', color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' };
const empty = (name) => ({ name, language: 'python', entrypoint: '', source: '', runId: '', functionId: '' });

export function BehavioralCompatibilityPanel() {
  const user = useAuthStore(state => state.user);
  const [project, setProject] = useState('');
  const [contractIds, setContractIds] = useState('');
  const [proposalJson, setProposalJson] = useState('');
  const [reviewSource, setReviewSource] = useState('');
  const [rationale, setRationale] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const [previous, setPrevious] = useState(empty('previous'));
  const [current, setCurrent] = useState(empty('current'));
  const [runId, setRunId] = useState('');
  const [error, setError] = useState('');
  const proposer = useMutation({ mutationFn: body => algorithmsApi.proposeContract(body) });
  const contracts = useMutation({ mutationFn: () => algorithmsApi.getContracts(project.trim()) });
  const review = useMutation({ mutationFn: doc => algorithmsApi.approveContract(doc.contract_id, {
    expected_fingerprint: doc.payload_fingerprint, source_reference: reviewSource, rationale, scope_reviewed: reviewed,
  }) });
  const relationships = useMutation({ mutationFn: () => algorithmsApi.getRelationships({ project_id: project.trim(), previous_run_id: previous.runId, current_run_id: current.runId }) });
  const comparison = useMutation({ mutationFn: body => algorithmsApi.startCompatibility(body), onSuccess: data => setRunId(data.run_id) });
  const run = useQuery({ queryKey: ['compatibility-run', runId], queryFn: () => algorithmsApi.getRun(runId), enabled: Boolean(runId),
    refetchInterval: query => ['pending', 'running'].includes(query.state.data?.status) ? 1000 : false });
  const docs = contracts.data?.contracts || [];
  const role = (user?.role || user?.organizational_role)?.toUpperCase();
  const canApprove = ['LEAD', 'PM', 'CEO'].includes(role);  // CR-008: approval comes from the role
  const canSubmit = user?.is_admin || ['DEVELOPER', 'LEAD', 'PM', 'CEO', 'QA', 'DEVOPS'].includes(role);
  const errors = [error, proposer.error?.message, contracts.error?.message, review.error?.message, relationships.error?.message, comparison.error?.message, run.error?.message].filter(Boolean);

  function candidate(value) {
    const result = { name: value.name, language: value.language, entrypoint: value.entrypoint, source: value.source };
    if (value.runId || value.functionId) result.function_reference = { run_id: value.runId, function_id: value.functionId };
    return result;
  }
  function submit(event) {
    event.preventDefault();
    setError('');
    comparison.mutate({ project_id: project.trim(), previous: candidate(previous), current: candidate(current),
      contract_ids: contractIds.split(',').map(s => s.trim()).filter(Boolean) });
  }
  return <Card title="Behavioral compatibility" subtitle="Validate a potential replacement against an explicitly approved functional contract" style={{ marginBottom: '1.75rem' }}>
    <p>Names, signatures, algorithm families and Phase 2 hypotheses establish provisional relationships only. All approved required checks must pass. Finite tests do not prove universal equivalence.</p>
    <Input label="Compatibility project ID" value={project} onChange={e => setProject(e.target.value)} />
    <details><summary>Functional contract proposal and independent approval</summary>
      <p>Propose the existing generic contract and datasets with required_dataset_ids, requirements (id, description, source_reference, dataset_ids) and scope_description. Only data validators are accepted. Proposed contracts are not approved automatically.</p>
      <label>Functional contract proposal JSON<textarea aria-label="Functional contract proposal JSON" style={editorStyle} value={proposalJson} onChange={e => setProposalJson(e.target.value)} /></label>
      <Button disabled={!canSubmit || !project.trim() || !proposalJson.trim()} onClick={() => {
        try { setError(''); proposer.mutate({ ...JSON.parse(proposalJson), project_id: project.trim() }); }
        catch { setError('Contract proposal must be valid JSON.'); }
      }}>Propose contract</Button>
      {proposer.data && <p role="status">Proposed {proposer.data.contract_id}: {proposer.data.status}. Fingerprint: {proposer.data.payload_fingerprint}</p>}
      <Button disabled={!project.trim()} onClick={() => contracts.mutate()}>Load project contracts</Button>
      {canApprove && <>
        <Input label="Contract review source reference" value={reviewSource} onChange={e => setReviewSource(e.target.value)} />
        <Input label="Contract review rationale" value={rationale} onChange={e => setRationale(e.target.value)} />
        <label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the functional requirements, expected results and finite validation scope.</label>
      </>}
      <ul>{docs.map(doc => <li key={doc.contract_id}>
        <p>{doc.contract_id} · {doc.contract?.name} v{doc.contract?.version} · {doc.status}</p>
        <details><summary>Review exact contract content</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(doc, null, 2)}</pre></details>
        {canApprove && doc.status === 'PROPOSED' && <Button disabled={!reviewed || !reviewSource.trim() || !rationale.trim() || doc.proposed_by === (user?.employee_id || user?.sub)} onClick={() => review.mutate(doc)}>Approve reviewed contract {doc.contract_id}</Button>}
      </li>)}</ul>
      {review.data && <p role="status">Approved contract {review.data.contract_id}. This approves requirements and scope, not an implementation.</p>}
    </details>
    <form aria-label="Behavioral compatibility form" onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <Input label="Approved contract IDs (comma separated)" value={contractIds} onChange={e => setContractIds(e.target.value)} />
      <p>Leave empty to record CONTRACT_MISSING without executing code. An unknown validator requirement remains UNVERIFIED.</p>
      {[['Previous', previous, setPrevious], ['Current', current, setCurrent]].map(([label, value, setter]) => <fieldset key={label}>
        <legend>{label} implementation</legend>
        <Input label={`${label} implementation name`} value={value.name} onChange={e => setter({ ...value, name: e.target.value })} />
        <label>{label} language<select aria-label={`${label} language`} value={value.language} onChange={e => setter({ ...value, language: e.target.value })}>
          {['python', 'javascript', 'typescript'].map(lang => <option key={lang}>{lang}</option>)}
        </select></label>
        <Input label={`${label} entrypoint`} value={value.entrypoint} onChange={e => setter({ ...value, entrypoint: e.target.value })} />
        <label>{label} source<textarea aria-label={`${label} source`} style={editorStyle} value={value.source} onChange={e => setter({ ...value, source: e.target.value })} /></label>
        <Input label={`${label} discovery run ID (optional)`} value={value.runId} onChange={e => setter({ ...value, runId: e.target.value })} />
        <Input label={`${label} function ID (optional)`} value={value.functionId} onChange={e => setter({ ...value, functionId: e.target.value })} />
      </fieldset>)}
      <Button type="button" disabled={!project.trim() || !previous.runId || !current.runId} onClick={() => relationships.mutate()}>Discover provisional relationships</Button>
      {relationships.data && <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(relationships.data, null, 2)}</pre>}
      <Button type="submit" disabled={!canSubmit || !project.trim() || comparison.isPending}>Validate behavioral compatibility</Button>
    </form>
    {errors.map((message, i) => <p key={i} role="alert">{message}</p>)}
    {runId && <p role="status">Compatibility run {runId}: {run.data?.status || 'Loading'}</p>}
    {run.data?.error && <p role="alert">{run.data.error}</p>}
    <BehavioralCompatibilitySection report={run.data?.behavioral_compatibility} />
    <RequirementsSection report={run.data?.decision?.requirements_discovery || run.data?.requirements_discovery} />
  </Card>;
}
