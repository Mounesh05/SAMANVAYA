import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { useAuthStore } from '../../store/useAuthStore';
import { useSessionScope } from '../../store/useSessionScope';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';

const idOf = doc => doc.contract_id || doc.source_id;
const titleOf = doc => doc.contract_id ? doc.contract?.name || doc.contract_id : doc.source_reference || doc.source_id;
const valueText = value => value == null ? 'Not specified' : typeof value === 'object' ? JSON.stringify(value) : String(value);
const label = value => (value || 'Unknown').toLowerCase().replaceAll('_', ' ');

function ReviewCard({ doc, canApprove, actor, onApproved }) {
  const [reference, setReference] = useState('');
  const [rationale, setRationale] = useState('');
  const [reviewed, setReviewed] = useState(false);
  const contract = Boolean(doc.contract_id);
  const self = !actor || actor === doc.proposed_by;
  const approval = useMutation({
    mutationFn: () => {
      const payload = { expected_fingerprint: doc.payload_fingerprint, source_reference: reference.trim(), rationale: rationale.trim(), scope_reviewed: true };
      return contract ? algorithmsApi.approveContract(doc.contract_id, payload) : algorithmsApi.approveRequirementSource(doc.source_id, payload);
    },
    onSuccess: onApproved,
  });
  const lifecycle = useMutation({
    mutationFn: action => {
      const payload = {action, expected_fingerprint: doc.payload_fingerprint, rationale: rationale.trim()};
      return contract ? algorithmsApi.reviewContract(doc.contract_id, payload) : algorithmsApi.reviewRequirementSource(doc.source_id, payload);
    }, onSuccess: onApproved,
  });
  const mayApprove = canApprove && !self && doc.status === 'PROPOSED' && Boolean(doc.payload_fingerprint);
  const mayRevoke = canApprove && !self && doc.status === 'APPROVED' && Boolean(doc.payload_fingerprint);
  return <article className="ai-review">
    <div><h4>{titleOf(doc)}</h4><p>{contract ? 'Functional contract' : 'Requirement source'} · {label(doc.status)}</p></div>
    <dl>
      <dt>Version / revision</dt><dd>{doc.contract?.version || doc.source_revision || 'Not recorded'}</dd>
      <dt>Scope</dt><dd>{contract ? doc.scope_description || 'Not recorded' : doc.source_kind || 'Not recorded'}</dd>
      {doc.automatic_scope && <><dt>Function binding</dt><dd>{doc.automatic_scope.repository} · {doc.automatic_scope.path} · {doc.automatic_scope.qualified_name}</dd></>}
      {contract && <><dt>Validation cases</dt><dd>{doc.required_dataset_ids?.length || 0} required / {doc.datasets?.length || 0} supplied</dd></>}
    </dl>
    <div>
      <strong>Requirements</strong>
      {(doc.requirements || []).length === 0 && <p>No requirements recorded.</p>}
      {(doc.requirements || []).map((r, i) => <div className="ai-list-row" key={r.id || i}>
        <div><strong>{r.description || r.key || r.id}</strong>{!contract && <p>{r.type}: {valueText(r.value)} {r.unit || ''}</p>}
          {r.source_reference && <p>Source: {r.source_reference}</p>}
          {r.metric && <p>Metric: {r.metric}</p>}
        </div>
      </div>)}
    </div>
    {contract && <details className="ai-disclosure"><summary>Inputs, expected outputs and validation rules</summary>
      <p>Input mutation: {doc.contract?.mutation || 'Not recorded'} · Validator: {doc.validator_requirement || 'Not recorded'}</p>
      {(doc.datasets || []).map(d => <div key={d.id} className="ai-list-row">
        <div><strong>{d.id}{doc.required_dataset_ids?.includes(d.id) ? ' · Required' : ''}</strong>
          <p>Arguments: {valueText(d.args)}</p><p>Expected: {Object.hasOwn(d, 'expected') ? valueText(d.expected) : 'Not established'}</p>
          {d.acceptable_outputs && <p>Other accepted outputs: {valueText(d.acceptable_outputs)}</p>}
        </div>
      </div>)}
    </details>}
    <details className="ai-disclosure"><summary>Exact reviewed content and provenance</summary><pre>{JSON.stringify(doc, null, 2)}</pre></details>
    {mayApprove && !approval.isSuccess && <>
      <Input label="Independent review reference" value={reference} onChange={e => setReference(e.target.value)} maxLength={500} />
      <Input label="Review rationale" value={rationale} onChange={e => setRationale(e.target.value)} maxLength={2000} />
      <label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the exact requirements, expected results or metric units, authority and applicable scope.</label>
      <Button disabled={!reviewed || !reference.trim() || !rationale.trim() || lifecycle.isPending} isLoading={approval.isPending} onClick={() => approval.mutate()}>Approve reviewed {contract ? 'contract' : 'requirements'}</Button>
      <div style={{display:'flex', flexWrap:'wrap', gap:'.5rem'}}>
        <Button variant="outline" disabled={!rationale.trim() || approval.isPending || lifecycle.isPending} onClick={() => lifecycle.mutate('request_changes')}>Request changes</Button>
        <Button variant="danger" disabled={!rationale.trim() || approval.isPending || lifecycle.isPending} onClick={() => lifecycle.mutate('reject')}>Reject</Button>
      </div>
    </>}
    {mayRevoke && <details className="ai-disclosure"><summary>Revoke approval</summary><div className="ai-stack">
      <p>Revocation stops future use of this approval and marks affected project analyses for review.</p>
      <Input label="Revocation rationale" value={rationale} onChange={e => setRationale(e.target.value)} maxLength={2000}/>
      <Button variant="danger" disabled={!rationale.trim()} isLoading={lifecycle.isPending} onClick={() => lifecycle.mutate('revoke')}>Revoke approval</Button>
    </div></details>}
    {doc.review_action && <p>Review: {label(doc.review_action.status)} · {doc.review_action.rationale}</p>}
    {lifecycle.isError && <p role="alert">{lifecycle.error.message}</p>}
    {doc.status === 'PROPOSED' && self && <p>Independent reviewer required.</p>}
    {approval.isError && <p role="alert">{approval.error.message}</p>}
    {approval.isSuccess && <p role="status">Approval recorded. Future analyses can reuse the approved scope.</p>}
  </article>;
}

