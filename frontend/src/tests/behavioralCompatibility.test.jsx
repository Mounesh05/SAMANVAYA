import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { BehavioralCompatibilityPanel } from '../pages/code-quality/BehavioralCompatibilityPanel';
import { BehavioralCompatibilitySection } from '../pages/code-quality/BehavioralCompatibilitySection';
import { algorithmsApi } from '../api/algorithms.api';
import { useAuthStore } from '../store/useAuthStore';

vi.mock('../api/algorithms.api', () => ({ algorithmsApi: {
  proposeContract: vi.fn(), getContracts: vi.fn(), approveContract: vi.fn(), startCompatibility: vi.fn(),
  getRun: vi.fn(), getRelationships: vi.fn(),
} }));
let client;
function panel() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><BehavioralCompatibilityPanel /></QueryClientProvider>);
}
beforeEach(() => { vi.resetAllMocks(); useAuthStore.setState({ user: { role: 'DEVELOPER', employee_id: 'author' } }); });
afterEach(() => { cleanup(); client?.clear(); });
function change(label, value) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }

it('does not infer approval or execute simply by opening the panel', () => {
  panel();
  expect(algorithmsApi.startCompatibility).not.toHaveBeenCalled();
  expect(algorithmsApi.proposeContract).not.toHaveBeenCalled();
  expect(algorithmsApi.approveContract).not.toHaveBeenCalled();
  expect(screen.getByText(/Names, signatures, algorithm families/)).toBeInTheDocument();
});

it('submits explicit previous/current implementations and approved contract references', async () => {
  algorithmsApi.startCompatibility.mockResolvedValue({ run_id: 'compare', status: 'completed' });
  algorithmsApi.getRun.mockResolvedValue({ status: 'completed' });
  panel();
  change('Compatibility project ID', 'P1');
  change('Approved contract IDs (comma separated)', 'FCT-one');
  change('Previous entrypoint', 'solve'); change('Current entrypoint', 'solve');
  change('Previous source', 'def solve(x): return x'); change('Current source', 'function solve(x) { return x; }');
  change('Current language', 'javascript');
  fireEvent.submit(screen.getByRole('form', { name: 'Behavioral compatibility form' }));
  await waitFor(() => expect(algorithmsApi.startCompatibility).toHaveBeenCalledWith({
    project_id: 'P1', contract_ids: ['FCT-one'],
    previous: { name: 'previous', language: 'python', entrypoint: 'solve', source: 'def solve(x): return x' },
    current: { name: 'current', language: 'javascript', entrypoint: 'solve', source: 'function solve(x) { return x; }' },
  }));
});

it('shows proposals separately and never approves them automatically', async () => {
  algorithmsApi.proposeContract.mockResolvedValue({ contract_id: 'FCT-new', status: 'PROPOSED', payload_fingerprint: 'fp' });
  panel();
  change('Compatibility project ID', 'P1'); change('Functional contract proposal JSON', '{"scope_description":"finite reviewed scope"}');
  fireEvent.click(screen.getByRole('button', { name: 'Propose contract' }));
  expect(await screen.findByRole('status')).toHaveTextContent('PROPOSED');
  expect(algorithmsApi.approveContract).not.toHaveBeenCalled();
});

it('requires independent reviewer acknowledgement and exact fingerprint', async () => {
  useAuthStore.setState({ user: { role: 'LEAD', employee_id: 'reviewer' } });
  algorithmsApi.getContracts.mockResolvedValue({ contracts: [{ contract_id: 'FCT-1', proposed_by: 'author', status: 'PROPOSED', payload_fingerprint: 'exact-fingerprint', contract: { name: 'reachability', version: '1' } }] });
  algorithmsApi.approveContract.mockResolvedValue({ contract_id: 'FCT-1', status: 'APPROVED' });
  panel(); change('Compatibility project ID', 'P1');
  fireEvent.click(screen.getByRole('button', { name: 'Load project contracts' }));
  const approve = await screen.findByRole('button', { name: 'Approve reviewed contract FCT-1' });
  expect(approve).toBeDisabled();
  change('Contract review source reference', 'spec:review'); change('Contract review rationale', 'Scope checked');
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(approve);
  await waitFor(() => expect(algorithmsApi.approveContract).toHaveBeenCalledWith('FCT-1', {
    expected_fingerprint: 'exact-fingerprint', source_reference: 'spec:review', rationale: 'Scope checked', scope_reviewed: true,
  }));
});

it.each(['INCOMPATIBLE', 'UNVERIFIED', 'CONTRACT_MISSING'])('blocks replacement claims for %s', status => {
  render(<BehavioralCompatibilitySection report={{ status, previous: { name: 'before', language: 'python' }, current: { name: 'after', language: 'typescript' }, phase1_eligible: false,
    checks: [{ candidate: 'after', dataset_id: 'required-path', status: status === 'INCOMPATIBLE' ? 'FAIL' : 'UNVERIFIED', evidence_reference: 'run/results/after/required-path' }],
    unverified_behavior: ['Required validation missing.'] }} />);
  expect(screen.getByRole('heading', { name: `Behavioral compatibility: ${status}` })).toBeInTheDocument();
  expect(screen.getByText(/Blocked; no verified replacement or superiority claim/)).toBeInTheDocument();
  expect(screen.getByText(/run\/results\/after\/required-path/)).toBeInTheDocument();
});

it('limits compatibility claims to tested scope', () => {
  render(<BehavioralCompatibilitySection report={{ status: 'COMPATIBLE_WITHIN_TESTED_CONTRACT', phase1_eligible: true,
    limitations: ['Finite approved validation scope only; no universal equivalence.'] }} />);
  expect(screen.getByText(/measurement prerequisites still apply/)).toBeInTheDocument();
  expect(screen.getByText(/no universal equivalence/)).toBeInTheDocument();
});
