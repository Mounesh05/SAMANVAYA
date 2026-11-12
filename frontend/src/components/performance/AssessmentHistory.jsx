import React, { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { performanceApi } from '../../api/performance.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Select } from '../common/Select';
import { Textarea as NotesField } from '../common/Textarea';
import { ScoreCard } from '../common/ScoreCard';
import { requestError } from '../../utils/performanceScoring';
import { useScoringDraft } from './useScoringDraft';

export function AssessmentHistory({ employeeId }) {
  const user = useAuthStore((s) => s.user);
  const [selected, setSelected] = useState('');
  const [replay, setReplay] = useState(null);
  const [notice, setNotice] = useState(null);
  const listKey = ['assessments', user?.employee_id, user?.role, employeeId];
  const records = useQuery({ queryKey: listKey, queryFn: () => performanceApi.getAssessments(employeeId),
    enabled: Boolean(employeeId), retry: false });
  const id = records.data?.some((r) => r.assessment_id === selected) ? selected : records.data?.[0]?.assessment_id;
  const historyKey = ['assessment-history', user?.employee_id, user?.role, id];
  const history = useQuery({ queryKey: historyKey, queryFn: () => performanceApi.getAssessmentHistory(id), enabled: Boolean(id), retry: false,
    refetchOnWindowFocus: false });
  const replayMutation = useMutation({ mutationFn: ({ revision, assessmentId }) => performanceApi.replayAssessment(assessmentId, revision),
    onSuccess: (data, variables) => setReplay({ assessmentId: variables.assessmentId, data }) });
  const selectedRecord = records.data?.find((r) => r.assessment_id === id);
  return <Card title="Assessment history" className="scoring-stack">
    {records.isPending ? <p role="status">Loading scoped assessments…</p> : records.isError ?
      <div role="alert"><p>{requestError(records.error)}</p><Button onClick={() => records.refetch()}>Retry assessment list</Button></div> : !records.data?.length ?
        <p>No canonical assessment is available in your scope. Legacy records above are preserved historical values.</p> : <>
          <Select label="Assessment" value={id || ''} placeholder={null} onChange={(e) => { setSelected(e.target.value); setReplay(null); setNotice(null); }}
            options={records.data.map((r) => ({ value: r.assessment_id, label: `${r.period_start?.slice(0, 10) || r.assessment_id.slice(0, 14)} · ${r.state}` }))} />
          {history.isPending ? <p role="status">Loading immutable history…</p> : history.isError ?
            <div role="alert"><p>{requestError(history.error)}</p><Button onClick={() => history.refetch()}>Retry history</Button></div> : <>
              <ScoreCard title="Current assessment" scoring={history.data.current} />
              <div className="scoring-table-wrap"><table className="scoring-table"><caption>Immutable revision history</caption>
                <thead><tr><th>Revision</th><th>State</th><th>Historical approved score</th><th>Validation</th></tr></thead>
                <tbody>{history.data.history.map((r) => <tr key={r.event_id}><td>{r.revision}</td><td>{r.state.replaceAll('_', ' ')}</td>
                  <td>{r.approved_score == null ? 'Not approved in this revision' : r.approved_score.toFixed(2)}</td>
                  <td>{r.state === 'APPROVED' && <Button variant="secondary" size="sm" disabled={replayMutation.isPending}
                    onClick={() => { setReplay(null); replayMutation.mutate({ revision: r.revision, assessmentId: id }); }}>Replay revision {r.revision}</Button>}</td></tr>)}</tbody>
              </table></div>
              {replayMutation.isError && replayMutation.variables?.assessmentId === id && <p role="alert">{requestError(replayMutation.error)}</p>}
              {replay?.assessmentId === id && <p role="status">Frozen revision {replay.data.revision}: {replay.data.status.toLowerCase()}. This replays frozen inputs; it does not replace later reviews.</p>}
              {notice === id && <p role="status">Challenge recorded. The earlier assessment remains in history.</p>}
              {selectedRecord?.can_appeal && <AppealForm key={`${user.employee_id}:${id}:${history.data.current.digest}`} owner={user.employee_id}
                assessmentId={id} current={history.data.current} historyKey={historyKey} listKey={listKey}
                onRecorded={() => setNotice(id)} onEdit={() => setNotice(null)} reload={() => history.refetch()} />}
            </>}
        </>}
  </Card>;
}

function AppealForm({ owner, assessmentId, current, historyKey, listKey, onRecorded, onEdit, reload }) {
  const client = useQueryClient();
  const draft = useScoringDraft(`${owner}:appeal:${assessmentId}`, { reason: '', expectedDigest: current.digest });
  const [error, setError] = useState('');
  const field = useRef(null);
  const attempt = useRef(null);
  const mutation = useMutation({ mutationFn: ({ body }) => performanceApi.appealAssessment(assessmentId, body),
    onSuccess: async (_, variables) => { draft.clearIfUnchanged(variables.draftVersion); onRecorded(); await Promise.all([client.invalidateQueries({ queryKey: historyKey }), client.invalidateQueries({ queryKey: listKey })]); },
    onError: (e) => setError(requestError(e)) });
  function submit(event) {
    event.preventDefault();
    if (mutation.isPending) return;
    if (!draft.value.reason.trim()) { setError('Explain the factual issue you want reviewed.'); field.current?.focus(); return; }
    const hash = JSON.stringify(draft.value);
    if (attempt.current?.hash !== hash) attempt.current = { hash, id: crypto.randomUUID() };
    setError(''); mutation.mutate({ body: { expected_digest: draft.value.expectedDigest, request_id: attempt.current.id,
      reason: draft.value.reason.trim(), evidence_references: [] }, draftVersion: draft.value });
  }
  return <form noValidate onSubmit={submit} className="scoring-stack">
    <NotesField label="Factual challenge" ref={field} maxLength={2000} value={draft.value.reason} disabled={mutation.isPending}
      error={error || undefined} helperText="A challenge appends a disputed revision and preserves the earlier record. Do not include secrets or another employee’s private details."
      onChange={(e) => { draft.change({ ...draft.value, reason: e.target.value }); onEdit(); }} />
    <div className="scoring-actions"><Button type="submit" style={{ minWidth: '16rem' }} aria-busy={mutation.isPending} isLoading={mutation.isPending}>Record factual challenge</Button>
      {draft.dirty && <Button variant="secondary" disabled={mutation.isPending} onClick={() => { draft.clear(); setError(''); }}>Discard challenge draft</Button>}
      {error && <Button variant="secondary" onClick={() => reload()}>Reload latest assessment</Button>}
      {draft.value.expectedDigest !== current.digest && <Button variant="secondary" onClick={() => { draft.change({ ...draft.value, expectedDigest: current.digest }); setError(''); }}>Use latest assessment after review</Button>}
    </div>
    <p className="scoring-help">Latest assessment revision {current.revision ?? 'unknown'}: {current.state}. Reloading keeps your notes; explicitly review a newer revision before using it.</p>
  </form>;
}
