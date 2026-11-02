import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { evaluationApi } from '../../api/evaluation.api';
import { ToastProvider } from '../../components/common/Toast';
import { AIEvaluationPage } from './AIEvaluationPage';

vi.mock('../../api/evaluation.api', () => ({
  evaluationApi: {
    getLatest: vi.fn(),
    evaluateDeveloperAI: vi.fn(),
  },
}));

const completedEvaluation = {
  evaluation_id: 'EVAL-23045AF4',
  status: 'completed',
  is_preliminary: false,
  employee_id: 'DEMO-MOUNESH',
  github_username: 'Mounesh05',
  repo_owner: 'Mounesh05',
  repo_name: 'campusconnect-demo',
  pr_number: 1,
  head_commit_sha: '2a108fe591a6fad4a20f4763a37d238e9f0956bf',
  evaluation_focus: 'code_quality',
  ai_provider: 'ollama',
  model_name: 'llama3.2',
  overall_score: 6.92,
  score_dimensions: ['code_quality', 'delivery', 'reliability', 'engineering_judgment'],
  score_weights: {
    code_quality: 0.384615,
    delivery: 0.307692,
    reliability: 0.230769,
    engineering_judgment: 0.076923,
  },
  evidence_coverage: {
    code_quality: 'assessed',
    delivery: 'partially_assessable',
    reliability: 'partially_assessable',
    engineering_judgment: 'partially_assessable',
    collaboration: 'insufficient_evidence',
    engineering_impact: 'insufficient_evidence',
  },
  evidence_coverage_reasons: {
    collaboration: 'No pull request reviews or comments were retrieved.',
    engineering_impact: 'No long-term impact metrics were available.',
  },
  ai_analysis: {
    evidence_score: 6.92,
    dimensions: {
      code_quality: {
        score: 8,
        reasoning: 'Changed files support this score.',
        evidence: [{ file: 'backend/routes/events.py', line: 12, excerpt: 'def create_event():' }],
      },
      delivery: {
        score: 6,
        reasoning: 'One commit was retrieved.',
        evidence: [{ commit_sha: '2a108fe591a6fad4a20f4763a37d238e9f0956bf' }],
      },
      reliability: {
        score: 7,
        reasoning: 'CI checks passed.',
        evidence: [{ check_name: 'CI' }],
      },
      engineering_judgment: {
        score: 5,
        reasoning: 'Limited implementation evidence.',
        evidence: [{ file: 'backend/routes/events.py', line: 12 }],
      },
      collaboration: { assessment: 'insufficient_evidence' },
      engineering_impact: { assessment: 'insufficient_evidence' },
    },
  },
  score_coverage: {
    configured_total_weight: 100,
    defined_dimension_weight: 90,
    unallocated_weight: 10,
    assessed_weight: 65,
    coverage_percentage: 65,
    included_dimensions: ['code_quality', 'delivery', 'reliability', 'engineering_judgment'],
    configured_weights: {
      code_quality: 25,
      delivery: 20,
      reliability: 15,
      engineering_judgment: 5,
    },
    excluded_dimensions: [
      {
        dimension: 'collaboration',
        configured_weight: 15,
        reason: 'No pull request reviews or comments were retrieved.',
      },
      {
        dimension: 'engineering_impact',
        configured_weight: 10,
        reason: 'No measured post-change outcome or impact metrics were available.',
      },
    ],
    normalized_weights: {
      code_quality: 0.384615,
      delivery: 0.307692,
      reliability: 0.230769,
      engineering_judgment: 0.076923,
    },
    normalized_dimension_score: 6.92,
    overall_score: 6.92,
    calculation: '((8 × 25) + (6 × 20) + (7 × 15) + (5 × 5)) / 65 = 6.92',
  },
  evidence_references: [
    { file: 'backend/routes/events.py', reason: 'Implements the event route.' },
  ],
  evidence_manifest: {
    files: [{ file: 'backend/routes/events.py', status: 'modified' }],
    commits: [{ sha: '2a108fe591a6fad4a20f4763a37d238e9f0956bf' }],
    check_runs: [{ name: 'CI', conclusion: 'success' }],
    reviews: [],
    comments: [],
  },
  limitations: ['PR-scoped evidence only.'],
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <AIEvaluationPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AIEvaluationPage', () => {
  beforeEach(() => {
    evaluationApi.getLatest.mockResolvedValue(completedEvaluation);
  });

  it('presents a completed evaluation as PR-scoped and shows its calculation and evidence', async () => {
    renderPage();

    expect(await screen.findByText('EVAL-23045AF4', {}, { timeout: 10000 })).toBeInTheDocument();
    expect(screen.getByText('completed', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText(/This result evaluates the available evidence from PR #1/)).toBeInTheDocument();
    expect(screen.getByText(/ollama \/ llama3.2/)).toBeInTheDocument();
    expect(screen.getByText(/8 × 25/)).toBeInTheDocument();
    expect(screen.getAllByText('6.92 / 10').length).toBeGreaterThan(0);
    expect(screen.getByText(/assessed weight: 65 \(65% coverage\)/)).toBeInTheDocument();
    expect(screen.getByText(/unallocated configured weight: 10/i)).toBeInTheDocument();
    expect(screen.getByText(/normalized score:/)).toBeInTheDocument();
    expect(screen.getByText('backend/routes/events.py: Implements the event route.')).toBeInTheDocument();
    expect(
      screen.getAllByText('No pull request reviews or comments were retrieved.').length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/Preliminary evaluation/)).not.toBeInTheDocument();
    expect(screen.queryByText(/collaboration.*\/ 10/i)).not.toBeInTheDocument();
    expect(screen.getByText('backend/routes/events.py (modified)')).toBeInTheDocument();
    expect(
      screen.getAllByText(/Evidence: backend\/routes\/events.py:12/).length,
    ).toBeGreaterThan(0);
  });

  it('retains the preliminary warning for preliminary results', async () => {
    evaluationApi.getLatest.mockResolvedValue({
      ...completedEvaluation,
      status: 'processing',
      is_preliminary: true,
    });

    renderPage();

    expect(await screen.findByText('Preliminary evaluation. Review evidence coverage before using this result.'))
      .toBeInTheDocument();
    expect(screen.getByText('Preliminary PR-scoped evaluation')).toBeInTheDocument();
  });

  it('does not label a completed evaluation preliminary because evidence is incomplete', async () => {
    evaluationApi.getLatest.mockResolvedValue({
      ...completedEvaluation,
      is_preliminary: true,
    });

    renderPage();

    expect(await screen.findByText('completed', { selector: 'strong' })).toBeInTheDocument();
    expect(screen.getByText('PR-scoped evaluation')).toBeInTheDocument();
    expect(screen.queryByText(/Preliminary/)).not.toBeInTheDocument();
    expect(screen.getByText(/65% coverage/)).toBeInTheDocument();
  });
});
