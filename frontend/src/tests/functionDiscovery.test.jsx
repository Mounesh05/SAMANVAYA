import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DiscoveredFunctions } from '../pages/code-quality/DiscoveredFunctions';
import { codeQualityApi } from '../api/codeQuality.api';

vi.mock('../api/codeQuality.api', () => ({ codeQualityApi: { getDiscoveredFunctions: vi.fn() } }));
let client;
function show(props = {}) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><DiscoveredFunctions runId="run-1" {...props} /></QueryClientProvider>);
}
beforeEach(() => vi.resetAllMocks());
afterEach(() => { cleanup(); client?.clear(); });

it('shows inferred tasks separately from observations and authoritative requirements', async () => {
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({
    status: 'available', method: 'function-purpose-v1', source_revision: 'head-sha', total: 1, returned: 1,
    limitations: ['No execution or equivalence claim.'], functions: [{
      function_id: 'f-1', qualified_name: 'explore', language: 'python', path: 'graph.py', line: 2,
      task_status: 'INFERRED', possible_task: 'graph_reachability', verified_contract: null,
      detected_patterns: [{ kind: 'fifo_graph_traversal' }],
      task_hypotheses: [{ kind: 'graph_reachability', status: 'INFERRED', evidence_refs: ['e-1'], supported_conclusion: 'Returns the tracked node set.', missing_information: ['Untested inputs unknown.'] }],
      evidence: [{ id: 'e-1', kind: 'return_value', status: 'OBSERVED', path: 'graph.py', line: 11 }],
      uncertainty: ['No authoritative contract is established.'],
    }],
  });
  show();
  expect(await screen.findByText(/graph.py:2/)).toHaveTextContent('INFERRED');
  expect(screen.getByText('Verified contract: None established')).toBeInTheDocument();
  expect(screen.getByText('fifo_graph_traversal (INFERRED)')).toBeInTheDocument();
  expect(screen.getByText(/No benchmarks are started here/)).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: /benchmark|equivalent/i })).not.toBeInTheDocument();
});

it('keeps unfamiliar functions visible with unknown purpose', async () => {
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'available', total: 1, returned: 1, functions: [{
    function_id: 'custom', qualified_name: 'custom_transform', language: 'typescript', path: 'custom.ts', line: 1,
    task_status: 'UNKNOWN', possible_task: null, detected_patterns: [], task_hypotheses: [], evidence: [], uncertainty: [],
  }] });
  show();
  expect(await screen.findByText(/custom_transform/)).toBeInTheDocument();
  expect(screen.getByText(/No recognized pattern; structural metadata remains available/)).toBeInTheDocument();
  expect(screen.getByText(/custom.ts:1/)).toHaveTextContent('UNKNOWN');
});

it('loads paginated persisted evidence', async () => {
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'available', functions: [], total: 51, returned: 50 });
  show();
  await waitFor(() => expect(screen.getByRole('button', { name: 'Next functions' })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: 'Next functions' }));
  await waitFor(() => expect(codeQualityApi.getDiscoveredFunctions).toHaveBeenLastCalledWith('run-1', { skip: 50, limit: 50 }));
});

it('does not request unfinished analysis', () => {
  show({ pending: true });
  expect(screen.getByText('Available when analysis finishes.')).toBeInTheDocument();
  expect(codeQualityApi.getDiscoveredFunctions).not.toHaveBeenCalled();
});

it('distinguishes legacy runs without discovery evidence', async () => {
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'not_analyzed', functions: [] });
  show();
  expect(await screen.findByText(/This run has no purpose-discovery snapshot/)).toBeInTheDocument();
});

it('shows retrieval failure without inventing results', async () => {
  codeQualityApi.getDiscoveredFunctions.mockRejectedValue(new Error('Access denied'));
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Access denied');
  expect(screen.queryByText('Verified contract: Recorded')).not.toBeInTheDocument();
});
