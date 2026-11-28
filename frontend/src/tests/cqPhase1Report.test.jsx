import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AIInterpretation, ReportStatusNotice, ScoreExplanation } from '../pages/code-quality/AIInterpretation';
import { useAuthStore } from '../store/useAuthStore';
import { PERMISSIONS } from '../auth/permissions';
import { codeQualityApi } from '../api/codeQuality.api';

vi.mock('../api/codeQuality.api', () => ({ codeQualityApi: { retryAiInterpretation: vi.fn() } }));

const wrap = (ui) => render(<QueryClientProvider client={new QueryClient()}>{ui}</QueryClientProvider>);
const asUser = (permissions) => useAuthStore.setState({ user: { employee_id: 'QA-1', role: 'QA', permissions } });

const advisory = {
  schema_version: 'code-quality-advisory-v1', summary: '1 finding(s) in 1 analysed file(s): 1 low.',
  suggestions: [{ finding_id: 'F-1', why: 'unused import', action: 'Remove the unused import.' }],
  limitations: ['Test coverage was not measured.'],
};

describe('Phase 1 report: advisory contract', () => {
  beforeEach(() => { vi.resetAllMocks(); asUser([PERMISSIONS.VIEW_CODE_QUALITY, PERMISSIONS.TRIGGER_CODE_ANALYSIS]); });

  it('shows the summary, finding-bound suggestions and limitations, with no confidence', () => {
    wrap(<AIInterpretation ai={{ status: 'completed', errors: [], advisory, analysis: 'raw model text' }} />);
    expect(screen.getByText(advisory.summary)).toBeInTheDocument();
    expect(screen.getByText('Remove the unused import.')).toBeInTheDocument();
    expect(screen.getByText('F-1')).toBeInTheDocument();
    expect(screen.getByText('Test coverage was not measured.')).toBeInTheDocument();
    expect(screen.queryByText('raw model text')).not.toBeInTheDocument();
    expect(screen.queryByText(/confidence/i)).not.toBeInTheDocument();
  });

  it('does not claim the code is clean when there are no suggestions', () => {
    wrap(<AIInterpretation ai={{ status: 'completed', errors: [], advisory: { ...advisory, suggestions: [] } }} />);
    expect(screen.getByText(/does not mean the code is free of defects/)).toBeInTheDocument();
  });

  it('offers a bounded AI-only retry to analysts and updates the report', async () => {
    codeQualityApi.retryAiInterpretation.mockResolvedValue({ run_id: 'RUN-1' });
    wrap(<AIInterpretation ai={{ status: 'unavailable', errors: ['MODEL_UNAVAILABLE'] }} runId="RUN-1" attempts={1} />);
    fireEvent.click(screen.getByRole('button', { name: 'Retry AI interpretation' }));
    await waitFor(() => expect(codeQualityApi.retryAiInterpretation).toHaveBeenCalledWith('RUN-1'));
  });

  it('hides the retry from viewers and once the attempt limit is reached', () => {
    const ai = { status: 'failed', errors: ['MODEL_TIMEOUT'] };
    const { unmount } = wrap(<AIInterpretation ai={ai} runId="RUN-1" attempts={3} />);
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument();
    unmount();
    asUser([PERMISSIONS.VIEW_CODE_QUALITY]);
    wrap(<AIInterpretation ai={ai} runId="RUN-1" attempts={1} />);
    expect(screen.queryByRole('button', { name: /Retry/ })).not.toBeInTheDocument();
  });

  it('labels a partial report with its reasons in words', () => {
    render(<ReportStatusNotice run={{ report_status: 'partial', report_incomplete_reasons: [
      'ai_interpretation_unavailable:MODEL_UNAVAILABLE', 'static_tools_skipped:mypy'] }} />);
    const notice = screen.getByRole('status');
    expect(notice).toHaveTextContent('Report incomplete');
    expect(notice).toHaveTextContent('the AI model could not be reached');
    expect(notice).toHaveTextContent('some analysis tools did not run: mypy');
  });

  it('marks a failed report', () => {
    render(<ReportStatusNotice run={{ report_status: 'failed', report_incomplete_reasons: ['static_evidence_unavailable'] }} />);
    expect(screen.getByRole('status')).toHaveTextContent('Report failed');
  });

  it('explains the score with effective weights and renormalisation, collapsed by default', () => {
    render(<ScoreExplanation policyDigest="sha256:abc" explanation={{
      formula: 'score = 100 - weighted penalty', renormalized: true, weighted_penalty: 12.5,
      dimensions: [
        { dimension: 'static_security', measured: true, configured_weight: 0.4, effective_weight: 0.5, penalty: 20, score: 80 },
        { dimension: 'testing', measured: false, configured_weight: 0.2, effective_weight: null, penalty: null, score: null },
      ] }} />);
    const details = screen.getByText('How the quality score was calculated').closest('details');
    expect(details.open).toBe(false);
    expect(screen.getByText(/weights of the measured ones were rescaled/)).toBeInTheDocument();
    expect(screen.getByText('Not measured')).toBeInTheDocument();
    expect(screen.getByText(/policy sha256:abc/)).toBeInTheDocument();
  });
});
