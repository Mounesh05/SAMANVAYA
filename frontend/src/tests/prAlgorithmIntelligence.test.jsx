import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PRAlgorithmIntelligencePanel, WorkloadDifferences } from '../pages/code-quality/PRAlgorithmIntelligencePanel';
import { algorithmsApi } from '../api/algorithms.api';

vi.mock('../api/algorithms.api', () => ({ algorithmsApi: { getPRIntelligence: vi.fn(), getRun: vi.fn(), getExplanation: vi.fn() } }));
let client;
function panel(prId) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><PRAlgorithmIntelligencePanel prId={prId} /></QueryClientProvider>);
}
beforeEach(() => { vi.resetAllMocks(); });
afterEach(() => { cleanup(); client?.clear(); });

it('loads authorized connected project findings without a project ID field', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [] }); panel();
  await screen.findByText(/No automatic PR analyses recorded/);
  expect(algorithmsApi.getPRIntelligence).toHaveBeenCalledWith({});
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  expect(algorithmsApi.getRun).not.toHaveBeenCalled();
});

it('scopes a PR view using its existing identity', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [] }); panel('PR1');
  await waitFor(() => expect(algorithmsApi.getPRIntelligence).toHaveBeenCalledWith({ pr_id: 'PR1' }));
});

it.each(['pending', 'analyzing', 'benchmarking', 'completed', 'insufficient_evidence', 'unsupported', 'failed'])('reports %s honestly', async status => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', repository: 'o/r', pr_number: 7, status,
    head_sha: 'head', base_sha: 'base', functions: [], reason: 'Bounded analysis scope' }] }); panel();
  expect(await screen.findByText(/o\/r PR #7/)).toBeInTheDocument();
  expect(screen.getByText('Bounded analysis scope')).toBeInTheDocument();
});

it('marks superseded revisions as historical and retains missing-contract evidence', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'old', repository: 'o/r', pr_number: 7, status: 'superseded', historical_only: true,
    functions: [{ current: { function_id: 'f1', path: 'module.py', qualified_name: 'explore', task_hypotheses: [{ kind: 'graph_reachability', status: 'INFERRED' }] },
      status: 'insufficient_evidence', reason: 'Approved functional contract missing', evidence_refs: ['base-ref', 'head-ref'] }] }] }); panel();
  expect(await screen.findByText(/Historical only/)).toBeInTheDocument();
  expect(screen.getByText(/graph_reachability \(INFERRED\)/)).toBeInTheDocument();
  expect(screen.getByText(/Approved functional contract missing/)).toBeInTheDocument();
});

it('loads isolated comparison evidence only when the developer inspects a result', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [{ current: { function_id: 'f1', qualified_name: 'solve' }, benchmark_run_id: 'ALG1' }] }] });
  algorithmsApi.getRun.mockResolvedValue({ run_id: 'ALG1', results: [], environment: {} }); panel();
  const button = await screen.findByRole('button', { name: 'Inspect comparison solve' });
  expect(algorithmsApi.getRun).not.toHaveBeenCalled(); fireEvent.click(button);
  expect(await screen.findByRole('region', { name: 'Automatic comparison details' })).toBeInTheDocument();
  expect(algorithmsApi.getRun).toHaveBeenCalledWith('ALG1');
});

it('shows measured deltas only with eligible comparable metrics', () => {
  const candidate = (name, median, bytes) => ({ candidate: name, methodology_fingerprint: 'same-runtime', datasets: [{ dataset_id: 'graph', eligibility: 'ELIGIBLE',
    timing: { status: 'AVAILABLE', median }, memory: { status: 'AVAILABLE', metric: 'memray_peak_tracked_allocations_bytes', bytes } }] });
  const view = render(<WorkloadDifferences decision={{ candidates: [candidate('previous', 0.2, 100), candidate('current', 0.1, 80)], dataset_comparisons: [{ dataset_id: 'graph', status: 'ELIGIBLE_WINNER' }] }} />);
  expect(screen.getByText(/Median time delta -0.100000 seconds/)).toBeInTheDocument();
  expect(screen.getByText(/Peak tracked allocation delta -20 bytes/)).toBeInTheDocument();
  const bad = candidate('current', 0.1, 80); bad.datasets[0].eligibility = 'UNVERIFIED';
  view.rerender(<WorkloadDifferences decision={{ candidates: [candidate('previous', 0.2, 100), bad], dataset_comparisons: [{ dataset_id: 'graph', status: 'INSUFFICIENT_EVIDENCE' }] }} />);
  expect(screen.getByText(/Time difference unverified/)).toBeInTheDocument();
  expect(screen.queryByText(/Peak tracked allocation delta/)).not.toBeInTheDocument();
});

