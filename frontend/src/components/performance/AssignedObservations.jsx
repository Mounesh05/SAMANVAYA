import React, { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Select } from '../common/Select';
import { Textarea as NotesField } from '../common/Textarea';
import { requestError } from '../../utils/performanceScoring';
import { useScoringDraft } from './useScoringDraft';
import './scoring.css';

export function AssignedObservations() {
  const user = useAuthStore((s) => s.user);
  const [selected, setSelected] = useState('');
  const [saved, setSaved] = useState(null);
  const assignments = useQuery({ queryKey: ['my-human-assignments', user?.employee_id, user?.role],
    queryFn: () => performanceApi.getAssignments(), enabled: Boolean(user), retry: false });
  const assigned = assignments.data?.find((a) => a.assignment_id === selected);
  const queryKey = ['own-human-review', user?.employee_id, selected];
  const review = useQuery({ queryKey, queryFn: () => performanceApi.getHumanReview(selected), enabled: Boolean(assigned),
    retry: false, refetchOnWindowFocus: false, staleTime: Infinity });
  return <Card title="Assigned observations" className="scoring-stack">
    <p className="scoring-help">Record only what your assignment covers. Observations remain unscored until rating anchors and source validation are approved. CEO feedback has no routine numerical contribution.</p>
    {assignments.isPending ? <p role="status">Loading your assignments…</p> : assignments.isError ?
      <div role="alert"><p>{requestError(assignments.error)}</p><Button onClick={() => assignments.refetch()}>Retry assignments</Button></div> : !assignments.data?.length ?
        <p>No active assigned reviews. A scoped administrator must establish your period interaction and reviewer eligibility first.</p> : <>
          <Select label="Assigned review" value={selected} onChange={(e) => { setSelected(e.target.value); setSaved(false); }} options={assignments.data.map((a) => ({
            value: a.assignment_id, label: `${a.employee_id} · ${a.role} · ${a.period_start.slice(0, 10)} to ${a.period_end.slice(0, 10)}` }))} />
          {assigned && (review.isPending || review.isFetching ? <p role="status">Loading your observation record…</p> : review.isError ?
            <div role="alert"><p>{requestError(review.error)}</p><Button onClick={() => review.refetch()}>Retry observation record</Button></div> :
            <ObservationEditor key={`${user.employee_id}:${selected}:${review.data?.revision_digest || 'new'}`}
              assignment={assigned} current={review.data} owner={user.employee_id} queryKey={queryKey} reload={() => review.refetch()}
              onSaved={(id) => setSaved(id)} onEdit={() => setSaved(null)} />)}
          {saved === selected && <p role="status">Recorded without a score. Newer draft notes, if any, are preserved. Evidence validation and approved rating policy are still required.</p>}
        </>}
  </Card>;
}

