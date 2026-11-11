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
  const candidate = (name, median, bytes) => ({ candidate: name, datasets: [{ dataset_id: 'graph', eligibility: 'ELIGIBLE',
    timing: { status: 'AVAILABLE', median }, memory: { status: 'AVAILABLE', metric: 'memray_peak_tracked_allocations_bytes', bytes } }] });
  const view = render(<WorkloadDifferences decision={{ candidates: [candidate('previous', 0.2, 100), candidate('current', 0.1, 80)], dataset_comparisons: [{ dataset_id: 'graph' }] }} />);
  expect(screen.getByText(/Median time delta -0.100000 seconds/)).toBeInTheDocument();
  expect(screen.getByText(/Peak tracked allocation delta -20 bytes/)).toBeInTheDocument();
  const bad = candidate('current', 0.1, 80); bad.datasets[0].eligibility = 'UNVERIFIED';
  view.rerender(<WorkloadDifferences decision={{ candidates: [candidate('previous', 0.2, 100), bad], dataset_comparisons: [{ dataset_id: 'graph' }] }} />);
  expect(screen.getByText(/Time difference unverified/)).toBeInTheDocument();
  expect(screen.queryByText(/Peak tracked allocation delta/)).not.toBeInTheDocument();
});