it('does not compute deltas when the decision reports incomparable methodologies', () => {
  const candidate = name => ({ candidate: name, datasets: [{ dataset_id: 'graph', eligibility: 'ELIGIBLE', timing: { status: 'AVAILABLE', median: name === 'previous' ? 1 : 0.5 },
    memory: { status: 'AVAILABLE', metric: 'memray_peak_tracked_allocations_bytes', bytes: 100 } }] });
  render(<WorkloadDifferences decision={{ candidates: [candidate('previous'), candidate('current')], dataset_comparisons: [{ dataset_id: 'graph', status: 'INCOMPARABLE_IMPLEMENTATIONS' }] }} />);
  expect(screen.getByText(/Time difference unverified/)).toBeInTheDocument();
  expect(screen.queryByText(/Peak tracked allocation delta/)).not.toBeInTheDocument();
});

it('provides working navigation from a PR function to its existing discovery snapshots', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI', base_discovery_run_id: 'PRI-base', head_discovery_run_id: 'PRI-head',
    functions: [{ current: { function_id: 'f1', qualified_name: 'solve' }, previous: { function_id: 'f0', qualified_name: 'solve' } }] }] });
  panel('PR1');
  expect(await screen.findByRole('link', { name: 'Inspect current function evidence' })).toHaveAttribute('href', '/code-quality/runs/PRI-head');
  expect(screen.getByRole('link', { name: 'Inspect previous function evidence' })).toHaveAttribute('href', '/code-quality/runs/PRI-base');
});

it('does not display cached successful findings after project access is refused', async () => {
  algorithmsApi.getPRIntelligence.mockRejectedValue(new Error('Project access denied'));
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['pr-algorithm-intelligence', 'PR1'], { analyses: [{ run_id: 'old', repository: 'private/repo', pr_number: 7, functions: [] }] });
  render(<QueryClientProvider client={client}><PRAlgorithmIntelligencePanel prId="PR1" /></QueryClientProvider>);
  expect(await screen.findByRole('alert')).toHaveTextContent('Project access denied');
  expect(screen.queryByText(/private\/repo PR #7/)).not.toBeInTheDocument();
});

it('does not show a cached comparison after its evidence request is refused', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI', functions: [{ current: { function_id: 'f1', qualified_name: 'solve' }, benchmark_run_id: 'ALG1' }] }] });
  algorithmsApi.getRun.mockRejectedValue(new Error('Benchmark access denied'));
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(['algorithms', 'run', 'ALG1'], { run_id: 'ALG1', results: [] });
  render(<QueryClientProvider client={client}><PRAlgorithmIntelligencePanel prId="PR1" /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: 'Inspect comparison solve' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('Benchmark access denied');
  expect(screen.queryByRole('region', { name: 'Automatic comparison details' })).not.toBeInTheDocument();
});

it('does not compare tradeoff-only measurements from different runtimes', () => {
  const candidate = (name, method) => ({ candidate: name, methodology_fingerprint: method, datasets: [{ dataset_id: 'graph', eligibility: 'ELIGIBLE',
    timing: { status: 'AVAILABLE', median: 1 }, memory: { status: 'UNAVAILABLE' } }] });
  render(<WorkloadDifferences decision={{ candidates: [candidate('previous', 'python-runtime'), candidate('current', 'node-runtime')],
    dataset_comparisons: [{ dataset_id: 'graph', status: 'MULTIPLE_ELIGIBLE' }] }} />);
  expect(screen.getByText(/Time difference unverified/)).toBeInTheDocument();
});

const analysedRow = overrides => ({
  current: { function_id: 'f1', path: 'backend/app/algorithms.py', qualified_name: 'bfs_dependencies',
    task_hypotheses: [{ kind: 'graph_traversal', status: 'INFERRED' }],
    detected_patterns: [{ kind: 'fifo_graph_traversal' }] },
  previous: null, mode: 'A', status: 'analyzed', comparison_status: 'not_applicable', static_status: 'analyzed',
  classification: { category: 'application', attribution: null },
  static: { status: 'analyzed', patterns: ['fifo_graph_traversal'], test_expectations: [
    { path: 'backend/tests/test_algorithms.py', line: 21, detail: 'Static assert references this call.' },
    { path: 'backend/tests/test_algorithms.py', line: 34, detail: 'Static assert references this call.' }] },
  complexity: { status: 'estimated', confidence: 'medium', time_complexity: 'O(V + E)', space_complexity: 'O(V)',
    dimension_bindings: { V: 'distinct elements', E: 'adjacency entries' },
    derivation: ['A membership guard precedes insertion into the tracked set.'],
    assumptions: [], limitations: ['Static syntax-derived bound: it is not a measurement.'] },
  evidence_refs: ['head-ref'], ...overrides });

it('reports mode, classification and an explicit static bound for every analysed function', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow()],
    comparison_modes: { A: 1 } }] }); panel();
  expect(await screen.findByText(/Comparison modes: Mode A · standalone — 1/)).toBeInTheDocument();
  expect(screen.getByText(/Classification: Application/)).toBeInTheDocument();
  expect(screen.getByText(/Comparison: Not applicable — no predecessor/)).toBeInTheDocument();
  expect(screen.getByText(/time O\(V \+ E\) · space O\(V\)/)).toBeInTheDocument();
  expect(screen.getByText(/Dimensions: V = distinct elements, E = adjacency entries/)).toBeInTheDocument();
  expect(screen.getAllByText(/Mode A · standalone/).length).toBeGreaterThan(0);
});

