import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RunDetailPage } from '../pages/code-quality/RunDetailPage';
import { codeQualityApi } from '../api/codeQuality.api';

vi.mock('../api/codeQuality.api', () => ({ codeQualityApi: { getRun: vi.fn(), getRunFindings: vi.fn(), getDiscoveredFunctions: vi.fn() } }));
let client;
function show() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/code-quality/runs/fixture']}><Routes>
    <Route path="/code-quality/runs/:runId" element={<RunDetailPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}
beforeEach(() => {
  vi.resetAllMocks();
  codeQualityApi.getRunFindings.mockResolvedValue({ findings: [], total: 0 });
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'available', functions: [], total: 0 });
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
    quality_analysis_status: 'available', tools_executed: ['ruff'], quality_score: 0, quality_grade: 'F', risk_score: 0 });
  show();
  await screen.findByText('Completed');
  expect(screen.getByText('Quality Score').parentElement).toHaveTextContent(/^Quality Score0/);
  expect(screen.queryByText('Quality score unavailable')).not.toBeInTheDocument();
});
