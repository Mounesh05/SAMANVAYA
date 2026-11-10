import React from 'react';

export function DecisionResults({ decision, revisions = [] }) {
  if (!decision) return null;
  return <section aria-label="Deterministic decision">
    <h4>Deterministic decision: {decision.task_suitability.status}</h4>
    <p>Engine: {decision.engine_version} · Policy: {decision.policy_id} v{decision.policy_version} · Revision: {decision.revision_number} ({decision.revision_id})</p>
    <p>Task eligibility is evaluated against established requirements. Dataset winners establish no global optimum or untested correctness.</p>
    <p>Eligible for all required datasets: {decision.task_suitability.eligible_candidates.join(', ') || 'None verified'}</p>
    {decision.candidates.map((candidate) => <div key={candidate.candidate}>
      <h5>{candidate.candidate}: {candidate.task_eligibility}</h5>
      <p>Tested correctness: {candidate.correctness}</p>
      {candidate.missing_required_dataset_ids.length > 0 && <p>Missing required datasets: {candidate.missing_required_dataset_ids.join(', ')}</p>}
      <ul>{candidate.datasets.map((dataset) => <li key={dataset.dataset_id}>
        {dataset.dataset_id}: eligibility {dataset.eligibility}; correctness {dataset.correctness}.
        {' '}Timing {dataset.timing.status}: count {dataset.timing.count}, median {dataset.timing.median ?? 'unavailable'} s,
        min {dataset.timing.minimum ?? 'unavailable'} s, max {dataset.timing.maximum ?? 'unavailable'} s,
        variability (range/median) {dataset.timing.variability_ratio ?? 'unavailable'}.
        {' '}Memory {dataset.memory.status}: {dataset.memory.bytes ?? 'unavailable'} bytes ({dataset.memory.metric || 'metric unavailable'}).
        <p>Evidence: {dataset.evidence_reference}</p>
      </li>)}</ul>
      <ul aria-label={`Constraint evaluations for ${candidate.candidate}`}>{candidate.constraint_evaluations.map((check, i) => <li key={i}>
        {check.constraint_id}: {check.status} · {check.classification} · Scope: {check.dataset_id ?? 'required dataset set'} · Source: {check.source_reference}
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(check, null, 2)}</pre>
      </li>)}</ul>
    </div>)}
    <h5>Dataset comparisons</h5>
    <ul>{decision.dataset_comparisons.map((comparison) => <li key={comparison.dataset_id}>
      {comparison.dataset_id}: {comparison.status} · Dataset winner: {comparison.winner || 'Not established'}
      <p>{comparison.reason}</p>
    </li>)}</ul>
    <h5>Unknown requirements</h5>
    <p>Unknown thresholds do not imply failure or establish compliance.</p>
    <ul>{decision.unknown_requirements.map((requirement) => <li key={requirement.id}>{requirement.id}: {requirement.description}</li>)}</ul>
    <h5>Missing measurements</h5>
    <ul>{decision.missing_evidence.map((item, i) => <li key={i}>{item.candidate} / {item.dataset_id}: {item.measurement} {item.status} · {item.evidence_reference || 'No measured case'}</li>)}</ul>
    <h5>Unverified requirements</h5>
    <ul>{(decision.unverified_requirements || []).map((item, i) => <li key={i}>{item.candidate} / {item.dataset_id ?? 'required dataset set'}: {item.constraint_id} · {item.metric || item.type} · {item.status}</li>)}</ul>
    <ul>{decision.limitations.map((limitation, i) => <li key={i}>{limitation}</li>)}</ul>
    <details>
      <summary>Policy, provenance, fingerprints and preserved revisions ({revisions.length})</summary>
      <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ policy: decision.policy_snapshot, identities: decision.identities,
        policy_fingerprint: decision.policy_fingerprint, provenance: decision.provenance, revisions }, null, 2)}</pre>
    </details>
  </section>;
}
