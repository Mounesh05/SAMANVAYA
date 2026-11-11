import React from 'react';

export function BehavioralCompatibilitySection({ report }) {
  if (!report) return null;
  return <section aria-label="Behavioral compatibility results" style={{ margin: '1rem 0' }}>
    <h4>Behavioral compatibility: {report.status}</h4>
    <p>Previous implementation: {report.previous?.name} ({report.previous?.language}) · Revision: {report.previous?.source_revision || 'Not established'}</p>
    <p>Current implementation: {report.current?.name} ({report.current?.language}) · Revision: {report.current?.source_revision || 'Not established'}</p>
    <p>Relationship: {report.relationship?.status || 'PROVISIONAL'}. Earlier implementations and similar structures are not proof of substitutability.</p>
    <p>Contract resolution: {report.contract_resolution?.status} · Contract: {report.contract_resolution?.contract_ids?.join(', ') || 'Missing'}</p>
    <p>Required checks: {report.required_checks?.join(', ') || 'Not established'}</p>
    <p>Phase 1 eligibility: {report.phase1_eligible ? 'Established within the tested contract; measurement prerequisites still apply.' : 'Blocked; no verified replacement or superiority claim.'}</p>
    <ul>{(report.checks || []).map((check, i) => <li key={i}>
      {check.candidate} · {check.dataset_id}: <strong>{check.status}</strong> · {check.reason}
      {check.violation && <p>Violation: {check.violation}</p>}
      <p>Evidence: {check.evidence_reference} · Input fingerprint: {check.input_fingerprint || 'Missing input'}</p>
    </li>)}</ul>
    <h5>Unverified behavior</h5>
    <ul>{(report.unverified_behavior || []).map((reason, i) => <li key={i}>{reason}</li>)}</ul>
    <details><summary>Approved scope, requirements and provenance</summary>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ contract: report.contract_resolution, requirements: report.requirements,
        relationship: report.relationship, evidence_binding: report.evidence_binding, evidence_refs: report.evidence_refs }, null, 2)}</pre>
    </details>
    <ul>{(report.limitations || []).map((limit, i) => <li key={i}>{limit}</li>)}</ul>
  </section>;
}