function ManualProposal({ projectId, onProposed }) {
  const [kind, setKind] = useState('contract');
  const [content, setContent] = useState('');
  const [error, setError] = useState('');
  const proposal = useMutation({
    mutationFn: body => kind === 'contract' ? algorithmsApi.proposeContract(body) : algorithmsApi.proposeRequirementSource(body),
    onSuccess: () => { setContent(''); onProposed(); },
  });
  function submit() {
    try {
      const parsed = JSON.parse(content);
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw Error('Provide a JSON object.');
      setError('');
      proposal.mutate({ ...parsed, project_id: projectId });
    } catch (err) { setError(err.message); }
  }
  return <details className="ai-disclosure">
    <summary>Manual proposal (expert)</summary>
    <div className="ai-stack">
      <p>Use a reviewed source or contract payload. The server validates the proposal; submission never approves it.</p>
      <Select label="Proposal type" value={kind} placeholder={null} disabled={proposal.isPending} options={[{value:'contract',label:'Functional contract'},{value:'source',label:'Requirement source'}]} onChange={e => { setKind(e.target.value); setContent(''); setError(''); proposal.reset(); }} />
      <label htmlFor="algorithm-proposal-content">Proposal JSON</label>
      <textarea id="algorithm-proposal-content" rows={7} value={content} onChange={e => setContent(e.target.value)} />
      <Button disabled={!content.trim()} isLoading={proposal.isPending} onClick={submit}>Submit for review</Button>
      {(error || proposal.isError) && <p role="alert">{error || proposal.error.message}</p>}
      {proposal.isSuccess && <p role="status">Proposal submitted; independent review required.</p>}
    </div>
  </details>;
}

