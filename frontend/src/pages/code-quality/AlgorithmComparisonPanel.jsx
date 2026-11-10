import React, { useEffect, useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { algorithmsApi } from '../../api/algorithms.api';
import { useAuthStore } from '../../store/useAuthStore';
import { Button } from '../../components/common/Button';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { DecisionResults } from './DecisionResults';

const activeStatuses = ['pending', 'running'];
const engineeringRoles = ['DEVELOPER', 'LEAD', 'PM', 'CEO', 'QA', 'DEVOPS'];
const pythonKeywords = new Set('False None True and as assert async await break class continue def del elif else except finally for from global if import in is lambda nonlocal not or pass raise return try while with yield'.split(' '));
const distributions = ['random', 'sorted', 'reversed', 'duplicates'];
const sumExample = {
  contract: {
    kind: 'function', name: 'sum-numbers', version: '1',
    input_schema: { type: 'array', minItems: 1, maxItems: 1, items: { type: 'array', items: { type: 'number' } } },
    output_schema: { type: 'number' }, correctness: 'expected', mutation: 'forbidden', output: { source: 'return' },
  },
  datasets: [
    { id: 'empty', args: [[]], expected: 0, dimensions: { count: 0 } },
    { id: 'mixed', args: [[1, -2, 3]], expected: 2, dimensions: { count: 3 } },
  ],
};
const isObject = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);

function parseEditor(text, label) {
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
}

function genericPayload(text) {
  const payload = parseEditor(text, 'Contract and datasets');
  if (!isObject(payload) || Object.keys(payload).some((key) => !['contract', 'datasets'].includes(key))) throw new Error('Provide an object containing only contract and datasets.');
  const { contract, datasets } = payload;
  if (!isObject(contract) || contract.kind !== 'function') throw new Error('Contract must be a non-null object with kind function.');
  if (typeof contract.name !== 'string' || !contract.name.trim() || contract.name.length > 128 || typeof contract.version !== 'string' || !contract.version.trim() || contract.version.length > 64) throw new Error('Contract needs a stable name (1..128 characters) and version (1..64 characters).');
  if (!isObject(contract.input_schema) || contract.input_schema.type !== 'array' || !isObject(contract.output_schema)) throw new Error('input_schema must have type array; output_schema must be an object (or {}).');
  if (!['expected', 'none'].includes(contract.correctness)) throw new Error('Correctness must be expected or none.');
  if (contract.mutation !== undefined && !['allowed', 'forbidden'].includes(contract.mutation)) throw new Error('Mutation must be allowed or forbidden.');
  const output = contract.output === undefined ? { source: 'return' } : contract.output;
  if (!isObject(output) || !['return', 'argument'].includes(output.source) || (output.index !== undefined && (!Number.isSafeInteger(output.index) || output.index < 0))) throw new Error('Output must select return or argument with a nonnegative integer index.');
  if (!Array.isArray(datasets) || datasets.length < 1 || datasets.length > 32) throw new Error('Provide 1..32 datasets.');
  const ids = new Set();
  for (const dataset of datasets) {
    if (!isObject(dataset) || typeof dataset.id !== 'string' || !dataset.id.trim() || dataset.id.length > 128 || !Array.isArray(dataset.args)) throw new Error('Each dataset needs an id (1..128 characters) and args array of positional arguments.');
    if (ids.has(dataset.id)) throw new Error('Dataset ids must be unique.');
    ids.add(dataset.id);
    const hasExpected = Object.hasOwn(dataset, 'expected');
    if (contract.correctness === 'expected' && !hasExpected) throw new Error('Expected correctness requires explicit expected on every dataset (null is allowed).');
    if (contract.correctness === 'none' && hasExpected) throw new Error('Remove expected values when correctness is none.');
    if (output.source === 'argument' && (output.index ?? 0) >= dataset.args.length) throw new Error('Output argument index must exist in every dataset.');
    if (dataset.dimensions !== undefined && !isObject(dataset.dimensions)) throw new Error('Dataset dimensions must be an object.');
  }
  return { contract, datasets };
}

function resourcePayload(text) {
  if (!text.trim()) return {};
  const resources = parseEditor(text, 'Resources');
  if (!isObject(resources)) throw new Error('Resources must be an object, or leave the editor empty.');
  const bounds = { timeout_seconds: [1, 120], memory_bytes: [67108864, 536870912], cpus: [0.1, 1], pids: [16, 64] };
  for (const [key, value] of Object.entries(resources)) {
    if (!Object.hasOwn(bounds, key)) throw new Error(`Unsupported resource limit: ${key}.`);
    const range = bounds[key];
    if (!Number.isFinite(value) || value < range[0] || value > range[1] || (key !== 'cpus' && !Number.isInteger(value))) throw new Error(`Resource ${key} must be ${key === 'cpus' ? 'a number' : 'an integer'} in ${range[0]}..${range[1]}.`);
  }
  return { resources };
}
const stack = { display: 'flex', flexDirection: 'column', gap: '1rem' };
const grid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem' };
const textAreaStyle = {
  width: '100%', padding: '0.75rem', background: 'var(--bg-input)',
  color: 'var(--text-primary)', border: '1px solid var(--border-default)',
  borderRadius: 'var(--radius-md)', fontFamily: 'var(--font-mono)',
};
const cellStyle = { padding: '0.5rem', textAlign: 'left', borderBottom: '1px solid var(--border-subtle)' };

