import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { DecisionResults } from './DecisionResults';
import { RequirementsSection } from './RequirementsPanel';
import { BehavioralCompatibilitySection } from './BehavioralCompatibilitySection';

const statusLabel = value => ({ pending: 'Pending', analyzing: 'Analyzing', benchmarking: 'Benchmarking', completed: 'Completed',
  insufficient_evidence: 'Insufficient evidence', unsupported: 'Unsupported', failed: 'Failed', superseded: 'Superseded' }[value] || value);

export function WorkloadDifferences({ decision }) {
  if (!decision) return null;
  const previous = decision.candidates?.find(c => c.candidate === 'previous');
  const current = decision.candidates?.find(c => c.candidate === 'current');
  return <section aria-label="Measured workload differences"><h4>Measured differences: current minus previous</h4>
    <p>These are descriptive measurements. Contract correctness, eligibility, uncertainty and the deterministic decision control their interpretation.</p>
    <ul>{(decision.dataset_comparisons || []).map(dataset => {
      const a = previous?.datasets.find(d => d.dataset_id === dataset.dataset_id);
      const b = current?.datasets.find(d => d.dataset_id === dataset.dataset_id);
      const comparable = ['ELIGIBLE_WINNER', 'CONDITIONAL_COMPARISON', 'MULTIPLE_ELIGIBLE'].includes(dataset.status)
        && previous?.methodology_fingerprint && previous.methodology_fingerprint === current?.methodology_fingerprint;
      const eligible = comparable && a?.eligibility === 'ELIGIBLE' && b?.eligibility === 'ELIGIBLE';
      const timing = eligible && a?.timing?.status === 'AVAILABLE' && b?.timing?.status === 'AVAILABLE' && Number.isFinite(a.timing.median) && Number.isFinite(b.timing.median);
      const memory = eligible && a?.memory?.status === 'AVAILABLE' && b?.memory?.status === 'AVAILABLE' && a.memory.metric === 'memray_peak_tracked_allocations_bytes' && b.memory.metric === a.memory.metric && Number.isFinite(a.memory.bytes) && Number.isFinite(b.memory.bytes);
      return <li key={dataset.dataset_id}>{dataset.dataset_id}: {timing ? `Median time delta ${(b.timing.median - a.timing.median).toPrecision(6)} seconds` : 'Time difference unverified'}.
        {' '}{memory ? `Peak tracked allocation delta ${b.memory.bytes - a.memory.bytes} bytes` : 'Peak memory difference unverified; compatible eligible peak measurements required'}.</li>;
    })}</ul>
  </section>;
}

