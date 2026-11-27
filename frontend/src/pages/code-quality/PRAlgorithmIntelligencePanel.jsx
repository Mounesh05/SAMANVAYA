import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { DecisionResults } from './DecisionResults';
import { RequirementsSection } from './RequirementsPanel';
import { BehavioralCompatibilitySection } from './BehavioralCompatibilitySection';
import { useSessionScope } from '../../store/useSessionScope';
import { AlgorithmAdvisory } from '../algorithm-intelligence/AlgorithmAdvisory';

const statusLabel = value => ({ pending: 'Pending', analyzing: 'Analyzing', benchmarking: 'Benchmarking', completed: 'Completed',
  insufficient_evidence: 'Insufficient evidence', unsupported: 'Unsupported', failed: 'Failed', superseded: 'Superseded',
  analyzed: 'Analysed (static only)', blocked: 'Blocked', not_applicable: 'Not applicable' }[value] || value);

const comparisonLabel = value => ({ not_analyzed: 'Not analysed', not_applicable: 'Not applicable — no predecessor',
  unsupported: 'Unsupported by the worker protocol', blocked: 'Blocked before execution', deferred: 'Deferred by the budget',
  completed: 'Executed', inconclusive: 'Executed, inconclusive', failed: 'Worker failed' }[value] || value);

const modeLabel = value => ({ A: 'Mode A · standalone', B: 'Mode B · base vs head', C: 'Mode C · same-revision alternatives' }[value] || value);

const categoryLabel = value => ({ application: 'Application', test: 'Test', test_helper: 'Test helper',
  helper: 'Helper', nested: 'Nested definition' }[value] || value);

const countBy = (rows, pick) => rows.reduce((acc, row) => {
  const key = pick(row);
  if (key) acc[key] = (acc[key] || 0) + 1;
  return acc;
}, {});