function ErrorMessage({ error }) {
  return error ? <p role="alert" style={{ color: 'var(--danger)' }}>{error.message || String(error)}</p> : null;
}

function median(values) {
  const sorted = (values || []).filter(Number.isFinite).slice().sort((a, b) => a - b);
  if (!sorted.length) return null;
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function seconds(value) {
  return Number.isFinite(value) ? `${value.toPrecision(6)} s` : 'Not measured';
}

function memoryLabel(metric, language) {
  if (/heap|delta/i.test(metric || '') || ['javascript', 'typescript'].includes(language)) {
    return `Node heap delta (not peak)${metric ? ` · ${metric}` : ''}`;
  }
  return metric || 'Memory metric not reported';
}

function RunDetails({ run, canSubmit, onSelectRun }) {
  const queryClient = useQueryClient();
  const [revisionPolicy, setRevisionPolicy] = useState(() => JSON.stringify(run.decision?.policy_snapshot || { id: 'project-policy', version: '1', constraints: [] }, null, 2));
  const [revisionError, setRevisionError] = useState('');
  const reevaluation = useMutation({
    mutationFn: (policy) => algorithmsApi.reevaluate(run.run_id, policy),
    onSuccess: () => Promise.all([
      queryClient.invalidateQueries({ queryKey: ['algorithms', 'run', run.run_id] }),
      queryClient.invalidateQueries({ queryKey: ['algorithms', 'history'] }),
    ]),
  });
  const [reason, setReason] = useState('');
  const [feedbackError, setFeedbackError] = useState('');
  const feedback = useMutation({
    mutationFn: (decision) => algorithmsApi.submitFeedback(run.run_id, { decision, reason: reason.trim() }),
  });
  const explanation = useMutation({ mutationFn: () => algorithmsApi.getExplanation(run.run_id) });
  const compatibleHistory = useMutation({ mutationFn: () => algorithmsApi.getCompatibleHistory(run.run_id) });
  const recommendation = run.recommendation;
  const explicitPolicy = run.decision?.policy_snapshot || run.request?.decision_policy;
  const generic = run.request?.contract != null;
  const terminal = ['completed', 'failed', 'unavailable'].includes(run.status);
  const canReview = canSubmit && run.status === 'completed' && Boolean(recommendation || run.decision);
  const eligibleRankings = (recommendation?.rankings || []).filter((ranking) => ranking.eligible === true);
  const excludedRankings = (recommendation?.rankings || []).filter((ranking) => ranking.eligible !== true);
  const structuralReports = {
    ...Object.fromEntries((run.results || []).filter((result) => result.structure != null).map((result) => [result.candidate, result.structure])),
    ...Object.fromEntries(Object.entries(run.structural_analysis || {}).filter(([, report]) => report != null)),
  };

  const sendFeedback = (decision) => {
    if (!canReview || feedback.isPending) return;
    if (!reason.trim()) {
      setFeedbackError('Enter a reason for your decision.');
      return;
    }
    if (reason.trim().length > 2000) {
      setFeedbackError('Feedback reason must be at most 2000 characters.');
      return;
    }
    setFeedbackError('');
    feedback.mutate(decision);
  };

  return (
    <section aria-label="Benchmark run details" style={stack}>
      <h4>Run {run.run_id}</h4>
      <p role="status">Status: {run.status}</p>
      <ErrorMessage error={run.error} />
      {run.status === 'unavailable' && <p>Ask an administrator to restore the benchmark worker, recheck availability, and submit a new run. History remains available.</p>}
      {run.request && <>
        <p>Language: {run.request.language} · Objective: {explicitPolicy ? (explicitPolicy.objective || 'TRADEOFF_ONLY') : run.request.objective} · Repetitions: {run.request.repetitions} · Seed: {run.request.seed}</p>
        {!generic && <p>Sizes: {run.request.sizes?.join(', ') || 'Not reported'} · Distributions: {run.request.distributions?.join(', ') || 'Not reported'}</p>}
        <p>{explicitPolicy ? 'Legacy tracked allocation limit (descriptive only)' : 'Tracked allocation limit'}: {run.request.memory_limit_bytes == null ? 'None' : `${run.request.memory_limit_bytes} bytes`}</p>
        <details>
          <summary>Request provenance: contract, datasets and resources</summary>
          <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(run.request, null, 2)}</pre>
        </details>
      </>}
      <DecisionResults decision={run.decision} revisions={run.decision_revisions} />
      {recommendation && !run.decision && (
        <div style={stack}>
          <h4>{recommendation.status === 'recommended' ? `Recommended: ${recommendation.winner}` : 'Insufficient evidence'}</h4>
          <p>{recommendation.reason}</p>
          <h5>Passing-only measurement rankings</h5>
          <p>Only complete passing evidence within supported constraints is eligible. Timing rank uses the equal-weight geometric mean of per-case medians, not the median summary. Close timing scores may remain inconclusive.</p>
          {!eligibleRankings.length && <p>No eligible candidates to rank.</p>}
          <ol aria-label="Eligible measurement rankings">{eligibleRankings.map((ranking, index) => (
            <li key={`${ranking.candidate}-${index}`}>
              {ranking.candidate} — Eligible; timing score: {seconds(ranking.timing_score_seconds)}; median summary: {seconds(ranking.median_seconds)};
              {' '}{run.request?.language === 'python' ? `Peak tracked allocations: ${ranking.peak_memory_bytes == null ? 'Not measured' : `${ranking.peak_memory_bytes} bytes`} (not RSS or total RAM)` : 'Node heap delta is not peak memory; see case metrics'}. {ranking.reason}
            </li>
          ))}</ol>
          {excludedRankings.length > 0 && <>
            <h5>Excluded candidates (not ranked)</h5>
            <ul>{excludedRankings.map((ranking, index) => <li key={`${ranking.candidate}-${index}`}>{ranking.candidate} — Ineligible. {ranking.reason}</li>)}</ul>
          </>}
          <h5>Recommendation limitations</h5>
          <ul>{(recommendation.limitations || []).map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
        </div>
      )}
      {Object.entries(structuralReports).map(([candidate, report]) => <details key={candidate}>
        <summary>Structural evidence for {candidate}</summary>
        <p>Source structure observations only, not an asymptotic proof. No Big-O or optimality is inferred.</p>
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(report, null, 2)}</pre>
      </details>)}
      {(run.results || []).map((result, index) => (
        <div key={`${result.candidate}-${index}`}>
          <h4>Candidate: {result.candidate}</h4>
          <p>Raw case diagnostics are not rankings; failed, unverified, or incomplete evidence cannot establish a correctness-backed performance winner.</p>
          <ErrorMessage error={result.error} />

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', fontSize: '0.8125rem' }}>
              <caption>Measured cases for {result.candidate}</caption>
              <thead><tr>{[...(generic ? ['Case ID', 'Dimensions'] : ['Size', 'Distribution']), 'Correctness', ...(generic ? ['Validation status'] : []), 'Median time', 'Raw timings (seconds)', 'Memory (bytes)', 'Memory metric', 'Error'].map((label) => <th style={cellStyle} key={label}>{label}</th>)}</tr></thead>
              <tbody>{(result.cases || []).map((item, caseIndex) => (
                <tr key={caseIndex}>
                  <td style={cellStyle}>{generic ? item.case_id : item.size}</td><td style={cellStyle}>{generic ? JSON.stringify(item.dimensions || {}) : item.distribution}</td>
                  <td style={cellStyle}>{item.correct === true ? 'Pass' : item.correct === false ? 'Fail' : 'Unverified'}</td>
                  {generic && <td style={cellStyle}>{item.validation_status || 'Not reported'}</td>}
                  <td style={cellStyle}>{seconds(median(item.timings_seconds))} {item.timing_status && `(${item.timing_status}: ${item.timing_error || 'available'})`}</td>
                  <td style={cellStyle}>{item.timings_seconds?.length ? item.timings_seconds.join(', ') : 'Not measured'}</td>
                  <td style={cellStyle}>{item.memory_bytes ?? 'Not measured'} {item.memory_status && `(${item.memory_status}: ${item.memory_error || 'available'})`}</td>
                  <td style={cellStyle}>{memoryLabel(item.memory_metric, run.request?.language)}</td>
                  <td style={cellStyle}>{item.error || 'None'}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      ))}
      {terminal && !run.results?.length && <p>No measured cases are available for this run.</p>}
      <section aria-label="Compatible historical runs" style={stack}>
        <h5>Compatible history for saved run {run.run_id}</h5>
        <p>Explicit historical access only, not current measurements. Matching workload or environment does not prove unchanged source or performance. A fresh benchmark is required; these references never rerank this run.</p>
        <Button variant="secondary" isLoading={compatibleHistory.isPending} onClick={() => compatibleHistory.mutate()}>Load compatible history</Button>
        <ErrorMessage error={compatibleHistory.error} />
        {compatibleHistory.data && <>
          <p>Historical only: {compatibleHistory.data.historical_only === true ? 'true' : compatibleHistory.data.historical_only === false ? 'false' : 'Not reported'}</p>
          <ul>{(compatibleHistory.data.limitations || []).map((limitation, index) => <li key={index}>{limitation}</li>)}</ul>
          {!compatibleHistory.data.history?.length && <p>No compatible historical runs found.</p>}
          <ul>{(compatibleHistory.data.history || []).map((item) => <li key={item.run_id}>
            <Button variant="ghost" onClick={() => onSelectRun(item.run_id)}>{item.run_id}</Button>
            {' '}· {item.status} · {item.created_at} · {item.decision ? `Decision: ${item.decision.task_suitability.status}` : `Historical winner: ${item.recommendation?.winner || 'None'}`}
            <p>Historical only: {String(item.historical_only ?? 'Not reported')} · Workload match: {String(item.workload_match ?? 'Not reported')} · Environment match: {String(item.environment_match ?? 'Not reported')}</p>
          </li>)}</ul>
        </>}
      </section>
      {generic && <p>RAG deferred: generic runs do not automatically retrieve or incorporate historical evidence. Compatible history is available only through the explicit action above.</p>}
      {!generic && <div>
        <h5>Historical evidence references</h5>
        <p>Historical context only, separate from this run’s measurements. A matching environment does not prove unchanged source or performance; a fresh benchmark is required.</p>
        {!run.historical_evidence?.length && <p>No historical evidence referenced.</p>}
        <ul>{(run.historical_evidence || []).map((evidence, index) => (
          <li key={`${evidence.run_id}-${index}`}>
            <Button variant="ghost" size="sm" onClick={() => onSelectRun(evidence.run_id)}>{evidence.run_id}</Button>
            {' '}{evidence.created_at} · Historical winner: {evidence.winner || 'None'} · {evidence.reason}
            <p>Environment: {evidence.environment_match === true ? 'Matches current run' : evidence.environment_match === false ? 'Differs from current run' : 'Not reported'} · Fresh benchmark required</p>
            <details>
              <summary>Historical source hashes and feedback</summary>
              <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ source_hashes: evidence.source_hashes || {}, feedback: evidence.feedback || [] }, null, 2)}</pre>
            </details>
          </li>
        ))}</ul>
      </div>}
      {terminal && (
        <>
          {canSubmit && run.status === 'completed' && <section aria-label="Reevaluate preserved evidence" style={stack}>
            <h5>Reevaluate preserved evidence</h5>
            <p>Apply a versioned policy to this run without executing candidate code. Earlier revisions and measurements remain preserved.</p>
            <label>Reevaluation policy JSON
              <textarea rows={8} spellCheck={false} style={textAreaStyle} value={revisionPolicy} onChange={(event) => setRevisionPolicy(event.target.value)} />
            </label>
            <Button variant="secondary" isLoading={reevaluation.isPending} onClick={() => {
              try {
                const policy = parseEditor(revisionPolicy, 'Reevaluation policy');
                if (!isObject(policy)) throw new Error('Reevaluation policy must be an object.');
                setRevisionError('');
                reevaluation.mutate(policy);
              } catch (error) { setRevisionError(error.message); }
            }}>Reevaluate without execution</Button>
            <ErrorMessage error={revisionError || reevaluation.error} />
            {reevaluation.data && <p role="status">Saved decision revision {reevaluation.data.revision_number}</p>}
          </section>}
          {canReview && (
            <div style={stack}>
              <Input label="Feedback reason" value={reason} onChange={(event) => setReason(event.target.value)} />
              <ErrorMessage error={feedbackError || feedback.error} />
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <Button variant="secondary" isLoading={feedback.isPending} onClick={() => sendFeedback('accepted')}>{run.decision ? 'Accept decision' : 'Accept recommendation'}</Button>
                <Button variant="secondary" isLoading={feedback.isPending} onClick={() => sendFeedback('rejected')}>{run.decision ? 'Reject decision' : 'Reject recommendation'}</Button>
              </div>
              {feedback.data && <p role="status">Feedback saved: {feedback.data.decision} — {feedback.data.reason}</p>}
            </div>
          )}
          {canReview && <div style={stack}>
            <p>Explanation is optional and may use the configured model service to summarize existing facts only. It does not change measurements or rewrite source.</p>
            <Button variant="secondary" isLoading={explanation.isPending} onClick={() => explanation.mutate()}>Request explanation</Button>
            <ErrorMessage error={explanation.error} />
            {explanation.data && (
              <div>
                <p>Explanation status: {explanation.data.status}</p>
                <p style={{ whiteSpace: 'pre-wrap' }}>{explanation.data.explanation || 'No explanation available.'}</p>
                <ErrorMessage error={explanation.data.error} />
                <p>Citations: {(explanation.data.citations || []).join(', ') || 'None'}</p>
              </div>
            )}
          </div>}
        </>
      )}
      <details>
        <summary>Environment and tools</summary>
        <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify({ created_at: run.created_at, source_hashes: run.source_hashes, environment: run.environment, tools: run.tools }, null, 2)}</pre>
      </details>
    </section>
  );
}

