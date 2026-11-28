import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { Select } from '../../components/common/Select';
import { algorithmsApi } from '../../api/algorithms.api';
import { useSessionScope } from '../../store/useSessionScope';
import { ComplexitySummary, StaticComparison, TestEvidenceGrouping } from './ReportSections';
import { DecisionResults } from '../code-quality/DecisionResults';
import { AlgorithmAdvisory } from './AlgorithmAdvisory';

const sections = ['Overview', 'Complexity', 'Benchmarks', 'Validation & constraints', 'AI', 'Evidence'];
const human = value => typeof value === 'string' ? value.replaceAll('_', ' ') : 'Not recorded';

export function EmpiricalGrowth({ report }) {
  if (!report) return null;
  return <section><h4>Observed growth</h4>
    {report.candidates?.length ? report.candidates.map(c => <div key={c.candidate} className="ai-list-row">
      <div><strong>{c.candidate}</strong><p>{c.model || human(c.status)}{c.dimension && ' · ' + c.dimension}</p>
        {c.reason && <p>{c.reason}</p>}
        {c.held_out_sizes?.length > 0 && <p>Held-out sizes {c.held_out_sizes.join(', ')}</p>}
      </div></div>) : <p>{human(report.status)}</p>}
  </section>;
}

export function AnalysisReport({ run, refresh, onReview, kind = 'pr' }) {
  const scope = useSessionScope();
  const [section, setSection] = useState('Overview');
  const [search, setSearch] = useState('');
  const [selection, setSelection] = useState('');
  const rows = (run.functions || []).filter(row => [row.current?.qualified_name, row.current?.path, row.current?.language, row.status]
    .some(v => String(v || '').toLowerCase().includes(search.trim().toLowerCase())));
  const row = rows.find(item => item.current?.function_id === selection) || rows[0];
  const fn = row?.current;
  const childId = row?.benchmark_run_id;
  const child = useQuery({ queryKey: ['algorithms', 'run', childId, scope, run.project_id],
    queryFn: () => algorithmsApi.getRun(childId), enabled: Boolean(childId && ['Benchmarks', 'Validation & constraints'].includes(section)), retry: false });
  const measured = !child.isError && child.data?.run_id === childId && child.data?.project_id === run.project_id ? child.data : null;
  const observed = fn?.detected_patterns?.map(p => human(p.kind)) || [];
  return <section className="ai-stack" aria-label="Algorithm analysis report">
    <div className="ai-list-row"><div><strong>{run.repository || run.repository_id || run.project_id}{run.pr_number && ' · PR #' + run.pr_number}</strong>
      <p>{run.head_sha?.slice(0, 12) || run.commit_sha?.slice(0, 12)} · {human(run.status)}{run.historical_only && ' · Historical'}</p>
    </div>{refresh && <Button variant="outline" size="sm" onClick={refresh}>Refresh report</Button>}</div>
    {(run.analysis_truncated || run.input_truncated) && <p role="status">Partial source coverage. Some functions or files were omitted.</p>}
    {(run.reason || run.error) && <p role="status">{run.reason || run.error}</p>}
    <nav aria-label="Report sections" className="ai-section-nav">{sections.map(s => <Button key={s} size="sm" variant={s === section ? 'primary' : 'ghost'}
      aria-pressed={s === section} onClick={() => setSection(s)}>{s}</Button>)}</nav>
    {section === 'AI' ? <AlgorithmAdvisory run={run} kind={kind} refresh={refresh} /> : <>
      {run.functions?.length > 0 && <div className="ai-fields">
        <Input label="Find function" type="search" value={search} onChange={e => setSearch(e.target.value)} />
        <Select label="Function" value={fn?.function_id || ''} placeholder={rows.length ? null : 'No matches'}
          options={rows.map(r => ({ value: r.current?.function_id, label: [r.current?.qualified_name, r.current?.path].filter(Boolean).join(' · ') }))}
          onChange={e => setSelection(e.target.value)} /></div>}
      {!row && <p>{search ? 'No functions match this search.' : 'No supported function evidence was recorded.'}</p>}
      {row && section === 'Overview' && <div className="ai-review">
        <h4>{fn?.qualified_name}</h4><p>{observed.join(', ') || 'Unclassified computational pattern'}</p>
        <dl><dt>Language</dt><dd>{human(fn?.language)}</dd><dt>Assessment</dt><dd>{({ A: 'Standalone', B: 'Revision comparison', C: 'Same-revision alternatives' })[row.mode] || 'Static analysis'}</dd>
          <dt>Static time / space</dt><dd>{row.complexity?.time_complexity || 'Unknown'} / {row.complexity?.space_complexity || 'Unknown'}</dd>
          <dt>Benchmark</dt><dd>{human(row.benchmark_status || row.comparison_status)}</dd><dt>Validation</dt><dd>{human(row.compatibility || row.finding_status)}</dd></dl>
        {(row.benchmark_reason || row.reason) && <p>{row.benchmark_reason || row.reason}</p>}</div>}
      {row && section === 'Complexity' && <>{row.complexity ? <ComplexitySummary complexity={row.complexity} /> : <p>Static complexity was not established.</p>}
        {row.previous && <div className="ai-table-wrap"><StaticComparison row={row} /></div>}</>}
      {row && section === 'Benchmarks' && <><h4>Measured workloads</h4>
        {measured ? <><div className="ai-table-wrap"><table><thead><tr><th>Implementation</th><th>Case</th><th>Correctness</th><th>Invocation samples (s)</th></tr></thead>
          <tbody>{(measured.results || []).flatMap(result => (result.cases || []).map((c,i) => <tr key={result.candidate + ':' + i}>
            <td>{result.candidate}</td><td>{c.case_id || c.dataset_id || c.size || (i + 1)}</td><td>{c.correct === true ? 'Passed' : c.correct === false ? 'Failed' : 'Unverified'}</td>
            <td>{c.timings_seconds?.length ? c.timings_seconds.map(t => t.toPrecision(3)).join(', ') : 'Unavailable'}</td></tr>))}</tbody></table></div>
          <EmpiricalGrowth report={measured.empirical_growth} /></> : <p>{childId ? (child.isError ? 'Benchmark evidence could not be loaded.' : child.isFetching ? 'Loading benchmark…' : 'Benchmark evidence unavailable.') : (row.benchmark_reason || row.reason || 'No measured workload was recorded.')}</p>}</>}
      {row && section === 'Validation & constraints' && <><h4>{row.contract_id || 'No approved applicable contract'}</h4><p>{human(row.compatibility || row.finding_status)}</p>
        {row.requirement_proposal && <p>Requirement draft · {human(row.requirement_proposal.review_status || row.requirement_proposal.status)}</p>}
        {measured?.decision && <DecisionResults decision={measured.decision} revisions={measured.decision_revisions} />}
        {child.isError && <p role="alert">Validation evidence could not be loaded.</p>}
        {row.reason && <p>{row.reason}</p>}{onReview && <Button variant="outline" onClick={onReview}>Review requirements</Button>}</>}
      {section === 'Evidence' && <div className="ai-stack"><p>Run {run.run_id}</p><p>Source revision {run.head_sha || run.commit_sha || 'Unavailable'}</p>
        {fn && <p>{fn.path}{fn.line ? ' · Lines ' + fn.line + '–' + (fn.end_line || fn.line) : ''}</p>}
        {row && <TestEvidenceGrouping evidence={row.static?.test_expectations} />}
        {row?.evidence_refs?.length > 0 && <details className="ai-disclosure"><summary>Evidence references</summary><ul>{row.evidence_refs.map(ref => <li key={ref}>{ref}</li>)}</ul></details>}
        {run.limitations?.length > 0 && <details className="ai-disclosure"><summary>Limitations</summary><ul>{run.limitations.map(x => <li key={x}>{x}</li>)}</ul></details>}
      </div>}
    </>}
  </section>;
}