it('states plainly when no bound could be established instead of showing an empty value', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow({
    complexity: { status: 'unknown', confidence: 'none', time_complexity: null, space_complexity: null,
      time_complexity_reason: 'while-loop trip count over frontier depends on runtime mutation',
      unknown_reasons: ['while-loop trip count over frontier depends on runtime mutation'],
      assumptions: [], limitations: ['Static syntax-derived bound: it is not a measurement.'] } })] }] }); panel();
  expect(await screen.findByText(/time unavailable · space unavailable/)).toBeInTheDocument();
  expect(screen.getByText(/No time bound established: while-loop trip count over frontier depends on runtime mutation/)).toBeInTheDocument();
});

it('groups static test evidence by asserting file rather than merging it into a count', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow()] }] }); panel();
  fireEvent.click(await screen.findByText(/Static test evidence \(2 assertion references\)/));
  expect(await screen.findByText(/backend\/tests\/test_algorithms\.py: line 21, line 34/)).toBeInTheDocument();
  expect(screen.getAllByText('Static assert references this call.')).toHaveLength(2);
});

it('shows previous and current findings side by side when a predecessor exists', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow({
    mode: 'B', status: 'insufficient_evidence', comparison_status: 'blocked',
    previous: { function_id: 'f0', qualified_name: 'bfs_dependencies' },
    static_previous: { status: 'analyzed', classification: { category: 'application' },
      patterns: ['visited_set_tracking'],
      complexity: { status: 'estimated', time_complexity: 'O(n m)', space_complexity: 'O(n)' } } })] }] }); panel();
  expect(await screen.findByRole('table')).toBeInTheDocument();
  expect(screen.getByText('O(n m)')).toBeInTheDocument();
  expect(screen.getByText('O(V + E)')).toBeInTheDocument();
  expect(screen.getByText('visited_set_tracking')).toBeInTheDocument();
  expect(screen.getByText(/Previous-revision complexity/)).toBeInTheDocument();
});

it('says so when a predecessor exists but its own static analysis is missing', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow({
    previous: { function_id: 'f0', qualified_name: 'bfs_dependencies' }, static_previous: undefined })] }] }); panel();
  expect(await screen.findByText(/Previous-revision static analysis is unavailable; only the current revision was analysed\./)).toBeInTheDocument();
});

it('distinguishes an analysis with no comparable predecessor from an unsupported run', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', status: 'completed', functions: [analysedRow()] }] }); panel();
  expect(await screen.findByText(/Completed/)).toBeInTheDocument();
  expect(screen.getByText(/Analysed \(static only\)/)).toBeInTheDocument();
  expect(screen.getByText(/Static analysis: 1 of 1 functions analysed/)).toBeInTheDocument();
  expect(screen.queryByText(/Unsupported/)).not.toBeInTheDocument();
});


it('does not render an artificial comparison table for a standalone algorithm', async () => {
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [{ run_id: 'PRI1', functions: [analysedRow()] }] });
  panel();
  expect(await screen.findByText(/time O\(V \+ E\) · space O\(V\)/)).toBeInTheDocument();
  expect(screen.queryByRole('table')).not.toBeInTheDocument();
  expect(screen.queryByText(/Previous: Unavailable/)).not.toBeInTheDocument();
  expect(screen.queryByText(/No replacement conclusion/)).not.toBeInTheDocument();
});

it('does not show measured comparison for a standalone candidate', () => {
  render(<WorkloadDifferences decision={{ candidates: [{ candidate: 'current' }], dataset_comparisons: [{ dataset_id: 'one' }] }} />);
  expect(screen.queryByRole('region', { name: 'Measured workload differences' })).not.toBeInTheDocument();
});
