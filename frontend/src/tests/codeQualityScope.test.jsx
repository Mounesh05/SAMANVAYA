import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { CodeQualityPage } from '../pages/code-quality/CodeQualityPage';
import { RunDetailPage } from '../pages/code-quality/RunDetailPage';
import { codeQualityApi } from '../api/codeQuality.api';
import { projectsApi } from '../api/projects.api';
import { githubApi } from '../api/github.api';
import { algorithmsApi } from '../api/algorithms.api';
import { useAuthStore } from '../store/useAuthStore';
import { PERMISSIONS } from '../auth/permissions';

vi.mock('../api/codeQuality.api', () => ({
  codeQualityApi: {
    startAnalysis: vi.fn(),
    getRun: vi.fn(),
    getRunFindings: vi.fn(),
    getDiscoveredFunctions: vi.fn(),
    getHistory: vi.fn(),
    getBranches: vi.fn(),
    getRepositoryFiles: vi.fn(),
    getPullRequests: vi.fn(),
  },
}));
vi.mock('../api/projects.api', () => ({ projectsApi: { list: vi.fn() } }));
vi.mock('../api/github.api', () => ({ githubApi: { getProjectConfig: vi.fn() } }));
vi.mock('../api/algorithms.api', () => ({
  algorithmsApi: {
    getPRIntelligence: vi.fn(),
    getAvailability: vi.fn(),
    getCompatibilityRuns: vi.fn(),
    getRelationships: vi.fn(),
    getRequirementSources: vi.fn(),
    getContracts: vi.fn(),
    getHistory: vi.fn(),
  },
}));

let client;
function show() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/code-quality/runs/fixture']}><Routes>
    <Route path="/code-quality/runs/:runId" element={<RunDetailPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
function showHistoryPage() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/code-quality']}><Routes>
    <Route path="/code-quality" element={<CodeQualityPage />} />
    <Route path="/code-quality/runs/:runId" element={<RunDetailPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  vi.resetAllMocks();
  useAuthStore.setState({
    user: {
      employee_id: 'QA-1',
      org_id: 'ORG-A',
      role: 'QA',
      permissions: [PERMISSIONS.VIEW_CODE_QUALITY, PERMISSIONS.TRIGGER_CODE_ANALYSIS],
    },
  });
  codeQualityApi.getRunFindings.mockResolvedValue({ findings: [], total: 0 });
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'available', functions: [], total: 0 });
  codeQualityApi.getHistory.mockResolvedValue({ repository_id: 'PRJ-1', history: [], count: 0 });
  projectsApi.list.mockResolvedValue([{ id: 'PRJ-1', name: 'Service Repo' }]);
  githubApi.getProjectConfig.mockResolvedValue({
    repository_owner: 'acme',
    repository_name: 'service',
    default_branch: 'main',
  });
  codeQualityApi.getBranches.mockResolvedValue({
    default_branch: 'main',
    branches: [{ name: 'main' }, { name: 'release/v2' }],
    branches_available: true,
  });
  codeQualityApi.getRepositoryFiles.mockResolvedValue({
    repository_id: 'PRJ-1',
    ref: 'main',
    commit_sha: 'a'.repeat(40),
    files: ['backend/app.py', 'frontend/App.tsx'],
    directories: ['backend', 'frontend'],
    total_supported_files: 2,
    max_files_per_run: 100,
  });
  codeQualityApi.getPullRequests.mockResolvedValue({
    pull_requests: [
      { number: 17, title: 'Fix quality scope', state: 'open', base_ref: 'main', head_ref: 'feat/scope' },
    ],
  });
  algorithmsApi.getPRIntelligence.mockResolvedValue({ analyses: [] });
  algorithmsApi.getAvailability.mockResolvedValue({ available: false });
  algorithmsApi.getCompatibilityRuns.mockResolvedValue({ runs: [] });
  algorithmsApi.getRelationships.mockResolvedValue({ relationships: [] });
  algorithmsApi.getRequirementSources.mockResolvedValue({ sources: [] });
  algorithmsApi.getContracts.mockResolvedValue({ contracts: [] });
  algorithmsApi.getHistory.mockResolvedValue({ history: [] });
});
afterEach(() => { cleanup(); client?.clear(); });

it('does not present discovery-only snapshots as clean quality analysis', async () => {
  codeQualityApi.getRun.mockResolvedValue({ run_id: 'fixture', status: 'completed', analysis_level: 'purpose_discovery', language: 'python' });
  show();
  expect(await screen.findByText('Discovery finished · quality not run')).toBeInTheDocument();
  expect(screen.getByText('Quality score unavailable')).toBeInTheDocument();
  expect(screen.getByText(/No clean-code conclusion/)).toBeInTheDocument();
  expect(screen.queryByText(/0 issues|passes all quality/)).not.toBeInTheDocument();
});

