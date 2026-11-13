import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { incidentsApi } from '../../api/incidents.api';
import { Button } from '../../components/common/Button';
import { StatusBadge } from '../../components/common/StatusBadge';
import { formatDate } from '../../utils/dates';

/** CR-014 lifecycle (mirrors backend TRANSITIONS). */
const NEXT_STEPS = {
  open: [{ status: 'investigating', label: 'Acknowledge' }],
  investigating: [{ status: 'resolved', label: 'Resolve' }],
  resolved: [{ status: 'closed', label: 'Close' }, { status: 'investigating', label: 'Reopen' }],
  closed: [],
};
const NEEDS_POSTMORTEM = new Set(['high', 'critical']);

/**
 * CR-014: one incident with owner, timeline and resolution. Triagers
 * (TRIAGE_INCIDENT: DevOps, Lead, PM) get the controls for the allowed next
 * steps; everyone else sees it read-only.
 */
export function IncidentDetail({ incidentId, canTriage }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ assignee_id: '', severity: '', note: '', resolution_summary: '', postmortem: '' });
  const [notice, setNotice] = useState(null);

  const { data: incident, isLoading, error } = useQuery({
    queryKey: ['incident', incidentId],
    queryFn: () => incidentsApi.get(incidentId),
    enabled: Boolean(incidentId),
  });

  const mutation = useMutation({
    mutationFn: (changes) => incidentsApi.triage(incidentId, changes),
    onSuccess: () => {
      setNotice({ tone: 'success', text: 'Incident updated.' });
      setForm({ assignee_id: '', severity: '', note: '', resolution_summary: '', postmortem: '' });
      queryClient.invalidateQueries({ queryKey: ['incident', incidentId] });
      queryClient.invalidateQueries({ queryKey: ['incidents'] });
    },
    onError: (err) => setNotice({ tone: 'danger', text: err?.response?.data?.detail || err?.message || 'The change could not be saved' }),
  });

  if (isLoading) return <p>Loading incident...</p>;
  if (error || !incident) return <p role="alert">Could not load the incident.</p>;

  const set = (field) => (event) => setForm({ ...form, [field]: event.target.value });
  const withNote = (changes) => ({ ...changes, ...(form.note.trim() ? { note: form.note.trim() } : {}) });
  const move = (status) => {
    const changes = { status };
    if (status === 'resolved') changes.resolution_summary = form.resolution_summary.trim() || incident.resolution_summary;
    if (status === 'closed' && form.postmortem.trim()) changes.postmortem = form.postmortem.trim();
    mutation.mutate(withNote(changes));
  };
  const steps = NEXT_STEPS[incident.status] || [];
  const needsReview = NEEDS_POSTMORTEM.has(incident.severity) && !incident.postmortem;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <StatusBadge status={incident.status} />
        <span>Severity: <strong>{incident.severity}</strong></span>
        <span>Owner: <strong>{incident.assignee_name || incident.assignee_id || 'Unassigned'}</strong></span>
      </div>
      <p style={{ margin: 0 }}>{incident.description}</p>
      {incident.resolution_summary && <p style={{ margin: 0 }}><strong>Resolution:</strong> {incident.resolution_summary}</p>}
      {incident.postmortem && <p style={{ margin: 0 }}><strong>Post-incident review:</strong> {incident.postmortem}</p>}

      {notice && (
        <p role={notice.tone === 'danger' ? 'alert' : 'status'} style={{ color: `var(--${notice.tone})`, margin: 0 }}>{notice.text}</p>
      )}

      {canTriage && incident.status !== 'closed' && (
        <section aria-label="Triage" style={{ display: 'grid', gap: '0.5rem' }}>
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <input aria-label="Owner employee ID" placeholder="Owner employee ID" value={form.assignee_id}
              onChange={set('assignee_id')} style={{ flex: '1 1 160px', minWidth: 0, padding: '0.4rem 0.6rem' }} />
            <Button size="sm" variant="secondary" disabled={!form.assignee_id.trim() || mutation.isPending}
              onClick={() => mutation.mutate(withNote({ assignee_id: form.assignee_id.trim() }))}>
              Assign
            </Button>
            <select aria-label="Severity" value={form.severity} onChange={set('severity')}>
              <option value="">Change severity…</option>
              {['low', 'medium', 'high', 'critical'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <Button size="sm" variant="secondary" disabled={!form.severity || mutation.isPending}
              onClick={() => mutation.mutate(withNote({ severity: form.severity }))}>
              Set severity
            </Button>
          </div>
          {incident.status === 'investigating' && (
            <textarea aria-label="Resolution summary" placeholder="Resolution summary (required to resolve)"
              value={form.resolution_summary} onChange={set('resolution_summary')} rows={2} />
          )}
          {incident.status === 'resolved' && needsReview && (
            <textarea aria-label="Post-incident review" placeholder="What happened, the cause, and follow-ups (required to close)"
              value={form.postmortem} onChange={set('postmortem')} rows={3} />
          )}
          <textarea aria-label="Note" placeholder="Note for the timeline (optional)" value={form.note} onChange={set('note')} rows={2} />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            {steps.map((step) => (
              <Button key={step.status} size="sm" variant="primary" onClick={() => move(step.status)}
                disabled={mutation.isPending
                  || (step.status === 'resolved' && !form.resolution_summary.trim() && !incident.resolution_summary)
                  || (step.status === 'closed' && needsReview && !form.postmortem.trim())}>
                {step.label}
              </Button>
            ))}
            <Button size="sm" variant="ghost" disabled={!form.note.trim() || mutation.isPending}
              onClick={() => mutation.mutate({ note: form.note.trim() })}>
              Add note
            </Button>
          </div>
        </section>
      )}

      <section aria-label="Timeline">
        <h3 style={{ fontSize: '0.95rem', margin: '0 0 0.5rem' }}>Timeline</h3>
        <ol style={{ margin: 0, paddingLeft: '1.2rem', display: 'grid', gap: '0.35rem' }}>
          {(incident.timeline || []).map((entry, index) => (
            <li key={`${entry.at}-${index}`}>
              <strong>{entry.action}</strong> by {entry.by_name || entry.by} · {formatDate(entry.at)}
              {Object.entries(entry.changes || {}).map(([field, [from, to]]) => (
                <span key={field}> · {field}: {from ?? '—'} → {to ?? '—'}</span>
              ))}
              {entry.note && <div style={{ color: 'var(--text-muted)' }}>{entry.note}</div>}
            </li>
          ))}
        </ol>
      </section>
    </div>
  );
}
