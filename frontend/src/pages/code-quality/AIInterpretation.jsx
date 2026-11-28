import React from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { PermissionGuard } from '../../auth/PermissionGuard';
import { PERMISSIONS } from '../../auth/permissions';
import { codeQualityApi } from '../../api/codeQuality.api';

// Why an interpretation did not complete, in words a reviewer can act on.
const AI_ERRORS = {
  MODEL_UNAVAILABLE: 'the AI model could not be reached',
  MODEL_TIMEOUT: 'the AI model did not answer in time',
  INVALID_MODEL_RESPONSE: 'the AI model returned an invalid answer',
  INVALID_AGENT_RESULT: 'the AI model returned an invalid answer',
  AGENT_FAILED: 'the AI step failed',
  AGENT_ADAPTER_FAILED: 'the AI step failed',
  MISSING_EVIDENCE: 'there was no measured evidence to interpret',
  AUTHORIZATION_FAILED: 'the AI request was not authorized',
  AUTHORIZATION_MISSING: 'the AI request was not authorized',
  AI_RESULT_ACCESS_DENIED: 'you do not have access to AI results for this project',
};

const REPORT_REASONS = {
  static_evidence_unavailable: 'static analysis results are unavailable',
  static_tools_skipped: 'some analysis tools did not run',
  comparison_partial: 'the two revisions could not be compared finding by finding',
  base_revision_not_measured: 'the base revision was not measured',
  head_revision_not_measured: 'the head revision was not measured',
};

const DEPENDENCY_AUDIT = {
  not_checked_offline: 'not checked (the isolated worker cannot reach advisory databases)',
  not_checked: 'not checked (no dependency auditor ran)',
  checked: 'checked',
};

export function dependencyAuditLabel(status) {
  return DEPENDENCY_AUDIT[status] || 'unknown';
}

function reasonLabel(reason) {
  const [kind, detail] = String(reason).split(':');
  if (kind.startsWith('ai_interpretation_')) {
    const codes = (detail || '').split(',').filter(Boolean);
    return `the AI interpretation is ${kind.replace('ai_interpretation_', '')}`
      + (codes.length ? ` (${codes.map((code) => AI_ERRORS[code] || code).join('; ')})` : '');
  }
  return REPORT_REASONS[kind] ? REPORT_REASONS[kind] + (detail && kind === 'static_tools_skipped' ? `: ${detail}` : '') : reason;
}

/** Composite report status: shown in words, never by colour alone. */
export function ReportStatusNotice({ run }) {
  const status = run?.report_status;
  if (!status || status === 'complete') return null;
  const reasons = run.report_incomplete_reasons || [];
  return (
    <div role="status" style={{ margin: '0 0 1rem', padding: '0.75rem 1rem', borderRadius: 8,
      border: '1px solid var(--warning)', color: 'var(--text-primary)' }}>
      <strong>{status === 'failed' ? 'Report failed' : 'Report incomplete'}:</strong>{' '}
      {status === 'failed' ? 'no measured results are available.' : 'the measured results below stand, but'}
      {reasons.length > 0 && <ul style={{ margin: '0.35rem 0 0', paddingLeft: '1.25rem' }}>
        {reasons.map((reason) => <li key={reason}>{reasonLabel(reason)}</li>)}
      </ul>}
    </div>
  );
}

function RetryButton({ runId }) {
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => codeQualityApi.retryAiInterpretation(runId),
    onSuccess: (run) => queryClient.setQueryData(['code-quality-run', runId], run),
  });
  return (
    <PermissionGuard permission={PERMISSIONS.TRIGGER_CODE_ANALYSIS}>
      <Button variant="secondary" size="sm" onClick={() => retry.mutate()} disabled={retry.isPending}>
        {retry.isPending ? 'Retrying AI interpretation…' : 'Retry AI interpretation'}
      </Button>
      {retry.error && <p role="alert">{retry.error.message}</p>}
    </PermissionGuard>
  );
}