it('shows partial tools and unavailable coverage with recorded findings', async () => {
  codeQualityApi.getRun.mockResolvedValue({
    run_id: 'fixture', status: 'completed', quality_analysis_status: 'partial',
    tools_executed: ['ruff'], tools_skipped: ['bandit', 'dependency-advisories-offline'],
    quality_unavailable_reason: 'Bandit unavailable',
    execution_provenance: { method: 'quality-snapshot-v1' },
  });
  codeQualityApi.getRunFindings.mockResolvedValue({ total: 1, findings: [{ file_path: 'module.py', line_number: 4, message: 'Unused binding', severity: 'low' }] });
  show();
  expect(await screen.findByText('Partially analyzed')).toBeInTheDocument();
  expect(screen.getByText('Bandit unavailable')).toBeInTheDocument();
  expect(screen.getByText('Test coverage: Not measured')).toBeInTheDocument();
  expect(screen.getByText(/coverage report for this revision/)).toBeInTheDocument();
  expect(screen.getByText(/cannot reach advisory databases/)).toBeInTheDocument();
  expect(await screen.findByText('Unused binding')).toBeInTheDocument();
  expect(screen.getByText('module.py')).toBeInTheDocument();
});

it('does not replace retrieval failures with zero findings', async () => {
  codeQualityApi.getRun.mockResolvedValue({ run_id: 'fixture', status: 'completed', tools_executed: ['ruff'] });
  codeQualityApi.getRunFindings.mockRejectedValue(new Error('Evidence unavailable'));
  show();
  expect(await screen.findByText('Evidence unavailable')).toBeInTheDocument();
  expect(screen.getByText('Retrieval failed')).toBeInTheDocument();
});

it('preserves a measured zero score as distinct from unavailable', async () => {
  codeQualityApi.getRun.mockResolvedValue({ run_id: 'fixture', status: 'completed',
    quality_analysis_status: 'available', file_scope: 'repository', tools_executed: ['ruff'],
    quality_score: 0, quality_grade: 'F', risk_score: 0, testing: { coverage_percentage: 0 } });
  show();
  await screen.findByText('Completed');
  expect(screen.getByText('Quality Score').parentElement).toHaveTextContent(/^Quality Score0/);
  expect(screen.queryByText('Quality score unavailable')).not.toBeInTheDocument();
  expect(screen.getByText('Source scope: Whole revision')).toBeInTheDocument();
  expect(screen.getByText('Tools executed: ruff')).toBeInTheDocument();
  expect(screen.getByText('Test coverage: 0%')).toBeInTheDocument();
});

it('defaults to whole-repository analysis with branch selector and supports selected-files and PR comparison modes', async () => {
  codeQualityApi.startAnalysis.mockResolvedValue({});
  showHistoryPage();

  await screen.findByRole('option', { name: 'Service Repo' });
  fireEvent.click(screen.getByRole('button', { name: 'Start analysis' }));
  const repoTab = screen.getByRole('tab', { name: /Whole repository/i });
  expect(repoTab).toHaveAttribute('aria-selected', 'true');
  fireEvent.change(screen.getByLabelText(/Analysis project/), { target: { value: 'PRJ-1' } });
  expect(await screen.findByText(/acme\/service/)).toBeInTheDocument();

  // Select a non-default branch without PR or filenames
  await screen.findByRole('option', { name: 'release/v2' });
  fireEvent.change(screen.getByLabelText('Branch'), { target: { value: 'release/v2' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(codeQualityApi.startAnalysis).toHaveBeenCalledWith(expect.objectContaining({
    repository_id: 'PRJ-1',
    file_scope: 'repository',
    repository_ref: 'release/v2',
    changed_files: [],
    pr_number: null,
  })));

  // Reopen modal and test Selected files browser (directory & file selection, no PR)
  fireEvent.click(await screen.findByRole('button', { name: 'Start analysis' }));
  fireEvent.click(screen.getByRole('tab', { name: /Selected files/i }));
  expect(await screen.findByText('backend/app.py')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'backend/' }));
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(codeQualityApi.startAnalysis).toHaveBeenLastCalledWith(expect.objectContaining({
    repository_id: 'PRJ-1',
    file_scope: 'selected_files',
    changed_files: ['backend/'],
    pr_number: null,
  })));

  // Reopen modal and test PR comparison mode without manually entering filenames
  fireEvent.click(await screen.findByRole('button', { name: 'Start analysis' }));
  fireEvent.click(screen.getByRole('tab', { name: /PR comparison/i }));
  fireEvent.change(await screen.findByLabelText('Pull request'), { target: { value: '17' } });
  fireEvent.click(screen.getByRole('button', { name: 'Run analysis' }));
  await waitFor(() => expect(codeQualityApi.startAnalysis).toHaveBeenLastCalledWith(expect.objectContaining({
    repository_id: 'PRJ-1',
    file_scope: 'pr_comparison',
    pr_number: 17,
    changed_files: [],
  })));
});
