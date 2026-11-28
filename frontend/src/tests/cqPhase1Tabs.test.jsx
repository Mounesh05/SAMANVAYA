import React from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { RunDetailPage } from '../pages/code-quality/RunDetailPage';
import { codeQualityApi } from '../api/codeQuality.api';
import { useAuthStore } from '../store/useAuthStore';
import { PERMISSIONS } from '../auth/permissions';

vi.mock('../api/codeQuality.api', () => ({
  codeQualityApi: { getRun: vi.fn(), getRunFindings: vi.fn(), getDiscoveredFunctions: vi.fn(), retryAiInterpretation: vi.fn() },
}));

let client;
function show() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/code-quality/runs/RUN-1']}><Routes>
    <Route path="/code-quality/runs/:runId" element={<RunDetailPage />} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

const RUN = {
  run_id: 'RUN-1', repository_id: 'PRJ-1', status: 'completed', quality_analysis_status: 'available',
  file_scope: 'repository', tools_executed: ['ruff'], quality_score: 88, quality_grade: 'B', commit_sha: 'a'.repeat(40),
  ai_required: true, ai_status: 'completed', report_status: 'complete', ai_attempts: 1,
  ai_analysis: { status: 'completed', errors: [], advisory: { schema_version: 'code-quality-advisory-v1', summary: 'Sixty findings.', suggestions: [], limitations: [] } },
  ai_provenance: { model: 'llama3.2:3b', policy_version: 'code-quality-advisory-v1', latency_ms: 812, evidence_digest: 'sha256:abc' },
  use_ai_requested: false,
};
const finding = (i) => ({ id: `F-${i}`, file_path: `src/m${i}.py`, line_number: i, rule_id: 'RUFF-F401', severity: 'low', message: `unused ${i}` });

beforeEach(() => {
  vi.resetAllMocks();
  useAuthStore.setState({ user: { employee_id: 'QA-1', role: 'QA', permissions: [PERMISSIONS.VIEW_CODE_QUALITY, PERMISSIONS.TRIGGER_CODE_ANALYSIS] } });
  codeQualityApi.getDiscoveredFunctions.mockResolvedValue({ status: 'available', functions: [], total: 0 });
  codeQualityApi.getRunFindings.mockImplementation(async (_, params) => {
    const all = Array.from({ length: 60 }, (_, i) => finding(i + 1)).filter((f) => !params.file || f.file_path === params.file || f.file_path.startsWith(params.file + '/'));
    const skip = params.skip || 0;
    return { total: all.length, findings: all.slice(skip, skip + params.limit) };
  });
});
afterEach(() => { cleanup(); client?.clear(); });

it('opens on an overview with the top findings and AI advice before any detail', async () => {
  codeQualityApi.getRun.mockResolvedValue(RUN);
  show();
  expect(await screen.findByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');
  expect(await screen.findByText(/unused 1$/)).toBeInTheDocument();
  expect(screen.queryByText(/unused 6$/)).not.toBeInTheDocument(); // only the top five
  expect(screen.getByText('AI interpretation')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'View all 60 findings' })).toBeInTheDocument();
  expect(screen.queryByText(/Function discovery/)).not.toBeInTheDocument(); // never before findings
  expect(screen.queryByRole('checkbox')).not.toBeInTheDocument(); // no AI opt-out
});

it('moves between tabs with the arrow keys', async () => {
  codeQualityApi.getRun.mockResolvedValue(RUN);
  show();
  const overview = await screen.findByRole('tab', { name: 'Overview' });
  fireEvent.keyDown(overview, { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Findings' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'Findings' })).toHaveFocus();
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Findings' }), { key: 'ArrowLeft' });
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Overview' }), { key: 'ArrowLeft' });
  expect(screen.getByRole('tab', { name: 'Evidence' })).toHaveAttribute('aria-selected', 'true');
});

it('pages through all findings with an exact total and resets the page on a filter', async () => {
  codeQualityApi.getRun.mockResolvedValue(RUN);
  show();
  fireEvent.click(await screen.findByRole('tab', { name: 'Findings' }));
  expect(await screen.findByText('Showing 1–25 of 60')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByText('Showing 26–50 of 60')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: 'Next' }));
  expect(await screen.findByText('Showing 51–60 of 60')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled();
  fireEvent.change(screen.getByLabelText('File or folder'), { target: { value: 'src/m12.py' } });
  expect(await screen.findByText('Showing 1–1 of 1')).toBeInTheDocument();
  await waitFor(() => expect(codeQualityApi.getRunFindings).toHaveBeenLastCalledWith('RUN-1', { file: 'src/m12.py', limit: 25, skip: 0 }));
});

it('offers the PR change filter on a revision child run', async () => {
  codeQualityApi.getRun.mockResolvedValue({ ...RUN, parent_run_id: 'PRQ-1' });
  show();
  fireEvent.click(await screen.findByRole('tab', { name: 'Findings' }));
  expect(await screen.findByLabelText('Change in this PR')).toBeInTheDocument();
});

it('keeps the score explanation in Metrics and the AI record in Evidence', async () => {
  codeQualityApi.getRun.mockResolvedValue({ ...RUN, score_explanation: { formula: 'score = 100 - weighted penalty', renormalized: false, weighted_penalty: 12, dimensions: [] } });
  show();
  fireEvent.click(await screen.findByRole('tab', { name: 'Metrics' }));
  expect(screen.getByText('How the quality score was calculated')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Evidence' }));
  expect(screen.getByText('Model: llama3.2:3b')).toBeInTheDocument();
  expect(screen.getByText('sha256:abc')).toBeInTheDocument();
  expect(screen.getByText(/asked for no AI; AI interpretation is required/)).toBeInTheDocument();
  expect(screen.getByText(/Function discovery \(not part of the quality score\)/).closest('details').open).toBe(false);
});

it('labels a legacy run without inventing an AI interpretation', async () => {
  const { ai_required, ai_analysis, ai_status, ai_provenance, report_status, ...legacy } = RUN;
  codeQualityApi.getRun.mockResolvedValue(legacy);
  show();
  expect(await screen.findByText('AI interpretation: legacy run, not recorded.')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('tab', { name: 'Evidence' }));
  expect(screen.getByText('Legacy run: no AI interpretation was recorded.')).toBeInTheDocument();
});

it('shows the composite report status in the header, not the per-tool status', async () => {
  codeQualityApi.getRun.mockResolvedValue({ ...RUN, quality_analysis_status: 'partial', file_scope: 'pr_comparison' });
  show();
  expect(await screen.findByText('Report complete')).toBeInTheDocument();
  expect(screen.queryByText('Partially analyzed')).not.toBeInTheDocument();
});

it('says a report is incomplete in the header when the AI interpretation is missing', async () => {
  codeQualityApi.getRun.mockResolvedValue({ ...RUN, ai_status: 'unavailable', report_status: 'partial',
    report_incomplete_reasons: ['ai_interpretation_unavailable:MODEL_UNAVAILABLE'] });
  show();
  expect(await screen.findByText('Report incomplete')).toBeInTheDocument();
});
