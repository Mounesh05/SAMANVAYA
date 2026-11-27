import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { withPermissions } from './utils/roleUser';
import { useAuthStore } from '../store/useAuthStore';
import { AlgorithmIntelligencePage } from '../pages/algorithm-intelligence/AlgorithmIntelligencePage';
import { algorithmsApi } from '../api/algorithms.api';
import { projectsApi } from '../api/projects.api';

vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../api/algorithms.api', () => ({ algorithmsApi: {
  getPRIntelligence: vi.fn(), getAvailability: vi.fn(), getContracts: vi.fn(), getRequirementSources: vi.fn(),
  getHistory: vi.fn(), getRun: vi.fn(), approveContract: vi.fn(), approveRequirementSource: vi.fn(),
} }));
let client;
function mount() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><AlgorithmIntelligencePage /></QueryClientProvider>);
}
const contract = { project_id: 'p1', contract_id: 'c1', payload_fingerprint: 'exact-fingerprint',
  status: 'PROPOSED', proposed_by: 'different-author', contract: { name: 'Scheduling', version: '1' },
  scope_description: 'Approved fixture scope', requirements: [{ id: 'r1', description: 'Preserve equal priority order' }],
  datasets: [{ id: 'd1', args: [[]], expected: [] }], required_dataset_ids: ['d1'] };
beforeEach(() => {
  vi.resetAllMocks();
  useAuthStore.setState({user: withPermissions({role:'LEAD', employee_id:'reviewer', org_id:'org', permissions:['USE_ENGINEERING_INTELLIGENCE','APPROVE_ENGINEERING_CONTRACTS','VIEW_CODE_QUALITY']})});
  projectsApi.list.mockResolvedValue([{ id:'p1', name:'TaskFlow' }]);
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [] });
  algorithmsApi.getAvailability.mockResolvedValue({ available: true });
  algorithmsApi.getContracts.mockResolvedValue({ contracts: [contract] });
  algorithmsApi.getRequirementSources.mockResolvedValue({ sources: [] });
  algorithmsApi.getHistory.mockResolvedValue({ history: [] });
  algorithmsApi.approveContract.mockResolvedValue({ ...contract, status: 'APPROVED' });
});
afterEach(() => {cleanup(); client?.clear(); useAuthStore.setState({user:null});});
async function choose(section) {
  fireEvent.click(screen.getByRole('button', { name:section }));
  await screen.findByRole('option', {name:'TaskFlow'});
  fireEvent.change(screen.getByLabelText('Project'), {target:{value:'p1'}});
}
it('opens a clean analyses workspace without loading advanced experiment or review panels', async () => {
  mount();
  await screen.findByText(/No automatic PR analyses/);
  expect(screen.queryByText('Advanced tools')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Benchmark mode')).not.toBeInTheDocument();
  expect(algorithmsApi.getContracts).not.toHaveBeenCalled();
  expect(algorithmsApi.getAvailability).not.toHaveBeenCalled();
});
it('starts experiments with one blank generic function and a selected project', async () => {
  mount(); await choose('Experiments');
  await screen.findByText('Benchmark worker available.');
  expect(screen.getByLabelText('Benchmark mode')).toHaveValue('generic');
  expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('');
  expect(screen.queryByLabelText('Candidate 2 source')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('Benchmark project ID')).not.toBeInTheDocument();
  expect(screen.getByLabelText('Contract and datasets JSON')).toHaveValue('');
});
it('requires explicit independent review and sends the exact stored fingerprint', async () => {
  mount(); await choose('Requirements');
  fireEvent.click(await screen.findByRole('button',{name:'Review'}));
  const approve = screen.getByRole('button',{name:'Approve reviewed contract'});
  expect(approve).toBeDisabled();
  fireEvent.change(screen.getByLabelText('Independent review reference'),{target:{value:'review/1'}});
  fireEvent.change(screen.getByLabelText('Review rationale'),{target:{value:'Checked expected outputs'}});
  expect(approve).toBeDisabled();
  fireEvent.click(screen.getByRole('checkbox'));
  fireEvent.click(approve);
  await waitFor(() => expect(algorithmsApi.approveContract).toHaveBeenCalledWith('c1',{
    expected_fingerprint:'exact-fingerprint', source_reference:'review/1', rationale:'Checked expected outputs', scope_reviewed:true
  }));
});
it('never offers self-approval and never displays another project record', async () => {
  algorithmsApi.getContracts.mockResolvedValue({ contracts: [{...contract, proposed_by:'reviewer'}, {...contract, project_id:'p2', contract_id:'foreign', contract:{name:'Foreign'}}] });
  mount(); await choose('Requirements');
  fireEvent.click(await screen.findByRole('button',{name:'Review'}));
  expect(screen.getByText('Independent reviewer required.')).toBeInTheDocument();
  expect(screen.queryByRole('button',{name:'Approve reviewed contract'})).not.toBeInTheDocument();
  expect(screen.queryByText('Foreign')).not.toBeInTheDocument();
});
