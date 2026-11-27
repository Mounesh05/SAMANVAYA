/**
 * QA dashboard CI list: each configuration has a stable, unique React key,
 * and records without a branch (test-report import registrations) or with a
 * repeated branch render without warnings or a broken Disable action.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { QADashboardPage, ciConfigKey } from '../pages/qa/QADashboardPage';
import { qaApi } from '../api/qa.api';
import { useAuthStore } from '../store/useAuthStore';
import { roleUser } from './utils/roleUser';

vi.mock('../api/qa.api', () => ({
  qaApi: {
    getProjects: vi.fn(), getDashboard: vi.fn(), getCIConfigs: vi.fn(), getTestRuns: vi.fn(),
    enableCIIntegration: vi.fn(), disableCIIntegration: vi.fn(),
  },
}));

let consoleError;

function renderDashboard(configs) {
  qaApi.getProjects.mockResolvedValue([{ id: 'P1', name: 'Atlas' }]);
  qaApi.getCIConfigs.mockResolvedValue({ configs });
  qaApi.getTestRuns.mockResolvedValue({ runs: [] });
  qaApi.getDashboard.mockResolvedValue({
    total_test_cases: 0, not_executed: 0, total_executions: 0, passed: 0, failed: 0, blocked: 0, pass_rate: 0,
    open_defects: 0, awaiting_retest: 0, recent_executions: [], execution_trend: [],
  });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><QADashboardPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

// React's two key warnings: a missing key, and two children with the same key.
const keyWarnings = () => consoleError.mock.calls.filter((call) => {
  const text = call.map(String).join(' ');
  return text.includes('unique "key"') || text.includes('same key');
});

async function ciList() {
  const card = (await screen.findByText('CI integration')).closest('section, div, article');
  await within(document.body).findAllByText(/Enabled/);
  return card;
}

beforeEach(() => {
  vi.clearAllMocks();
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
  useAuthStore.setState({ user: roleUser('QA', { employee_id: 'E6' }), token: null, isAuthenticated: true });
});

afterEach(() => consoleError.mockRestore());

describe('CI configuration keys', () => {
  it('a record without a branch renders with no key warning and no Disable button', async () => {
    renderDashboard([
      { config_id: 'a1', project_id: 'P1', repository: 'org/app', enabled: true, artifact_import_source: 'github_actions' },
      { config_id: 'b2', project_id: 'P1', repository: 'org/app', branch: 'main', enabled: true },
    ]);
    await ciList();
    expect(screen.getByText('all branches (test-report import)')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: 'Disable' })).toHaveLength(1); // only the "main" record
    expect(keyWarnings()).toEqual([]);
  });

  it('repeated branch values render as separate rows with no key warning', async () => {
    renderDashboard([
      { config_id: 'c3', project_id: 'P1', repository: 'org/app', branch: 'main', enabled: true },
      { config_id: 'd4', project_id: 'P1', repository: 'org/other', branch: 'main', enabled: true },
    ]);
    await ciList();
    expect(screen.getByText('org/app')).toBeInTheDocument();
    expect(screen.getByText('org/other')).toBeInTheDocument();
    expect(keyWarnings()).toEqual([]);
  });

  it('records without config_id, branch or repository still get unique keys', async () => {
    renderDashboard([
      { project_id: 'P1', repository: 'org/app', enabled: true },
      { project_id: 'P1', enabled: true },
      { project_id: 'P1', repository: 'org/app', branch: 'main', enabled: true },
      { project_id: 'P1', repository: 'org/app', branch: 'main', enabled: true },
      null,
    ]);
    await ciList();
    expect(screen.getByText('Repository not set')).toBeInTheDocument();
    expect(keyWarnings()).toEqual([]);
  });

  it('ciConfigKey prefers the record id and stays unique without it', () => {
    expect(ciConfigKey({ config_id: 'abc', branch: 'main' }, 3)).toBe('ci-abc');
    expect(ciConfigKey({ config_id: 'abc', branch: 'dev' }, 9)).toBe('ci-abc'); // stable across reorders
    const legacy = [{ branch: 'main' }, { branch: 'main' }, {}, {}];
    const keys = legacy.map((config, index) => ciConfigKey(config, index));
    expect(new Set(keys).size).toBe(keys.length);
  });
});
