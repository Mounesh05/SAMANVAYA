import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { codeQualityApi } from '../../api/codeQuality.api';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { algorithmsApi } from '../../api/algorithms.api';
import { BehavioralCompatibilitySection } from './BehavioralCompatibilitySection';

function FunctionCompatibilityHistory({ projectId, functionId }) {
  const [enabled, setEnabled] = useState(false);
  const { data, error } = useQuery({ queryKey: ['function-compatibility', projectId, functionId],
    queryFn: () => algorithmsApi.getFunctionCompatibility(projectId, functionId), enabled: enabled && Boolean(projectId) });
  if (!projectId) return null;
  return <div>
    <Button variant="secondary" onClick={() => setEnabled(true)}>Load behavioral compatibility history</Button>
    {error && <p role="alert">Could not load compatibility evidence: {error.message}</p>}
    {data && <p>Historical validation scope only; a changed source requires fresh validation.</p>}
    {data && !data.history?.length && <p>No behavioral validation recorded for this function identity.</p>}
    {(data?.history || []).map(run => <div key={run.run_id}><p>Run {run.run_id}: {run.status}</p><BehavioralCompatibilitySection report={run.behavioral_compatibility} /></div>)}
  </div>;
}

export function DiscoveredFunctions({ runId, pending = false }) {
  const [skip, setSkip] = useState(0);
  const { data, isLoading, error } = useQuery({
    queryKey: ['discovered-functions', runId, skip],
    queryFn: () => codeQualityApi.getDiscoveredFunctions(runId, { skip, limit: 50 }),
    enabled: Boolean(runId) && !pending,
  });
  return <Card title="Discovered functions" subtitle="Observed structure and possible computational purposes">
    <p>Discovery runs with code analysis and PR synchronization. Patterns and inferred tasks are not verified functional requirements or correctness guarantees. No benchmarks are started here.</p>
    {pending ? <p>Available when analysis finishes.</p> : isLoading ? <p role="status">Loading discovered functions...</p> : error ? <p role="alert">Could not load function evidence: {error.message}</p> : <>
      <p>Status: {data?.status || 'not_analyzed'} · Method: {data?.method || 'Not recorded'} · Revision: {data?.source_revision || 'Unknown'}</p>
      {data?.status === 'not_analyzed' && <p>This run has no purpose-discovery snapshot. Start a new analysis or synchronize a PR to collect one.</p>}
      {data?.diagnostics?.length > 0 && <details><summary>Unavailable or incomplete source</summary>
        <ul>{data.diagnostics.map((d, i) => <li key={i}>{d.path || 'Repository'}: {d.kind}{d.line ? ` at line ${d.line}` : ''}. {d.message || ''}</li>)}</ul>
      </details>}
      {!data?.functions?.length && data?.status === 'available' && <p>No supported functions were found in the inspected source.</p>}
      {(data?.functions || []).map(fn => <article key={fn.function_id} style={{ margin: '1rem 0', borderTop: '1px solid var(--border-default)', paddingTop: '1rem' }}>
        <h4>{fn.qualified_name} <small>({fn.language}{fn.is_async ? ', async' : ''})</small></h4>
        <p>{fn.path}:{fn.line} · Task status: <strong>{fn.task_status}</strong> · Possible task: {fn.possible_task || 'Not established'}</p>
        <p>Verified contract: {fn.verified_contract ? 'Recorded' : 'None established'}</p>
        <dl>
          <dt>Structural patterns inferred from observed syntax</dt>
          <dd>{fn.detected_patterns?.length ? fn.detected_patterns.map(p => `${p.kind} (${p.status || 'INFERRED'})`).join(', ') : 'No recognized pattern; structural metadata remains available.'}</dd>
          <dt>Possible computational tasks</dt>
          <dd><ul>{(fn.task_hypotheses || []).map(h => <li key={h.kind}>{h.kind} — {h.status}: {h.supported_conclusion}
            <p>Evidence: {h.evidence_refs.join(', ')}</p>
            <ul>{h.missing_information.map((m, i) => <li key={i}>{m}</li>)}</ul>
          </li>)}</ul></dd>
        </dl>
        <details><summary>Evidence, signature and call relationships</summary>
          <p>Function identity: {fn.function_id} · Method: {fn.method} · Source hash: {fn.source_hash}</p>
          <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ parameters: fn.parameters, returns: fn.returns, return_annotation: fn.return_annotation, structure: fn.structure, calls: fn.calls, callers: fn.callers }, null, 2)}</pre>
          <ul>{(fn.evidence || []).map(e => <li key={e.id}><strong>{e.status}</strong> {e.kind}: {e.subject} {e.related}
            <p>{e.path}:{e.line} · {e.id} · {e.method} · Revision: {e.source_revision || 'Unknown'} · Hash: {e.source_hash}</p><p>{e.detail}</p>
          </li>)}</ul>
        </details>
        <details><summary>Pattern evidence</summary><pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(fn.detected_patterns, null, 2)}</pre></details>
        <ul aria-label={`Uncertainty for ${fn.qualified_name}`}>{(fn.uncertainty || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
        <FunctionCompatibilityHistory projectId={fn.repository_id} functionId={fn.function_id} />
      </article>)}
      <div style={{ display: 'flex', gap: '1rem', marginTop: '1rem' }}>
        <Button variant="secondary" disabled={skip === 0} onClick={() => setSkip(Math.max(0, skip - 50))}>Previous functions</Button>
        <Button variant="secondary" disabled={skip + (data?.returned || 0) >= (data?.total || 0)} onClick={() => setSkip(skip + 50)}>Next functions</Button>
      </div>
      <ul>{(data?.limitations || []).map((item, i) => <li key={i}>{item}</li>)}</ul>
    </>}
  </Card>;
}
