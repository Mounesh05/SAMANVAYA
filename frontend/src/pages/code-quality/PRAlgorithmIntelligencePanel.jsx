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

import { AnalysisReport } from '../algorithm-intelligence/AnalysisReport';
import { ComplexitySummary, StaticComparison, TestEvidenceGrouping, WorkloadDifferences, statusLabel, comparisonLabel, modeLabel, categoryLabel, countBy } from '../algorithm-intelligence/ReportSections';
export { ComplexitySummary, StaticComparison, TestEvidenceGrouping, WorkloadDifferences } from '../algorithm-intelligence/ReportSections';

export function PRAlgorithmIntelligencePanel({ prId, source, projectId, compact = false, onReview }) {
  const [selected, setSelected] = useState('');
  const scope = useSessionScope();
  const history = useQuery({ queryKey: ['pr-algorithm-intelligence', scope, prId || projectId || 'accessible-projects'],
    queryFn: () => algorithmsApi.getPRIntelligence(prId ? { pr_id: prId } : projectId ? { project_id: projectId } : {}),
    refetchInterval: source ? false : 5000 });
  const explanation = useMutation({ mutationFn: runId => algorithmsApi.getExplanation(runId) });
  const staticExplanation = useMutation({
    mutationFn: ({ runId, functionId }) => algorithmsApi.explainPRFunction(runId, functionId),
  });
  const runs = (history.error ? [] : history.data?.analyses || []).filter(run => !projectId || run.project_id === projectId).filter((run) => !source || (
    run.project_id === source.projectId && run.head_sha === source.head &&
    run.pr_number === source.number && run.repository?.toLowerCase() === source.repository.toLowerCase()
  ));
  const FunctionContainer = compact ? 'details' : 'article';
  const parentRun = runs.find(run => run.functions?.some(fn => fn.benchmark_run_id === selected));
  const comparison = useQuery({ queryKey: ['algorithms', 'run', selected, scope, parentRun?.project_id],
    queryFn: () => algorithmsApi.getRun(selected), enabled: Boolean(selected && parentRun && !history.isError) });
  return <Card className="cq-panel" title={compact ? 'Pull request analyses' : 'PR algorithm checks'}
    subtitle={source ? 'Static findings and measured comparisons for this PR revision' : 'Static analysis and eligible benchmarks for connected projects'}
    style={{ marginBottom: '1.75rem' }}>
    <p className="cq-note">Results cover tested workloads only. Behaviour without an approved contract is reported as unknown.</p>
    {history.isLoading && <p role="status">Loading PR analysis…</p>}
    {history.error && <p role="alert">{history.error.message}</p>}
    {!history.isLoading && !history.error && !runs.length && <p>{source ? 'No stored analysis matches this PR head.' : 'No automatic PR analyses recorded yet.'}</p>}
    {runs.map(run => {
      if (compact) return <details key={run.run_id} className="ai-disclosure">
        <summary>{run.repository} ? PR #{run.pr_number} ? {statusLabel(run.status)}{run.historical_only && ' ? Historical'}</summary>
        <a href={'/algorithm-intelligence/pr/' + encodeURIComponent(run.run_id) + '?project=' + encodeURIComponent(run.project_id)}>Open report</a>
        <AnalysisReport run={run} refresh={() => history.refetch()} onReview={onReview ? () => onReview(run.project_id) : undefined} />
      </details>;
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
          {fn.requirement_proposal && <p>Requirement draft: {fn.requirement_proposal.status === 'proposed'
            ? 'Awaiting independent review in Requirements' : fn.requirement_proposal.status.replaceAll('_', ' ')}
            {fn.requirement_proposal.contract_id && <> · {fn.requirement_proposal.contract_id}</>}
            {fn.requirement_proposal.reason && <> · {fn.requirement_proposal.reason}</>}
          </p>}
          {fn.previous && fn.mode !== 'C' && <p>Previous: {fn.previous.qualified_name} · Current: {fn.current?.qualified_name}</p>}
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
    {comparison.data && parentRun && comparison.data.run_id === selected && (!comparison.data.project_id || comparison.data.project_id === parentRun.project_id) && !comparison.error && !history.error && <section aria-label={comparison.data.kind === 'pr_standalone' ? 'Standalone benchmark details' : 'Automatic comparison details'}>
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