/** Advisory AI interpretation: short summary, at most three finding-bound suggestions, limitations, evidence. */
export function AIInterpretation({ ai, runId, attempts }) {
  if (!ai || ai.status === 'skipped') return null;
  const completed = ai.status === 'completed';
  const reason = (ai.errors || []).map((code) => AI_ERRORS[code] || code).join('; ');
  const advisory = ai.advisory;
  const legacyPoints = [...(ai.critical_issues || []), ...(ai.recommendations || [])];
  const canRetry = ['failed', 'unavailable'].includes(ai.status) && runId && (attempts || 1) < 3;
  return (
    <Card title="AI interpretation" style={{ marginBottom: 24 }}>
      <p style={{ marginTop: 0, color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
        Advisory only. Scores and findings are measured by the analysis tools and are not changed by AI.
      </p>
      {!completed && <>
        <p><strong>{ai.status === 'blocked' ? 'Blocked' : 'Not available'}:</strong> {reason || 'the interpretation did not complete'}.</p>
        {canRetry && <RetryButton runId={runId} />}
      </>}
      {completed && advisory && <>
        <p style={{ lineHeight: 1.5 }}>{advisory.summary}</p>
        {advisory.suggestions.length > 0
          ? <ol style={{ paddingLeft: '1.25rem', lineHeight: 1.5 }}>
            {advisory.suggestions.map((item) => <li key={item.finding_id} style={{ marginBottom: '0.5rem' }}>
              <div>{item.action}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
                Finding <code>{item.finding_id}</code>: {item.why}
              </div>
            </li>)}
          </ol>
          : <p>No suggestions. This does not mean the code is free of defects; see the limitations.</p>}
        {advisory.limitations?.length > 0 && <>
          <h4 style={{ margin: '0.75rem 0 0.25rem', fontSize: '0.875rem' }}>Limitations</h4>
          <ul style={{ paddingLeft: '1.25rem', marginTop: 0, lineHeight: 1.5 }}>
            {advisory.limitations.map((text) => <li key={text}>{text}</li>)}
          </ul>
        </>}
      </>}
      {completed && !advisory && <>
        {/* Legacy record from before the advisory contract; shown as recorded. */}
        {ai.analysis && <p style={{ lineHeight: 1.5 }}>{ai.analysis}</p>}
        {legacyPoints.length > 0
          ? <ul style={{ paddingLeft: '1.25rem', lineHeight: 1.5 }}>
            {legacyPoints.map((text, index) => <li key={index}>{text}</li>)}
          </ul>
          : <p>No recommendations.</p>}
      </>}
      {completed && ai.evidence_basis?.length > 0 && <details style={{ marginTop: '0.75rem' }}>
        <summary style={{ cursor: 'pointer' }}>Evidence used ({ai.evidence_basis.length})</summary>
        <ul style={{ paddingLeft: '1.25rem', marginTop: '0.5rem', lineHeight: 1.5 }}>
          {ai.evidence_basis.map((fact, index) => <li key={index}>{fact}</li>)}
        </ul>
      </details>}
    </Card>
  );
}

const DIMENSION_LABELS = {
  static_security: 'Static and security findings', testing: 'Testing', complexity: 'Complexity',
  architecture: 'Architecture', duplication: 'Duplication',
};

/** How the existing engine produced the quality score (CQ-15/CQ-17). */
export function ScoreExplanation({ explanation, policyDigest }) {
  if (!explanation) return null;
  return (
    <details style={{ marginBottom: 24 }}>
      <summary style={{ cursor: 'pointer', fontWeight: 600 }}>How the quality score was calculated</summary>
      <p style={{ lineHeight: 1.5 }}>{explanation.formula}.
        {explanation.renormalized && ' Some dimensions were not measured, so the weights of the measured ones were rescaled to add up to 1.'}
      </p>
      <div style={{ overflowX: 'auto' }}>
        <table style={{ borderCollapse: 'collapse', minWidth: 420 }}>
          <thead><tr>
            {['Dimension', 'Measured', 'Configured weight', 'Effective weight', 'Penalty', 'Score'].map((h) =>
              <th key={h} scope="col" style={{ textAlign: 'left', padding: '0.25rem 0.75rem 0.25rem 0' }}>{h}</th>)}
          </tr></thead>
          <tbody>{explanation.dimensions.map((d) => <tr key={d.dimension}>
            <td style={{ padding: '0.25rem 0.75rem 0.25rem 0' }}>{DIMENSION_LABELS[d.dimension] || d.dimension}</td>
            <td>{d.measured ? 'Yes' : 'Not measured'}</td>
            <td>{d.configured_weight}</td>
            <td>{d.effective_weight ?? '—'}</td>
            <td>{d.penalty ?? '—'}</td>
            <td>{d.score ?? '—'}</td>
          </tr>)}</tbody>
        </table>
      </div>
      <p style={{ color: 'var(--text-muted)', fontSize: '0.8125rem' }}>
        Weighted penalty {explanation.weighted_penalty}{policyDigest ? ` · policy ${policyDigest}` : ''}
      </p>
    </details>
  );
}