export function WorkloadDifferences({ decision }) {
  if (!decision) return null;
  const previous = decision.candidates?.find(c => c.candidate === 'previous');
  const current = decision.candidates?.find(c => c.candidate === 'current');
  if (!previous || !current) return null;
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

/** Static bound with an explicit statement whenever a bound could not be established. */
export function ComplexitySummary({ complexity, label = 'Estimated complexity' }) {
  if (!complexity) return null;
  const dimensions = Object.entries(complexity.dimension_bindings || {});
  const unknown = complexity.unknown_reasons || [];
  const strip = value => value ? String(value).replace(/^(time|space):\s*/, '') : null;
  const timeReason = strip(complexity.time_complexity_reason) || strip(unknown.find(reason => reason.startsWith('time:')))
    || unknown[0] || 'no reason was recorded';
  const spaceReason = strip(complexity.space_complexity_reason) || strip(unknown.find(reason => reason.startsWith('space:')));
  return <div className="cq-complexity">
    <p>{label}: time {complexity.time_complexity || 'unavailable'} · space {complexity.space_complexity || 'unavailable'}
      {' · '}{complexity.status || 'unknown'} ({complexity.confidence || 'none'} confidence)</p>
    {dimensions.length > 0 && <p>Dimensions: {dimensions.map(([letter, binding]) => `${letter} = ${binding}`).join(', ')}</p>}
    {!complexity.time_complexity && <p>No time bound established: {timeReason}</p>}
    {!complexity.space_complexity && <p>No space bound established: {spaceReason || 'no reason was recorded'}</p>}
    <details><summary>Basis, assumptions and limitations</summary>
      <ul>
        {(complexity.derivation || []).map((step, i) => <li key={`d${i}`}>Derivation: {step}</li>)}
        {(complexity.space_derivation || []).map((step, i) => <li key={`s${i}`}>Space: {step}</li>)}
        {(complexity.assumptions || []).map((step, i) => <li key={`a${i}`}>Assumption: {step}</li>)}
        {(complexity.limitations || []).map((step, i) => <li key={`l${i}`}>Limitation: {step}</li>)}
      </ul>
    </details>
  </div>;
}

/** Test evidence grouped by the file that asserts it, never merged into a single number. */
export function TestEvidenceGrouping({ evidence }) {
  if (!evidence?.length) return null;
  const groups = evidence.reduce((acc, item) => {
    const key = item.path || 'unknown file';
    (acc[key] = acc[key] || []).push(item);
    return acc;
  }, {});
  return <details><summary>Static test evidence ({evidence.length} assertion reference{evidence.length === 1 ? '' : 's'})</summary>
    <ul>{Object.entries(groups).map(([path, items]) => <li key={path}>
      {path}: {items.map(item => `line ${item.line}`).join(', ')}
      <ul>{items.map((item, i) => <li key={i}>{item.detail || 'Static assertion reference; not executed or proven authoritative.'}</li>)}</ul>
    </li>)}</ul>
  </details>;
}

/** Only render a comparison for a real counterpart. Standalone bounds are rendered separately. */
export function StaticComparison({ row }) {
  if (!row.previous) return null;
  const before = row.static_previous;
  const after = row.static;
  const cell = (value, fallback) => value || fallback;
  const afterComplexity = after?.complexity || row.complexity;
  const afterCategory = after?.classification?.category || row.classification?.category;
  const afterPatterns = after?.patterns?.length ? after.patterns
    : (row.current?.detected_patterns || []).map(pattern => pattern.kind);
  return <section aria-label="Static comparison">
    <h5>{row.mode === 'C' ? 'Same-revision alternatives' : 'Static comparison'}</h5>
    <table>
      <thead><tr><th>Aspect</th><th>{row.mode === 'C' ? row.previous.qualified_name : 'Previous'}</th><th>{row.mode === 'C' ? row.current?.qualified_name : 'Current'}</th></tr></thead>
      <tbody>
        <tr><td>Declaration</td><td>{row.previous ? row.previous.qualified_name : 'No base counterpart'}</td>
          <td>{row.current?.qualified_name}</td></tr>
        <tr><td>Classification</td>
          <td>{before ? categoryLabel(before.classification?.category) : 'Not analysed'}</td>
          <td>{afterCategory ? categoryLabel(afterCategory) : 'Not analysed'}</td></tr>
        <tr><td>Time bound</td>
          <td>{before?.complexity ? cell(before.complexity.time_complexity, 'Unavailable') : 'Not analysed'}</td>
          <td>{afterComplexity ? cell(afterComplexity.time_complexity, 'Unavailable') : 'Not analysed'}</td></tr>
        <tr><td>Space bound</td>
          <td>{before?.complexity ? cell(before.complexity.space_complexity, 'Unavailable') : 'Not analysed'}</td>
          <td>{afterComplexity ? cell(afterComplexity.space_complexity, 'Unavailable') : 'Not analysed'}</td></tr>
        <tr><td>Observed patterns</td>
          <td>{before?.patterns?.length ? before.patterns.join(', ') : 'None observed'}</td>
          <td>{afterPatterns.length ? afterPatterns.join(', ') : 'None observed'}</td></tr>
      </tbody>
    </table>
    {before?.complexity && <ComplexitySummary complexity={before.complexity} label="Previous-revision complexity" />}
    {!before && row.previous && <p>Previous-revision static analysis is unavailable; only the current revision was analysed.</p>}
  </section>;
}

export function PRAlgorithmIntelligencePanel({ prId, source, projectId, compact = false }) {
  const [selected, setSelected] = useState('');
  const scope = useSessionScope();
  const history = useQuery({ queryKey: ['pr-algorithm-intelligence', scope, prId || projectId || 'accessible-projects'],
    queryFn: () => algorithmsApi.getPRIntelligence(prId ? { pr_id: prId } : projectId ? { project_id: projectId } : {}),
    refetchInterval: source ? false : 5000 });
  const comparison = useQuery({ queryKey: ['algorithms', 'run', scope, selected], queryFn: () => algorithmsApi.getRun(selected), enabled: Boolean(selected) });
  const explanation = useMutation({ mutationFn: runId => algorithmsApi.getExplanation(runId) });
  const staticExplanation = useMutation({
    mutationFn: ({ runId, functionId }) => algorithmsApi.explainPRFunction(runId, functionId),
  });
  const runs = (history.error ? [] : history.data?.analyses || []).filter(run => !projectId || run.project_id === projectId).filter((run) => !source || (
    run.project_id === source.projectId && run.head_sha === source.head &&
    run.pr_number === source.number && run.repository?.toLowerCase() === source.repository.toLowerCase()
  ));
  const FunctionContainer = compact ? 'details' : 'article';
  return <Card className="cq-panel" title={compact ? 'Pull request analyses' : 'PR algorithm checks'}
    subtitle={source ? 'Static findings and measured comparisons for this PR revision' : 'Static analysis and eligible benchmarks for connected projects'}
    style={{ marginBottom: '1.75rem' }}>
    <p className="cq-note">Results cover tested workloads only. Behaviour without an approved contract is reported as unknown.</p>
    {history.isLoading && <p role="status">Loading PR analysis…</p>}
    {history.error && <p role="alert">{history.error.message}</p>}
    {!history.isLoading && !history.error && !runs.length && <p>{source ? 'No stored analysis matches this PR head.' : 'No automatic PR analyses recorded yet.'}</p>}
    {runs.map(run => {
      const rows = run.functions || [];
      const modes = countBy(rows, row => row.mode);
      const categories = countBy(rows, row => row.classification?.category);
      const analysed = rows.filter(row => row.static_status === 'analyzed').length;
      return <details key={run.run_id} open={!run.historical_only}>
        <summary>{run.repository} PR #{run.pr_number} · {statusLabel(run.status)}{run.historical_only ? ' · Historical only' : ''}</summary>
        {compact ? <details><summary>Source revisions</summary><p>Project: {run.project_id} · Base: {run.base_sha} · Head: {run.head_sha}</p></details> : <p>Project: {run.project_id} · Base: {run.base_sha} · Head: {run.head_sha}</p>}
        {run.repository && <a href={`https://github.com/${run.repository}/pull/${run.pr_number}`} target="_blank" rel="noreferrer">Open pull request</a>}
        <p>Analyzed functions: {rows.length} · Validated comparisons: {rows.filter(f => f.compatibility === 'COMPATIBLE_WITHIN_TESTED_CONTRACT').length}</p>
        {run.algorithm_advisory || run.report_status ? <AlgorithmAdvisory key={run.run_id} run={run} kind="pr" refresh={() => history.refetch()} /> : null}
        {!compact && (analysed > 0 || Object.keys(modes).length > 0) && <section aria-label="Analysis summary">
          <p>Static analysis: {analysed} of {rows.length} functions analysed</p>
          <ul>
            {Object.entries(modes).map(([mode, total]) => <li key={mode}>{modeLabel(mode)}: {total}</li>)}
            {Object.entries(categories).map(([category, total]) => <li key={category}>{categoryLabel(category)}: {total}</li>)}
          </ul>
        </section>}
        {!compact && run.comparison_modes && <p>Comparison modes: {Object.entries(run.comparison_modes).map(([mode, total]) => `${modeLabel(mode)} — ${total}`).join(' · ')}</p>}
        {run.reason && <p>{run.reason}</p>}{run.error && <p role="alert">{run.error}</p>}
        {rows.map((fn, i) => <FunctionContainer key={fn.current?.function_id || i}>
          {compact && <summary><span className="ai-function-summary"><strong>{fn.current?.qualified_name || 'Unnamed function'}</strong>
            <span>{fn.mode === 'A' ? 'Standalone' : fn.mode === 'B' ? 'Revision comparison' : fn.mode === 'C' ? 'Alternatives' : 'Analysis'}</span>
            <span>Time: {fn.complexity?.time_complexity || 'Unknown'} · Space: {fn.complexity?.space_complexity || 'Unknown'}</span>
          </span></summary>}
          <h4>{fn.current?.path} · {fn.current?.qualified_name}</h4>
          {compact && !run.algorithm_advisory && !run.report_status && fn.static_status === 'analyzed' && !(staticExplanation.variables?.runId === run.run_id && staticExplanation.variables?.functionId === fn.current?.function_id) && <p>Historical AI explanation: Not requested</p>}
          <p>{fn.benchmark_run_id && fn.mode === 'A' ? 'Static analysis complete' : statusLabel(fn.status)} · {fn.finding_status || fn.compatibility || (fn.mode === 'A' ? 'Standalone assessment' : 'No replacement conclusion')}</p>
          <p>Mode: {modeLabel(fn.mode) || 'Not recorded'} · Classification: {categoryLabel(fn.classification?.category)}
            {fn.classification?.attribution ? ` (attributed to ${fn.classification.attribution})` : ''}</p>
          <p>Static analysis: {fn.static_status === 'analyzed' ? 'Analysed' : 'Not analysed'}
            {' · '}Comparison: {comparisonLabel(fn.comparison_status)}
            {fn.benchmark_status && <> · Benchmark: {statusLabel(fn.benchmark_status)}</>}</p>
          {fn.benchmark_reason && <p>{fn.benchmark_reason}</p>}
          {fn.requirement_proposal && <p>Requirement draft: {['proposed', 'existing'].includes(fn.requirement_proposal.status)
            ? 'Awaiting independent review in Requirements' : fn.requirement_proposal.status.replaceAll('_', ' ')}
            {fn.requirement_proposal.contract_id && <> · {fn.requirement_proposal.contract_id}</>}
            {fn.requirement_proposal.reason && <> · {fn.requirement_proposal.reason}</>}
          </p>}
          {fn.previous && <p>{fn.mode === 'C' ? 'Alternative' : 'Previous'}: {fn.previous.qualified_name} · Current: {fn.current?.qualified_name}</p>}
          <StaticComparison row={fn} />
          {fn.complexity && <ComplexitySummary complexity={fn.complexity} />}
          <p>Possible tasks: {(fn.current?.task_hypotheses || []).map(h => `${h.kind} (${h.status})`).join(', ') || 'Unknown'}</p>
          <p>Observed patterns: {(fn.current?.detected_patterns || []).map(p => p.kind).join(', ') || 'No recognized pattern'}</p>
          <TestEvidenceGrouping evidence={fn.static?.test_expectations} />
          {fn.reason && <p>{fn.reason}</p>}
          <p>Contract: {fn.contract_id || 'No approved applicable contract'} · Evidence: {(fn.evidence_refs || []).join(' · ')}</p>
          {fn.current_decision_reference && <p>Current decision: {fn.current_decision_reference}</p>}
          {run.head_discovery_run_id && <p><a href={`/code-quality/runs/${encodeURIComponent(run.head_discovery_run_id)}`}>Inspect current function evidence</a></p>}
          {fn.static_status === 'analyzed' && fn.current?.function_id && <Button
            disabled={staticExplanation.isPending} onClick={() => staticExplanation.mutate({
              runId: run.run_id, functionId: fn.current.function_id,
            })}>Explain static findings</Button>}
          {staticExplanation.variables?.runId === run.run_id && staticExplanation.variables?.functionId === fn.current?.function_id && (
            <>
              <p>AI explanation: {staticExplanation.data?.status === 'generated' ? 'Model response received' : staticExplanation.data?.status === 'unavailable' ? 'Unavailable — deterministic evidence shown' : staticExplanation.isPending ? 'Running' : 'Not completed'}</p>
              {staticExplanation.data?.explanation && <p style={{ whiteSpace: 'pre-line' }}>{staticExplanation.data.explanation}</p>}
              {staticExplanation.data?.error && <p role="status">{staticExplanation.data.error}</p>}
              {staticExplanation.error && <p role="alert">{staticExplanation.error.message}</p>}
            </>
          )}
          {fn.previous && fn.mode === 'C' && run.head_discovery_run_id && <p><a href={`/code-quality/runs/${encodeURIComponent(run.head_discovery_run_id)}`}>Inspect alternative function evidence</a></p>}
          {fn.previous && fn.mode !== 'C' && run.base_discovery_run_id && <p><a href={`/code-quality/runs/${encodeURIComponent(run.base_discovery_run_id)}`}>Inspect previous function evidence</a></p>}
          {fn.benchmark_run_id && <Button onClick={() => setSelected(fn.benchmark_run_id)}>
            {fn.mode === 'A' ? 'Inspect standalone benchmark' : 'Inspect comparison'} {fn.current?.qualified_name}
          </Button>}
          {fn.datasets && <details><summary>Approved dataset provenance</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(fn.datasets, null, 2)}</pre></details>}
          {fn.requirements_discovery && <RequirementsSection report={fn.requirements_discovery} />}
        </FunctionContainer>)}
        {(run.analysis_truncated || run.input_truncated) && <p>Analysis is partial; these findings do not cover every PR change.</p>}
        {compact ? (run.limitations || []).length > 0 && <details><summary>Limitations</summary><ul>{run.limitations.map((text, i) => <li key={i}>{text}</li>)}</ul></details> : <ul>{(run.limitations || []).map((text, i) => <li key={i}>{text}</li>)}</ul>}
      </details>;
    })}
    {comparison.error && <p role="alert">{comparison.error.message}</p>}
    {comparison.data && !comparison.error && !history.error && <section aria-label={comparison.data.kind === 'pr_standalone' ? 'Standalone benchmark details' : 'Automatic comparison details'}>
      <h3>{comparison.data.kind === 'pr_standalone' ? 'Standalone benchmark' : 'Comparison'} {comparison.data.run_id}</h3>
      <BehavioralCompatibilitySection report={comparison.data.behavioral_compatibility} />
      <RequirementsSection report={comparison.data.decision?.requirements_discovery || comparison.data.requirements_discovery} />
      <WorkloadDifferences decision={comparison.data.decision} />
      <DecisionResults decision={comparison.data.decision} revisions={comparison.data.decision_revisions} />
      <Button onClick={() => explanation.mutate(selected)} disabled={explanation.isPending}>Explain measured findings</Button>
      {explanation.data && explanation.variables === selected && <div>
        <p>AI explanation: {explanation.data.status === 'generated' ? 'Model response received' : explanation.data.status === 'unavailable' ? 'Unavailable — deterministic evidence shown' : 'Not completed'}</p>
        <p style={{ whiteSpace: 'pre-line' }}>{explanation.data.explanation || 'No explanation available.'}</p>
        {explanation.data.error && <p role="status">{explanation.data.error}</p>}
      </div>}
      {explanation.error && explanation.variables === selected && <p role="alert">{explanation.error.message}</p>}
      <details><summary>Candidate source</summary>{(comparison.data.request?.candidates || []).map(candidate => <section key={candidate.name}>
        <h4>{candidate.name}: {candidate.entrypoint}</h4><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{candidate.source}</pre>
      </section>)}</details>
      <details><summary>Measurements and environment evidence</summary><pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ results: comparison.data.results, environment: comparison.data.environment, tools: comparison.data.tools }, null, 2)}</pre></details>
    </section>}
  </Card>;
}
