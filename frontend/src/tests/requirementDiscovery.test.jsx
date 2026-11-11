import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { RequirementsPanel, RequirementsSection } from '../pages/code-quality/RequirementsPanel';
import { algorithmsApi } from '../api/algorithms.api';
import { useAuthStore } from '../store/useAuthStore';

vi.mock('../api/algorithms.api', () => ({ algorithmsApi: {
  discoverRequirements: vi.fn(), getRequirementSources: vi.fn(), proposeRequirementSource: vi.fn(), approveRequirementSource: vi.fn(),
} }));
let client;
const change = (label, value) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
function panel() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><RequirementsPanel /></QueryClientProvider>);
}
beforeEach(() => { vi.resetAllMocks(); useAuthStore.setState({ user: { employee_id: 'author', role: 'DEVELOPER' } }); });
afterEach(() => { cleanup(); client?.clear(); });

it('keeps established requirements, suggestions, observations and unknowns separate', () => {
  render(<RequirementsSection report={{ method: 'requirement-discovery-v1', established: [{ id: 'latency', type: 'MAX_LATENCY', value: 0.1, unit: 'seconds', metric: 'elapsed_invocation_seconds', authority_status: 'AUTHORITATIVE', applicability_status: 'APPLIES', source_revision: 'abc', evidence_refs: ['policy:1'] }],
    observations: [{ id: 'size', type: 'TEST_INPUT', value: 10000 }], suggestions: [{ id: 'intent', value: 'Shortest paths' }], unknown: [{ id: 'memory', description: 'Memory limit unknown' }], conflicts: [] }} />);
  for (const text of ['Established requirements (1)', 'Observed workload characteristics (1)', 'Suggestions needing confirmation (1)', 'Unknown critical requirements (1)', 'Requirement conflicts (0)']) expect(screen.getByText(text)).toBeInTheDocument();
  expect(screen.getByText('policy:1')).toBeInTheDocument();
  expect(screen.getByText(/Source revision: abc/)).toBeInTheDocument();
});

it('discovers project policy without requiring a complete specification', async () => {
  algorithmsApi.discoverRequirements.mockResolvedValue({ unknown: [{ id: 'latency', description: 'Latency unknown' }] });
  panel(); change('Requirements project ID', 'P1'); fireEvent.click(screen.getByRole('button', { name: 'Discover requirements' }));
  await waitFor(() => expect(algorithmsApi.discoverRequirements).toHaveBeenCalledWith({ project_id: 'P1', context: {} }));
  expect(algorithmsApi.approveRequirementSource).not.toHaveBeenCalled();
  expect(await screen.findByText(/Latency unknown/)).toBeInTheDocument();
});

it('rejects malformed optional context before sending a request', () => {
  panel(); change('Requirements project ID', 'P1'); change('Requirement context JSON', 'bad');
  fireEvent.click(screen.getByRole('button', { name: 'Discover requirements' }));
  expect(screen.getByRole('alert')).toHaveTextContent('Provide valid JSON.');
  expect(algorithmsApi.discoverRequirements).not.toHaveBeenCalled();
});

it('requires independent acknowledgement before approving an exact revision', async () => {
  useAuthStore.setState({ user: { employee_id: 'reviewer', role: 'LEAD' } });
  algorithmsApi.getRequirementSources.mockResolvedValue({ sources: [{ source_id: 'RQS-1', status: 'PROPOSED', proposed_by: 'author', payload_fingerprint: 'exact-fp' }] });
  algorithmsApi.approveRequirementSource.mockResolvedValue({ status: 'APPROVED' });
  algorithmsApi.discoverRequirements.mockResolvedValue({});
  panel(); change('Requirements project ID', 'P1'); fireEvent.click(screen.getByRole('button', { name: 'Load requirement sources' }));
  const approve = await screen.findByRole('button', { name: 'Approve requirement source RQS-1' });
  expect(approve).toBeDisabled();
  change('Requirement review source', 'review:1'); change('Requirement review rationale', 'Scope checked'); fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(approve);
  await waitFor(() => expect(algorithmsApi.approveRequirementSource).toHaveBeenCalledWith('RQS-1', { expected_fingerprint: 'exact-fp', source_reference: 'review:1', rationale: 'Scope checked', scope_reviewed: true }));
});

it('shows explicit conflicts without resolving them by source order', () => {
  render(<RequirementsSection report={{ conflicts: [{ reason: 'Sources disagree', evidence_refs: ['source:A', 'source:B'] }] }} />);
  expect(screen.getByText(/Sources disagree/)).toBeInTheDocument();
  expect(screen.getByText('source:A · source:B')).toBeInTheDocument();
});
