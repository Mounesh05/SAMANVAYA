import React from 'react';
import { Card } from '../../components/common/Card';

// Why an interpretation did not complete, in words a reviewer can act on.
const AI_ERRORS = {
  MODEL_UNAVAILABLE: 'the AI model could not be reached',
  MODEL_TIMEOUT: 'the AI model did not answer in time',
  INVALID_MODEL_RESPONSE: 'the AI model returned an invalid answer',
  INVALID_AGENT_RESULT: 'the AI model returned an invalid answer',
  MISSING_EVIDENCE: 'there was no measured evidence to interpret',
  AUTHORIZATION_FAILED: 'the AI request was not authorized',
  AUTHORIZATION_MISSING: 'the AI request was not authorized',
  AI_RESULT_ACCESS_DENIED: 'you do not have access to AI results for this project',
};

const DEPENDENCY_AUDIT = {
  not_checked_offline: 'not checked (the isolated worker cannot reach advisory databases)',
  not_checked: 'not checked (no dependency auditor ran)',
  checked: 'checked',
};

export function dependencyAuditLabel(status) {
  return DEPENDENCY_AUDIT[status] || 'unknown';
}

export function ReportStatusNotice({ run }) {
  if (run?.report_status !== 'incomplete') return null;
  return (
    <p role="status" style={{ margin: '0 0 1rem', padding: '0.75rem 1rem', borderRadius: 8,
      border: '1px solid var(--warning)', color: 'var(--text-primary)' }}>
      <strong>Report incomplete:</strong> the measured results below are final, but the AI interpretation did not complete.
    </p>
  );
}

/** Advisory AI interpretation: short summary, at most three cited points, and the evidence it was given. */
export function AIInterpretation({ ai }) {
  if (!ai || ai.status === 'skipped') return null;
  const completed = ai.status === 'completed';
  const reason = (ai.errors || []).map((code) => AI_ERRORS[code] || code).join('; ');
  const points = [...(ai.critical_issues || []), ...(ai.recommendations || [])];
  return (
    <Card title="AI interpretation" style={{ marginBottom: 24 }}>
      <p style={{ marginTop: 0, color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
        Advisory only. Scores and findings are measured by the analysis tools and are not changed by AI.
      </p>
      {!completed && <p><strong>Not available:</strong> {reason || 'the interpretation did not complete'}.</p>}
      {completed && <>
        {ai.analysis && <p style={{ lineHeight: 1.5 }}>{ai.analysis}</p>}
        {points.length > 0
          ? <ul style={{ paddingLeft: '1.25rem', lineHeight: 1.5 }}>{points.map((text, index) => <li key={index}>{text}</li>)}</ul>
          : <p>No recommendations: nothing in the measured evidence needs a change.</p>}
        {ai.evidence_basis?.length > 0 && <details style={{ marginTop: '0.75rem' }}>
          <summary style={{ cursor: 'pointer' }}>Evidence used ({ai.evidence_basis.length})</summary>
          <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', lineHeight: 1.5 }}>
            {ai.evidence_basis.map((fact, index) => <li key={index}>{fact}</li>)}
          </ul>
        </details>}
      </>}
    </Card>
  );
}