export function AlgorithmComparisonPanel() {
  const id = useId();
  const user = useAuthStore((state) => state.user);
  const canSubmit = Boolean(user?.is_admin || engineeringRoles.includes((user?.role ?? user?.organizational_role)?.toUpperCase()));
  const queryClient = useQueryClient();
  const [projectId, setProjectId] = useState('');
  const [historyProject, setHistoryProject] = useState('');
  const [runId, setRunId] = useState('');
  const [language, setLanguage] = useState('python');
  const [mode, setMode] = useState('sorting');
  const generic = mode === 'generic';
  const [functionJson, setFunctionJson] = useState(() => JSON.stringify(sumExample, null, 2));
  const [resourcesJson, setResourcesJson] = useState('');
  const [policyJson, setPolicyJson] = useState('');
  const [candidates, setCandidates] = useState([
    { name: '', source: '', entrypoint: '' }, { name: '', source: '', entrypoint: '' },
  ]);
  const [sizes, setSizes] = useState('0, 1, 100, 1000');
  const [objective, setObjective] = useState('time');
  const [memoryLimit, setMemoryLimit] = useState('');
  const [validationError, setValidationError] = useState('');
  const [inspectionError, setInspectionError] = useState('');
  const inspection = useMutation({ mutationFn: (request) => algorithmsApi.inspectStructure(request) });
  const availability = useQuery({
    queryKey: ['algorithms', 'availability'], queryFn: algorithmsApi.getAvailability, retry: false,
  });
  const history = useQuery({
    queryKey: ['algorithms', 'history', historyProject],
    queryFn: () => algorithmsApi.getHistory(historyProject, 10), enabled: Boolean(historyProject),
  });
  const runQuery = useQuery({
    queryKey: ['algorithms', 'run', runId], queryFn: () => algorithmsApi.getRun(runId), enabled: Boolean(runId),
    retry: false, refetchOnWindowFocus: false,
    refetchInterval: (query) => !query.state.error && activeStatuses.includes(query.state.data?.status) ? 2000 : false,
  });
  const run = runQuery.data;
  useEffect(() => {
    if (run?.status && !activeStatuses.includes(run.status)) {
      queryClient.invalidateQueries({ queryKey: ['algorithms', 'history'] });
    }
  }, [run?.run_id, run?.status, queryClient]);
  const submit = useMutation({
    mutationFn: (request) => algorithmsApi.startRun(request),
    onSuccess: (response, request) => {
      setRunId(response.run_id);
      setHistoryProject(request.project_id);
      queryClient.invalidateQueries({ queryKey: ['algorithms', 'history', request.project_id] });
    },
  });

  const updateCandidate = (index, field, value) => {
    setCandidates((current) => current.map((candidate, position) => position === index ? { ...candidate, [field]: value } : candidate));
  };
  const candidateRequest = (minimum) => {
    const normalizedCandidates = candidates.map((candidate) => ({ ...candidate, name: candidate.name.trim(), entrypoint: candidate.entrypoint.trim() }));
    if (!projectId.trim()) throw new Error('Enter a project ID.');
    if (normalizedCandidates.length < minimum || normalizedCandidates.length > 5) throw new Error(`Provide ${minimum}..5 candidates.`);
    if (normalizedCandidates.some((candidate) => !candidate.name || !candidate.source.trim() || !candidate.entrypoint)) throw new Error(minimum === 2 ? 'Provide a name, source, and entrypoint for both candidates.' : 'Provide a name, source, and entrypoint for every candidate.');
    if (projectId.trim().length > 200) throw new Error('Project ID must be at most 200 characters.');
    if (normalizedCandidates.some((candidate) => candidate.name.length > 200 || candidate.name.includes('\u0000'))) throw new Error('Candidate names must be at most 200 characters and contain no NUL bytes.');
    if (normalizedCandidates.some((candidate) => new TextEncoder().encode(candidate.source).length > 200000)) throw new Error('Candidate source must be at most 200000 UTF-8 bytes.');
    if (normalizedCandidates.some((candidate) => candidate.entrypoint.length > 128 || !(language === 'python' ? /^[A-Za-z_][A-Za-z0-9_]*$/ : /^[A-Za-z_$][A-Za-z0-9_$]*$/).test(candidate.entrypoint) || (language === 'python' && pythonKeywords.has(candidate.entrypoint)))) throw new Error('Entrypoints must be simple function identifiers valid for the selected language, not expressions or Python keywords.');
    if (new Set(normalizedCandidates.map((candidate) => candidate.name)).size !== normalizedCandidates.length) throw new Error('Candidate names must be unique.');
    if (!canSubmit) throw new Error('An engineering role is required to submit benchmarks.');
    return { project_id: projectId.trim(), language, candidates: normalizedCandidates };
  };
  const handleInspect = () => {
    if (inspection.isPending) return;
    try {
      const request = { ...candidateRequest(1), ...resourcePayload(resourcesJson) };
      if (language !== 'python' && (availability.isError || availability.isFetching || !availability.data?.available)) throw new Error('JS/TS structure inspection requires enabled Docker workers. Recheck availability before inspecting.');
      setInspectionError('');
      inspection.mutate(request);
    } catch (validation) {
      setInspectionError(validation.message);
    }
  };
  const handleSubmit = (event) => {
    event.preventDefault();
    if (submit.isPending) return;
    const sizeParts = sizes.split(',').map((part) => part.trim());
    const parsedSizes = sizeParts.map(Number);
    let request;
    try {
      request = candidateRequest(generic ? 1 : 2);
    } catch (validation) {
      setValidationError(validation.message);
      return;
    }
    let error = '';
    if (!generic && (sizeParts.some((part) => !/^\d+$/.test(part)) || parsedSizes.some((size) => !Number.isSafeInteger(size) || size < 0 || size > 10000))) error = 'Sizes must be comma-separated integers in 0..10000.';
    else if (!generic && parsedSizes.length > 16) error = 'Provide at most 16 sizes.';
    else if (!generic && new Set(parsedSizes).size !== parsedSizes.length) error = 'Sizes must be unique.';
    else if (objective === 'memory' && language !== 'python') error = 'Memory objective is supported only for Python.';
    else if (memoryLimit.trim() && (!/^\d+$/.test(memoryLimit.trim()) || !Number.isSafeInteger(Number(memoryLimit)) || Number(memoryLimit) <= 0 || Number(memoryLimit) > 536870912)) error = 'Memory limit must be a positive integer up to 536870912 bytes, or empty.';
    else if (language !== 'python' && memoryLimit.trim()) error = 'Memory limits are supported only for Python tracked allocations.';
    else if (!canSubmit) error = 'An engineering role is required to submit benchmarks.';
    else if (availability.isError || availability.isFetching || !availability.data?.available) error = 'Benchmark worker is unavailable. Recheck availability before submitting.';
    let modePayload = {};
    let resources = {};
    let policy = {};
    if (!error) {
      try {
        modePayload = generic ? genericPayload(functionJson) : { sizes: parsedSizes, distributions };
        resources = resourcePayload(resourcesJson);
        if (policyJson.trim()) {
          const value = parseEditor(policyJson, 'Decision policy');
          if (!isObject(value)) throw new Error('Decision policy must be an object.');
          policy = { decision_policy: value };
        }
      } catch (validation) {
        error = validation.message;
      }
    }
    setValidationError(error);
    if (error) return;
    submit.mutate({
      ...request, ...modePayload, ...resources, ...policy,
      repetitions: 5, seed: 42, objective,
      memory_limit_bytes: memoryLimit.trim() ? Number(memoryLimit) : null,
    });
  };

  return (
    <Card title={generic ? 'Generic function benchmark' : 'Numeric sorting benchmark'} subtitle="Inspect or compare synchronous functions using measured evidence." style={{ marginBottom: '1.75rem' }}>
      <div style={stack}>
        <Select label="Benchmark mode" value={mode} placeholder={null} options={[{ value: 'sorting', label: 'Numeric sorting preset' }, { value: 'generic', label: 'Generic function' }]} onChange={(event) => {
          setMode(event.target.value);
          setValidationError('');
          if (event.target.value === 'sorting' && candidates.length < 2) setCandidates((current) => [...current, { name: '', source: '', entrypoint: '' }]);
        }} />
        {generic ? <>
          <p>Inspect one function or compare up to five using custom data inputs. Only synchronous functions with JSON positional arguments and JSON results are supported; async functions, promises, generators, and non-JSON values are unsupported. Algorithm names are not recognized or used to infer behavior; the contract name and version are your stable semantic identity.</p>
          <p>Edit the sum example below and provide your own source (Python example: def total(values): return sum(values)). Provide 1..32 datasets with id, args (JSON positional arguments), and optional dimensions. input_schema describes the entire args array. Choose output source return, or argument with index 0 (or another positional index) for in-place functions. Python functions must be module-level; JS/TS named functions or CommonJS exports are supported. Dependencies must already exist in the worker image.</p>
          <p>RAG deferred: generic contracts do not automatically retrieve historical evidence. Saved runs offer explicit compatible-history access, without reranking.</p>
          <p>Explicit expected values are optional: use correctness expected with expected on every dataset, or none with no expected values. None produces unverified measurements, excluded from passing-only rankings, with no correctness-backed winner. Schemas and policies are validated by the service.</p>
        </> : <>
        <p>Provide a named synchronous Python, JavaScript, or TypeScript function taking one numeric list/array. Return a numerically ascending list/array with the same values, or sort in-place and return Python None / JavaScript undefined. Sources are sent to the benchmark service; do not include secrets.</p>
        <p>Unsupported contracts: async functions, promises, generators, JavaScript null, sparse or nonnumeric output, custom comparators, and object sorting. Stability is not tested. Python functions must be defined at module level; JS/TS named functions or CommonJS exports are supported. TypeScript export function is transpiled, not semantically type-checked. Dependencies must already exist in the worker image.</p>
        <p>Five repetitions per case; seed 42; random, sorted, reversed, and duplicates distributions. Default sizes cover empty, singleton, small, and larger inputs; choose up to 16 unique sizes in 0..10000. Python memory objective and limit apply to Memray peak tracked allocations, not RSS or total RAM. Node reports signed heap delta, not peak memory; memory objectives and limits are unsupported.</p>
        </>}
        {generic && <p>Five repetitions per dataset; seed 42. Python memory objective and limit use peak tracked allocations, not RSS or total RAM. Node heap delta is not peak memory and does not support memory objectives or tracked allocation limits.</p>}
        <p>Measurements and structural observations do not infer Big-O complexity, asymptotic proof, or optimality.</p>
        <p>Benchmarks are submitted asynchronously and polled for completion. Recommendations and feedback never automatically rewrite or apply source changes; quality and security analysis remain separate.</p>
        {availability.isPending ? <p role="status">Checking benchmark worker...</p> : !availability.isError && availability.data?.available ? <p role="status">Benchmark worker available.</p> : (
          <div role="alert">
            <p>Benchmark worker unavailable: {availability.error?.message || availability.data?.error || 'Worker probe did not confirm availability.'}</p>
            <p>Ask an administrator to start or configure the benchmark worker, then recheck. You can still load project history.</p>
          </div>
        )}
        <Button variant="secondary" isLoading={availability.isFetching} onClick={() => availability.refetch()}>Recheck availability</Button>
        {!canSubmit && <p>An engineering role is required to submit runs and feedback. History remains available.</p>}
        <form onSubmit={handleSubmit} noValidate style={stack} aria-label={generic ? 'Generic function benchmark form' : 'Numeric sorting benchmark form'}>
          <Input label="Benchmark project ID" value={projectId} onChange={(event) => setProjectId(event.target.value)} />
          <div style={grid}>
            <Select label="Benchmark language" value={language} placeholder={null} options={['python', 'javascript', 'typescript']} onChange={(event) => {
              setLanguage(event.target.value);
              if (event.target.value !== 'python') {
                setObjective('time');
                setMemoryLimit('');
              }
            }} />
            <Select label="Benchmark objective" value={objective} placeholder={null} options={language === 'python' ? ['time', 'memory'] : ['time']} onChange={(event) => setObjective(event.target.value)} />
            {!generic && <Input label="Input sizes" value={sizes} onChange={(event) => setSizes(event.target.value)} />}
            <Input label="Memory limit in bytes (optional)" disabled={language !== 'python'} inputMode="numeric" value={memoryLimit} onChange={(event) => setMemoryLimit(event.target.value)} />
          </div>
          {generic && <>
            <label htmlFor={`${id}-function-json`}>Contract and datasets JSON</label>
            <textarea id={`${id}-function-json`} rows={20} spellCheck={false} style={textAreaStyle} value={functionJson} onChange={(event) => setFunctionJson(event.target.value)} />
          </>}
          <label htmlFor={`${id}-resources-json`}>Resources JSON (optional)</label>
          <textarea id={`${id}-resources-json`} rows={3} spellCheck={false} style={textAreaStyle} placeholder={'{"timeout_seconds":30,"memory_bytes":268435456,"cpus":0.5,"pids":32}'} value={resourcesJson} onChange={(event) => setResourcesJson(event.target.value)} />
          <p>Leave empty for service defaults. Container limits: timeout_seconds 1..120; memory_bytes 67108864..536870912 (64..512 MiB); cpus 0.1..1; pids 16..64. These are separate from Python’s tracked allocation limit.</p>
          <label htmlFor={`${id}-policy-json`}>Decision policy JSON (optional)</label>
          <textarea id={`${id}-policy-json`} rows={6} spellCheck={false} style={textAreaStyle} value={policyJson} onChange={(event) => setPolicyJson(event.target.value)}
            placeholder={'{"id":"project-policy","version":"1","objective":"MINIMIZE_TIME","constraints":[],"unknown_requirements":[{"id":"memory-budget","description":"Memory budget not established"}]}'} />
          <p>Leave empty for legacy ranking. An explicit policy gives authoritative dataset decisions; an omitted policy objective means tradeoffs only. Its acceptance thresholds are separate from sandbox resources and the legacy objective above. Project authorization is checked by the server.</p>
          <div style={grid}>{candidates.map((candidate, index) => (
            <fieldset key={index} style={{ ...stack, minWidth: 0, border: '1px solid var(--border-default)', padding: '1rem' }}>
              <legend>Candidate {index + 1}</legend>
              <Button variant="ghost" disabled={candidates.length <= (generic ? 1 : 2)} onClick={() => setCandidates((current) => current.filter((_, position) => position !== index))}>Remove candidate {index + 1}</Button>
              <Input label={`Candidate ${index + 1} name`} value={candidate.name} onChange={(event) => updateCandidate(index, 'name', event.target.value)} />
              <Input label={`Candidate ${index + 1} entrypoint`} value={candidate.entrypoint} onChange={(event) => updateCandidate(index, 'entrypoint', event.target.value)} />
              <label htmlFor={`${id}-source-${index}`}>Candidate {index + 1} source</label>
              <textarea id={`${id}-source-${index}`} rows={10} spellCheck={false} style={textAreaStyle} value={candidate.source} onChange={(event) => updateCandidate(index, 'source', event.target.value)} />
            </fieldset>
          ))}</div>
          <Button variant="secondary" disabled={candidates.length >= 5} onClick={() => setCandidates((current) => [...current, { name: '', source: '', entrypoint: '' }])}>Add candidate</Button>
          <p>Structure inspection requires no contract or datasets and never executes submitted source. Python parses AST on the host, even when benchmark opt-in or Docker is unavailable. JS/TS parsing requires enabled Docker workers. Sources are sent to the service; do not include secrets.</p>
          <ErrorMessage error={inspectionError || inspection.error} />
          <Button variant="secondary" isLoading={inspection.isPending} disabled={!canSubmit || (language !== 'python' && (availability.isError || !availability.data?.available || availability.isFetching))} onClick={handleInspect}>Inspect structure (no execution)</Button>
          <ErrorMessage error={validationError || submit.error} />
          <Button type="submit" isLoading={submit.isPending} disabled={!canSubmit || availability.isError || !availability.data?.available || availability.isFetching}>{generic ? 'Run generic benchmark' : 'Run sorting benchmark'}</Button>
        </form>
        {inspection.data && <section aria-label="Structure-only inspection results" style={stack}>
          <h4>Structure-only inspection results</h4>
          <p>Last submitted inspection: project {inspection.variables.project_id} · Language: {inspection.variables.language}</p>
          <p>Execution performed: {String(inspection.data.execution_performed ?? 'Not reported')}</p>
          <p>Separate from benchmark measurements. No correctness, timing, Big-O, asymptotic proof, or optimality is established.</p>
          {Object.entries(inspection.data.structural_analysis || {}).map(([candidate, report]) => <details key={candidate}>
            <summary>Inspection report for {candidate}</summary>
            <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(report, null, 2)}</pre>
          </details>)}
          <details>
            <summary>Structure inspection environment</summary>
            <pre style={{ whiteSpace: 'pre-wrap', overflowWrap: 'anywhere' }}>{JSON.stringify(inspection.data.environment || {}, null, 2)}</pre>
          </details>
        </section>}
        <section aria-label="Benchmark project history" style={stack}>
          <h4>Project benchmark history</h4>
          <Button variant="secondary" disabled={!projectId.trim()} isLoading={history.isFetching} onClick={() => {
            if (projectId.trim() === historyProject) history.refetch();
            else setHistoryProject(projectId.trim());
          }}>Load project history</Button>
          {historyProject && <p>History for project: {historyProject}</p>}
          <ErrorMessage error={history.error} />
          {history.data?.history?.length === 0 && <p>No benchmark runs found.</p>}
          <ul>{(history.data?.history || []).map((item) => (
            <li key={item.run_id}>
              <Button variant="ghost" onClick={() => setRunId(item.run_id)}>{item.run_id}</Button>
              {' '}· {item.status} · {item.created_at} · {item.decision ? `Decision: ${item.decision.task_suitability.status} · Revision ${item.decision.revision_number}` : `Winner: ${item.recommendation?.winner || 'None'}`}
              {' '}· {!item.decision && (item.recommendation?.reason || item.summary?.reason || '')}
            </li>
          ))}</ul>
        </section>
        {runId && runQuery.isPending && <p role="status">Loading benchmark run...</p>}
        <ErrorMessage error={runQuery.error} />
        {runQuery.error && <Button variant="secondary" onClick={() => runQuery.refetch()}>Retry loading run</Button>}
        {run && <RunDetails key={run.run_id} run={run} canSubmit={canSubmit} onSelectRun={setRunId} />}
      </div>
    </Card>
  );
}
