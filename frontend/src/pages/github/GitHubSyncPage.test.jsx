import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import { renderWithProviders } from '../../tests/utils/test-utils';
import { githubApi } from '../../api/github.api';
import { GitHubSyncPage } from './GitHubSyncPage';
import { useAuthStore } from '../../store/useAuthStore';
import { withPermissions } from '../../tests/utils/roleUser';

vi.mock('../../api/github.api', () => ({
  githubApi: {
    checkHealth: vi.fn(),
    getProjectConfig: vi.fn(),
    saveProjectConfig: vi.fn(),
    syncPullRequest: vi.fn(),
    provisionQaWorkflow: vi.fn(),
  },
}));

const quality = {
  quality_score: 83,
  quality_grade: 'B',
  dimension_scores: { static_security: 90, testing: 80, complexity: 70, architecture: 100, duplication: 75 },
  penalties: { static_security: 10, testing: 20, complexity: 30, architecture: 0, duplication: 25 },
};
const risk = { risk_score: 27, risk_level: 'low', risk_factors: [], dimension_scores: { size: 12 } };
const engineResults = { schema_version: 'engine-results-v1', quality, risk };

async function submitResult(analysis, report) {
  githubApi.syncPullRequest.mockResolvedValue({
    message: 'PR synced successfully',
    risk_score: risk.risk_score,
    risk_level: risk.risk_level,
    ai_analysis: analysis,
    code_quality_report: report,
    details: { code_quality_report: report, engine_results_v1: engineResults },
  });
  renderWithProviders(<GitHubSyncPage />);
  const button = screen.getByRole('button', { name: 'Sync & Analyze Pull Request' });
  const form = within(button.closest('form'));
  fireEvent.change(form.getByLabelText(/Repository Owner/), { target: { value: 'owner' } });
  fireEvent.change(form.getByLabelText(/Repository Name/), { target: { value: 'repo' } });
  fireEvent.change(form.getByLabelText(/PR Number/), { target: { value: '7' } });
  fireEvent.change(form.getByLabelText(/Target Project ID/), { target: { value: 'P1' } });
  fireEvent.click(button);
  await screen.findByText('PR synced successfully');
  expect(githubApi.syncPullRequest).toHaveBeenCalledWith({
    owner: 'owner', repo: 'repo', pr_number: 7, project_id: 'P1', use_ai: true,
  });
}

describe('GitHubSyncPage report compatibility', () => {
  beforeEach(() => {
    useAuthStore.setState({ user: withPermissions({ employee_id: 'A', role: 'DEVELOPER', org_id: 'O1' }) });
    githubApi.checkHealth.mockResolvedValue({ status: 'operational' });
    githubApi.getProjectConfig.mockResolvedValue(null);
  });

  it('renders versioned engine values with a null legacy breakdown', async () => {
    const analysis = { status: 'completed', analysis: 'Advisory review', recommendations: [], engine_results_v1: engineResults };
    const report = {
      quality_representation: 'quality-engine-v1', quality_breakdown: null,
      engine_quality: { schema_version: 'quality-engine-v1', ...quality },
      engine_risk: risk, quality_score: 83, failure_risk: 27,
    };
    await submitResult(analysis, report);
    const output = screen.getByText((_, element) => element.tagName === 'P' && element.textContent === JSON.stringify(analysis, null, 2));
    expect(output).toHaveTextContent('engine-results-v1');
    expect(output).toHaveTextContent('"architecture": 100');
    expect(output).toHaveTextContent('"testing": 80');
    expect(output).not.toHaveTextContent('NaN');
    expect(output).not.toHaveTextContent('[object Object]');
  });

  it('retains historical reports in their existing result view', async () => {
    const analysis = { analysis: 'Historical advisory review', recommendations: ['Inspect evidence'] };
    await submitResult(analysis, { quality_score: 78, quality_breakdown: {
      correctness: 18, maintainability: 15, security: 16, testing: 10, performance: 8, architecture: 8, readability: 3,
    } });
    expect(screen.getByText((_, element) => element.tagName === 'P' && element.textContent.includes('Historical advisory review'))).toBeVisible();
  });

  it.each(['failed', 'unavailable'])('preserves an explicit %s interpretation with available engine measurements', async (status) => {
    const analysis = { status, analysis: null, errors: ['MODEL_UNAVAILABLE'], engine_results_v1: engineResults };
    await submitResult(analysis, { quality_representation: 'quality-engine-v1', quality_breakdown: null });
    expect(screen.getByText((_, element) => element.tagName === 'P' && element.textContent === JSON.stringify(analysis, null, 2))).toHaveTextContent(status);
    expect(screen.getByText((_, element) => element.tagName === 'P' && element.textContent.includes('MODEL_UNAVAILABLE'))).toBeVisible();
  });

  it('handles absent AI and report data', async () => {
    await submitResult(null, null);
    await waitFor(() => expect(screen.queryByText('AI Code Review')).not.toBeInTheDocument());
  });
});