function ObservationEditor({ assignment, current, owner, queryKey, reload, onSaved, onEdit }) {
  const client = useQueryClient();
  const initial = { observations: assignment.dimensions.map((dimension) => current?.observations?.find((o) => o.dimension === dimension) ||
    { dimension, state: '', rating: null, reason: '' }), attested: false, baseDigest: current?.revision_digest || null };
  const draft = useScoringDraft(`${owner}:${assignment.assignment_id}`, initial);
  const [error, setError] = useState('');
  const attempt = useRef(null);
  const form = useRef(null);
  const mutation = useMutation({ mutationFn: ({ payload }) => current ? performanceApi.reviseHumanReview(assignment.assignment_id, payload) :
    performanceApi.submitHumanReview(assignment.assignment_id, payload),
    onSuccess: async (_, variables) => { draft.clearIfUnchanged(variables.draftVersion); onSaved(assignment.assignment_id); await client.invalidateQueries({ queryKey }); },
    onError: (e) => setError(requestError(e)) });
  const change = (index, fields) => { draft.change({ ...draft.value,
    observations: draft.value.observations.map((o, i) => i === index ? { ...o, ...fields } : o) }); onEdit(); };
  function save(event) {
    event.preventDefault();
    if (mutation.isPending) return;
    if ((current?.revision_digest || null) !== draft.value.baseDigest) { setError('A newer observation exists. Compare it with your preserved draft, then discard the draft or explicitly use the latest revision.'); return; }
    const invalid = draft.value.observations.findIndex((o) => !o.reason.trim() || !['NOT_OBSERVED', 'NOT_APPLICABLE', 'UNDER_REVIEW'].includes(o.state));
    if (invalid >= 0 || !draft.value.attested) {
      setError('Explain every dimension, select an unscored state for corrections, and confirm that you have no conflict.');
      form.current?.querySelector(invalid >= 0 ? `[name="reason-${invalid}"]` : '[name="attested"]')?.focus();
      return;
    }
    const payload = { no_conflict_attested: true, observations: draft.value.observations.map((o) => ({ dimension: o.dimension,
      state: o.state, rating: null, reason: o.reason.trim(), direct_observation: false, evidence: [] })) };
    if (current) {
      const hash = JSON.stringify(payload);
      if (attempt.current?.hash !== hash) attempt.current = { hash, id: crypto.randomUUID() };
      Object.assign(payload, { expected_digest: draft.value.baseDigest, request_id: attempt.current.id,
        reason: 'Reviewer correction to an explicitly unscored observation state' });
    }
    setError(''); mutation.mutate({ payload, draftVersion: draft.value });
  }
  return <form ref={form} noValidate onSubmit={save} className="scoring-stack">
    {current && <p className="scoring-help">Revision {current.revision}. Corrections append history; they do not overwrite the earlier observation.</p>}
    <fieldset disabled={mutation.isPending} className="scoring-stack"><legend>Period observations</legend>
      {draft.value.observations.map((o, i) => <div className="scoring-stack" key={o.dimension}>
        <Select label={o.dimension.replaceAll('_', ' ')} value={o.state} onChange={(e) => change(i, { state: e.target.value })}
          options={[...(o.state === 'OBSERVED' ? [{ value: 'OBSERVED', label: 'Earlier numerical observation — choose an unscored state to correct' }] : []),
            { value: 'NOT_OBSERVED', label: 'Not observed' }, { value: 'NOT_APPLICABLE', label: 'Not applicable — explain why' },
            { value: 'UNDER_REVIEW', label: 'Evidence awaiting review' }]} />
        <NotesField label={`Reason for ${o.dimension.replaceAll('_', ' ')}`} name={`reason-${i}`} maxLength={2000}
          value={o.reason} error={error && !o.reason.trim() ? 'Explain this dimension before recording it.' : undefined} onChange={(e) => change(i, { reason: e.target.value })} />
      </div>)}
      <label><input name="attested" type="checkbox" checked={draft.value.attested}
        onChange={(e) => draft.change({ ...draft.value, attested: e.target.checked })} /> I have no conflict and have explained the observation limits.</label>
    </fieldset>
    {error && <p role="alert" className="scoring-error">{error}</p>}
    {current && <details><summary>Latest saved observations</summary>{current.observations.map((o) => <p key={o.dimension}>{o.dimension.replaceAll('_', ' ')}: {o.state} — {o.reason}</p>)}</details>}
    <div className="scoring-actions"><Button type="submit" style={{ minWidth: '16rem' }} aria-busy={mutation.isPending} isLoading={mutation.isPending}>Record observations</Button>
      {draft.dirty && <Button variant="secondary" disabled={mutation.isPending} onClick={() => { draft.clear(); setError(''); }}>Discard draft</Button>}
      {error && <Button variant="secondary" onClick={() => reload()}>Reload latest record</Button>}
      {current && current.revision_digest !== draft.value.baseDigest && <Button variant="secondary" onClick={() => draft.change({ ...draft.value, baseDigest: current.revision_digest, attested: false })}>Use latest revision after review</Button>}
    </div>
    <p className="scoring-help">Draft notes are kept only in this session, including if you change the selected assignment. Sign-out clears them.</p>
  </form>;
}
