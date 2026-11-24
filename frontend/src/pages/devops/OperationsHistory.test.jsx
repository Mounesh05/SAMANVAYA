import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, expect, it, vi } from 'vitest';
import { OperationsHistory } from './OperationsHistory';
import { rolesApi } from '../../api/roles.api';
import { IncidentsPage } from '../incidents/IncidentsPage';
import { incidentsApi } from '../../api/incidents.api';
import { useAuthStore } from '../../store/useAuthStore';
import { roleUser } from '../../tests/utils/roleUser';

vi.mock('../../api/roles.api', () => ({ rolesApi: { getPipelines: vi.fn(), getDeployments: vi.fn() } }));
vi.mock('../../api/incidents.api', () => ({ incidentsApi: { list: vi.fn() } }));
vi.mock('../../api/projects.api', () => ({ projectsApi: { list: async () => [] } }));

function openHistory(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/pipelines" element={<OperationsHistory kind="pipelines" />} />
      <Route path="/deployments/:owner?/:repo?" element={<OperationsHistory kind="deployments" />} />
      <Route path="/incidents" element={<IncidentsPage />} />
    </Routes>
  </MemoryRouter></QueryClientProvider>);
}

beforeEach(() => vi.resetAllMocks());

it('keeps the selected day and outcome when paging and opens the exact GitHub attempt', async () => {
  const run = { id: 19, name: 'CI', repository: 'acme/shop', status: 'completed', conclusion: 'failure' };
  rolesApi.getPipelines.mockImplementation(({ page }) => Promise.resolve({
    pipelines: [{ ...run, attempt: page }], total: 2, page_size: 1,
  }));
  openHistory('/pipelines?day=2026-11-22&outcome=failed');
  const next = await screen.findByRole('button', { name: 'Next' });
  fireEvent.click(next);
  expect(await screen.findByRole('link', { name: 'CI #19 · attempt 2' })).toHaveAttribute('href',
    'https://github.com/acme/shop/actions/runs/19/attempts/2');
  expect(rolesApi.getPipelines).toHaveBeenLastCalledWith({ day: '2026-11-22', outcome: 'failed', page: 2 });
});

it('resolves a failed deployment notification to the exact repository, deployment, and commit', async () => {
  const sha = 'a'.repeat(40);
  rolesApi.getDeployments.mockResolvedValue({ deployments: [{
    id: 9, repository: 'acme/shop', environment: 'production', sha, status: 'failure',
  }], total: 1, page_size: 50 });
  openHistory('/deployments?repository=acme%2Fshop&deployment_id=9');
  expect(await screen.findByText('#9')).toBeInTheDocument();
  expect(screen.getByRole('link', { name: sha.slice(0, 12) })).toHaveAttribute('href', `https://github.com/acme/shop/commit/${sha}`);
  expect(rolesApi.getDeployments).toHaveBeenCalledWith({ repository: 'acme/shop', deployment_id: '9', today: false, page: 1 });
});

it('opens existing notification links that carry the owner and repository in the path', async () => {
  rolesApi.getDeployments.mockResolvedValue({ deployments: [], total: 0, page_size: 50 });
  openHistory('/deployments/acme/shop');
  expect(await screen.findByText('No matching GitHub records in your projects.')).toBeInTheDocument();
  expect(rolesApi.getDeployments).toHaveBeenCalledWith({ repository: 'acme/shop', deployment_id: undefined, today: false, page: 1 });
});

it('keeps the unresolved filter when loading older incident records', async () => {
  useAuthStore.setState({ user: roleUser('DEVOPS') });
  const incident = (i) => ({ id: `INC-${i}`, title: `Outage ${i}`, status: 'investigating', severity: 'high' });
  incidentsApi.list.mockImplementation(({ offset }) => Promise.resolve(offset ? [incident(51)] : Array.from({ length: 50 }, (_, i) => incident(i + 1))));
  openHistory('/incidents?status=unresolved');
  fireEvent.click(await screen.findByRole('button', { name: 'Load more incidents' }));
  expect(await screen.findByText('Outage 51')).toBeInTheDocument();
  expect(incidentsApi.list).toHaveBeenLastCalledWith({ status: 'unresolved', offset: 50, limit: 50 });
  expect(screen.queryByRole('button', { name: 'Load more incidents' })).not.toBeInTheDocument();
});
