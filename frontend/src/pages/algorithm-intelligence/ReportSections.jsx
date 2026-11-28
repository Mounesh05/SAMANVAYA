import React from 'react';

export const statusLabel = value => ({ pending: 'Pending', analyzing: 'Analyzing', benchmarking: 'Benchmarking', completed: 'Completed',
  insufficient_evidence: 'Insufficient evidence', unsupported: 'Unsupported', failed: 'Failed', superseded: 'Superseded',
  analyzed: 'Analysed (static only)', blocked: 'Blocked', not_applicable: 'Not applicable' }[value] || value);

export const comparisonLabel = value => ({ not_analyzed: 'Not analysed', not_applicable: 'Not applicable — no predecessor',
  unsupported: 'Unsupported by the worker protocol', blocked: 'Blocked before execution', deferred: 'Deferred by the budget',
  completed: 'Executed', inconclusive: 'Executed, inconclusive', failed: 'Worker failed' }[value] || value);

export const modeLabel = value => ({ A: 'Mode A · standalone', B: 'Mode B · base vs head', C: 'Mode C · same-revision alternatives' }[value] || value);

export const categoryLabel = value => ({ application: 'Application', test: 'Test', test_helper: 'Test helper',
  helper: 'Helper', nested: 'Nested definition' }[value] || value);

export const countBy = (rows, pick) => rows.reduce((acc, row) => {
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
    {before?.complexity && <ComplexitySummary complexity={before.complexity} label={row.mode === 'C' ? row.previous.qualified_name + ' complexity' : 'Previous-revision complexity'} />}
    {!before && row.previous && <p>{row.mode === 'C' ? 'Static analysis is unavailable for this alternative.' : 'Previous-revision static analysis is unavailable; only the current revision was analysed.'}</p>}
  </section>;
}