export function RequirementReviewWorkspace({ projectId }) {
  const scope = useSessionScope();
  const user = useAuthStore(state => state.user);
  const canApprove = hasPermission(user, PERMISSIONS.APPROVE_ENGINEERING_CONTRACTS);
  const canSubmit = hasPermission(user, PERMISSIONS.USE_ENGINEERING_INTELLIGENCE);
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState('');
  const [filter, setFilter] = useState('all');
  const contracts = useQuery({ queryKey: ['algorithm-contracts', scope, projectId], queryFn: () => algorithmsApi.getContracts(projectId), retry: false });
  const sources = useQuery({ queryKey: ['algorithm-requirement-sources', scope, projectId], queryFn: () => algorithmsApi.getRequirementSources(projectId), enabled: canSubmit, retry: false });
  const docs = [
    ...(contracts.isError ? [] : contracts.data?.contracts || []),
    ...(!canSubmit || sources.isError ? [] : sources.data?.sources || []),
  ].filter(d => d.project_id === projectId);
  const pending = docs.filter(d => d.status === 'PROPOSED');
  const current = docs.find(d => idOf(d) === selected);
  const refresh = () => Promise.all([
    queryClient.invalidateQueries({ queryKey: ['algorithm-contracts', scope, projectId] }),
    queryClient.invalidateQueries({ queryKey: ['algorithm-requirement-sources', scope, projectId] }),
    queryClient.invalidateQueries({ queryKey: ['pr-algorithm-intelligence', scope] }),
  ]);
  return <Card title="Requirements" subtitle="Review contracts and constraints once, then reuse approved versions." className="ai-stack">
    {(contracts.isPending || (canSubmit && sources.isPending)) && <p role="status">Loading requirements…</p>}
    {contracts.isError && <p role="alert">Contracts: {contracts.error.message} <Button size="sm" variant="outline" onClick={() => contracts.refetch()}>Retry</Button></p>}
    {canSubmit && sources.isError && <p role="alert">Requirement sources: {sources.error.message} <Button size="sm" variant="outline" onClick={() => sources.refetch()}>Retry</Button></p>}
    <Select label="Review status" value={filter} placeholder={null} options={[{value:'all',label:'All requirements'},{value:'PROPOSED',label:'Pending review'},{value:'APPROVED',label:'Approved'},{value:'SUPERSEDED',label:'Superseded'},{value:'CHANGES_REQUESTED',label:'Changes requested'},{value:'REJECTED',label:'Rejected'},{value:'REVOKED',label:'Revoked'}]} onChange={e => {setFilter(e.target.value); setSelected('');}} />
    <p>{pending.length} pending review · {docs.filter(d => d.status === 'APPROVED').length} approved</p>
    {docs.filter(d => filter === 'all' || d.status === filter).map(doc => <div className="ai-list-row" key={idOf(doc)}>
      <div><strong>{titleOf(doc)}</strong><p>{doc.contract_id ? 'Functional contract' : 'Requirement source'} · {label(doc.status)}</p></div>
      <Button size="sm" variant="outline" onClick={() => setSelected(idOf(doc))}>{doc.status === 'PROPOSED' ? 'Review' : 'View'}</Button>
    </div>)}
    {contracts.isSuccess && (!canSubmit || sources.isSuccess) && docs.filter(d => filter === 'all' || d.status === filter).length === 0 && <p>No matching requirements.</p>}
    {current && <ReviewCard key={idOf(current) + ':' + current.payload_fingerprint + ':' + current.status} doc={current} actor={user?.employee_id || user?.sub} canApprove={canApprove} onApproved={refresh} />}
    {canSubmit && <ManualProposal projectId={projectId} onProposed={refresh} />}
  </Card>;
}