export function PRAlgorithmIntelligencePanel({ prId }) {
  const [selected, setSelected] = useState('');
  const history = useQuery({ queryKey: ['pr-algorithm-intelligence', prId || 'accessible-projects'],
    queryFn: () => algorithmsApi.getPRIntelligence(prId ? { pr_id: prId } : {}),
    refetchInterval: 5000 });
  const comparison = useQuery({ queryKey: ['algorithms', 'run', selected], queryFn: () => algorithmsApi.getRun(selected), enabled: Boolean(selected) });
  const explanation = useMutation({ mutationFn: runId => algorithmsApi.getExplanation(runId) });
  const runs = history.error ? [] : history.data?.analyses || [];
  return <Card title="PR Algorithm Intelligence" subtitle="Automatic evidence and fresh comparisons for connected projects" style={{ marginBottom: '1.75rem' }}>
    <p>Approved functional contracts determine what can be validated. Missing behavior stays unknown. Findings apply to tested workloads and do not identify a production-optimal algorithm.</p>
    {history.isLoading && <p role="status">Loading PR analysis…</p>}
    {history.error && <p role="alert">{history.error.message}</p>}
    {!history.isLoading && !history.error && !runs.length && <p>No automatic PR analyses recorded for your connected projects.</p>}
    {runs.map(run => <details key={run.run_id} open={!run.historical_only}>
      <summary>{run.repository} PR #{run.pr_number} · {statusLabel(run.status)}{run.historical_only ? ' · Historical only' : ''}</summary>
      <p>Project: {run.project_id} · Base: {run.base_sha} · Head: {run.head_sha}</p>
      {run.repository && <a href={`https://github.com/${run.repository}/pull/${run.pr_number}`} target="_blank" rel="noreferrer">Open pull request</a>}
      <p>Analyzed functions: {run.functions?.length || 0} · Validated comparisons: {(run.functions || []).filter(f => f.compatibility === 'COMPATIBLE_WITHIN_TESTED_CONTRACT').length}</p>
      {run.reason && <p>{run.reason}</p>}{run.error && <p role="alert">{run.error}</p>}
      {(run.functions || []).map((fn, i) => <article key={fn.current?.function_id || i}>
        <h4>{fn.current?.path} · {fn.current?.qualified_name}</h4>
        <p>{statusLabel(fn.status)} · {fn.finding_status || fn.compatibility || 'No replacement conclusion'}</p>
        <p>Previous: {fn.previous?.qualified_name || 'Unavailable'} · Current: {fn.current?.qualified_name}</p>
        <p>Possible tasks: {(fn.current?.task_hypotheses || []).map(h => `${h.kind} (${h.status})`).join(', ') || 'Unknown'}</p>
        <p>Observed patterns: {(fn.current?.detected_patterns || []).map(p => p.kind).join(', ') || 'No recognized pattern'}</p>
        {fn.reason && <p>{fn.reason}</p>}
        <p>Contract: {fn.contract_id || 'No approved applicable contract'} · Evidence: {(fn.evidence_refs || []).join(' · ')}</p>
        {fn.current_decision_reference && <p>Current decision: {fn.current_decision_reference}</p>}
        {run.head_discovery_run_id && <p><a href={`/code-quality/runs/${encodeURIComponent(run.head_discovery_run_id)}`}>Inspect current function evidence</a></p>}
        {fn.previous && run.base_discovery_run_id && <p><a href={`/code-quality/runs/${encodeURIComponent(run.base_discovery_run_id)}`}>Inspect previous function evidence</a></p>}
        {fn.benchmark_run_id && <Button onClick={() => setSelected(fn.benchmark_run_id)}>Inspect comparison {fn.current?.qualified_name}</Button>}
        {fn.datasets && <details><summary>Approved dataset provenance</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(fn.datasets, null, 2)}</pre></details>}
        {fn.requirements_discovery && <RequirementsSection report={fn.requirements_discovery} />}
      </article>)}
      {(run.analysis_truncated || run.input_truncated) && <p>Analysis is partial; these findings do not cover every PR change.</p>}
      <ul>{(run.limitations || []).map((text, i) => <li key={i}>{text}</li>)}</ul>
    </details>)}
    {comparison.error && <p role="alert">{comparison.error.message}</p>}
    {comparison.data && !comparison.error && !history.error && <section aria-label="Automatic comparison details">
      <h3>Comparison {comparison.data.run_id}</h3>
      <BehavioralCompatibilitySection report={comparison.data.behavioral_compatibility} />
      <RequirementsSection report={comparison.data.decision?.requirements_discovery || comparison.data.requirements_discovery} />
      <WorkloadDifferences decision={comparison.data.decision} />
      <DecisionResults decision={comparison.data.decision} revisions={comparison.data.decision_revisions} />
      <Button onClick={() => explanation.mutate(selected)} disabled={explanation.isPending}>Explain measured findings</Button>
      {explanation.data && explanation.variables === selected && <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(explanation.data, null, 2)}</pre>}
      {explanation.error && explanation.variables === selected && <p role="alert">{explanation.error.message}</p>}
      <details><summary>Previous and current source</summary>{(comparison.data.request?.candidates || []).map(candidate => <section key={candidate.name}>
        <h4>{candidate.name}: {candidate.entrypoint}</h4><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{candidate.source}</pre>
      </section>)}</details>
      <details><summary>Measurements and environment evidence</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ results: comparison.data.results, environment: comparison.data.environment, tools: comparison.data.tools }, null, 2)}</pre></details>
    </section>}
  </Card>;
}
