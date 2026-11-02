import React, { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { evaluationApi } from '../../api/evaluation.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../components/common/Toast';
import { Cpu } from 'lucide-react';

function getScoreCalculation(result) {
  const dimensions = result.score_dimensions || [];
  const parts = dimensions.flatMap((name) => {
    const score = result.ai_analysis?.dimensions?.[name]?.score;
    const weight = result.score_weights?.[name];
    if (typeof score !== 'number' || typeof weight !== 'number') return [];
    return [{ score, weight }];
  });
  if (!parts.length) return null;

  const calculatedScore = parts.reduce((total, part) => total + part.score * part.weight, 0);
  const humanScore = result.human_score;
  const overallScore = typeof humanScore === 'number'
    ? calculatedScore * 0.9 + humanScore * 0.1
    : calculatedScore;
  const expression = parts
    .map(({ score, weight }) => `${score} × ${weight.toFixed(6)}`)
    .join(' + ');
  return {
    expression: typeof humanScore === 'number'
      ? `(${expression}) × 0.9 + ${humanScore} × 0.1`
      : expression,
    calculatedScore: overallScore.toFixed(2),
  };
}

export function AIEvaluationPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [formData, setFormData] = useState({
    employee_id: '',
    github_username: '',
    repo_owner: '',
    repo_name: '',
    pr_number: '',
    human_score: '',
    evaluation_focus: 'code_quality',
  });

  const [evalResult, setEvalResult] = useState(null);
  const latestEvaluation = useQuery({
    queryKey: ['latest-evaluation'],
    queryFn: evaluationApi.getLatest,
  });

  useEffect(() => {
    if (latestEvaluation.data) {
      setEvalResult(latestEvaluation.data);
    }
  }, [latestEvaluation.data]);

  const evalMutation = useMutation({
    mutationFn: (data) =>
      evaluationApi.evaluateDeveloperAI({
        ...data,
        pr_number: data.pr_number ? parseInt(data.pr_number, 10) : null,
        human_score: data.human_score ? parseFloat(data.human_score) : null,
      }),
    onSuccess: (res) => {
      setEvalResult(res);
      queryClient.setQueryData(['latest-evaluation'], res);
      toast.success('AI evaluation completed successfully!');
    },
    onError: (error) => {
      const message = error?.message || 'Evaluation failed';
      toast.error(message);
    },
  });

  const handleEvaluate = (e) => {
    e.preventDefault();
    
    // Validate required fields
    if (!formData.github_username.trim()) {
      toast.error('GitHub username is required');
      return;
    }
    if (!formData.employee_id.trim()) {
      toast.error('Employee ID is required');
      return;
    }
    if (!formData.repo_owner.trim()) {
      toast.error('Repository owner is required');
      return;
    }
    if (!formData.repo_name.trim()) {
      toast.error('Repository name is required');
      return;
    }
    if (!/^\d+$/.test(formData.pr_number) || Number(formData.pr_number) < 1) {
      toast.error('A valid pull request number is required');
      return;
    }
    if (
      formData.human_score &&
      (!Number.isFinite(Number(formData.human_score)) ||
        Number(formData.human_score) < 1 ||
        Number(formData.human_score) > 10)
    ) {
      toast.error('Human baseline score must be between 1 and 10');
      return;
    }
    
    evalMutation.mutate(formData);
  };

  const scoreCalculation = evalResult ? getScoreCalculation(evalResult) : null;
  const displayedCalculatedScore =
    evalResult?.score_coverage?.overall_score ?? scoreCalculation?.calculatedScore;

  return (
    <div>
      <PageHeader
        title="AI-Powered Developer Evaluation"
        subtitle="Evaluate developer contributions across public or private GitHub repositories using AI synthesis."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        {/* Input Form Card */}
        <Card title="Evaluation Parameters" subtitle="GitHub repository & developer details">
          <form onSubmit={handleEvaluate} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <Input
              label="Employee ID"
              value={formData.employee_id}
              onChange={(e) => setFormData({ ...formData, employee_id: e.target.value })}
              placeholder="e.g. DEMO-MOUNESH"
              required
            />

            <Input
              label="Developer GitHub Username"
              value={formData.github_username}
              onChange={(e) => setFormData({ ...formData, github_username: e.target.value })}
              placeholder="e.g. contributor-name"
              required
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="Repo Owner"
                value={formData.repo_owner}
                onChange={(e) => setFormData({ ...formData, repo_owner: e.target.value })}
                placeholder="e.g. organization"
                required
              />
              <Input
                label="Repo Name"
                value={formData.repo_name}
                onChange={(e) => setFormData({ ...formData, repo_name: e.target.value })}
                placeholder="e.g. repository-name"
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="PR Number"
                type="number"
                min="1"
                step="1"
                value={formData.pr_number}
                onChange={(e) => setFormData({ ...formData, pr_number: e.target.value })}
                placeholder="e.g. 42"
                required
              />
              <Input
                label="Human Baseline Score (1-10, optional)"
                type="number"
                step="0.1"
                min="1"
                max="10"
                value={formData.human_score}
                onChange={(e) => setFormData({ ...formData, human_score: e.target.value })}
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              isLoading={evalMutation.isPending}
              leftIcon={<Cpu size={16} />}
            >
              Run AI Evaluation
            </Button>
          </form>
        </Card>

        {/* Results Card */}
        <Card title="AI Evaluation Outcome" subtitle="Synthesized scores and actionable recommendations">
          {evalMutation.isPending ? (
            <LoadingState message="Analyzing commits, PRs, and running LLM evaluation..." />
          ) : evalResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {evalResult.duplicate && (
                <div style={{ padding: '0.75rem', color: 'var(--warning)', backgroundColor: 'var(--bg-elevated)' }}>
                  This PR head already has a validated evaluation. Showing {evalResult.evaluation_id}.
                </div>
              )}
              {evalResult.is_preliminary && evalResult.status !== 'completed' && (
                <div style={{ padding: '0.75rem', color: 'var(--warning)', backgroundColor: 'var(--bg-elevated)' }}>
                  Preliminary evaluation. Review evidence coverage before using this result.
                </div>
              )}
              {evalResult.unsupported_references?.length > 0 && (
                <div style={{ padding: '0.75rem', color: 'var(--danger)', backgroundColor: 'var(--bg-elevated)' }}>
                  Evidence validation warning: {evalResult.unsupported_references.length} unsupported reference(s) were detected.
                </div>
              )}
              <div style={{ padding: '0.75rem', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-md)' }}>
                <strong>
                  {evalResult.is_preliminary && evalResult.status !== 'completed'
                    ? 'Preliminary PR-scoped evaluation'
                    : 'PR-scoped evaluation'}
                </strong>
                <div>
                  This result evaluates the available evidence from PR #{evalResult.pr_number}; it is not a
                  complete assessment of the developer&apos;s engineering performance.
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '1rem',
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                    OVERALL SCORE (NORMALIZED TO ASSESSED DIMENSIONS)
                  </span>
                  <div style={{ fontSize: '2rem', fontWeight: '900', color: 'var(--cyan)' }}>
                    {evalResult.overall_score == null ? 'Overall score unavailable' : `${evalResult.overall_score} / 10`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Human Baseline: <strong>{evalResult.human_score ?? '—'}</strong>
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Evidence Score: <strong>{evalResult.ai_analysis?.evidence_score ?? '—'} / 10</strong>
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                <div>Evaluation ID: <strong>{evalResult.evaluation_id}</strong></div>
                <div>Status: <strong>{evalResult.status || 'unknown'}</strong></div>
                <div>Developer: <strong>{evalResult.employee_id}</strong> ({evalResult.github_username})</div>
                <strong>{evalResult.repo_owner}/{evalResult.repo_name}</strong>
                {evalResult.pr_number ? ` · PR #${evalResult.pr_number}` : ''}
                {evalResult.repo_info?.pr_title ? ` · ${evalResult.repo_info.pr_title}` : ''}
                <div>Focus: {evalResult.evaluation_focus || 'code_quality'}</div>
                {evalResult.head_commit_sha && (
                  <div>Commit SHA: <code>{evalResult.head_commit_sha}</code></div>
                )}
                <div>
                  Model: <strong>{evalResult.ai_provider || 'unknown'} / {evalResult.model_name || 'unknown'}</strong>
                </div>
              </div>

              {evalResult.score_dimensions?.length > 0 && (
                <div>
                  <h4>Score coverage and calculation</h4>
                  {evalResult.score_coverage && (
                    <div>
                      Configured total weight: {evalResult.score_coverage.configured_total_weight ?? '—'};{' '}
                      assessed weight: {evalResult.score_coverage.assessed_weight ?? '—'} (
                      {evalResult.score_coverage.coverage_percentage ?? '—'}% coverage).
                      {evalResult.score_coverage.unallocated_weight > 0 && (
                        <> Unallocated configured weight: {evalResult.score_coverage.unallocated_weight}.</>
                      )}
                    </div>
                  )}
                  {scoreCalculation ? (
                    <div>
                      {evalResult.score_coverage?.calculation || `${scoreCalculation.expression} = ${scoreCalculation.calculatedScore}`}
                      {' '}· normalized score: <strong>
                        {displayedCalculatedScore} / 10
                      </strong>
                      {' '}· persisted overall score: <strong>{evalResult.overall_score ?? 'unavailable'} / 10</strong>
                    </div>
                  ) : (
                    <div>Calculation metadata is unavailable for this historical evaluation.</div>
                  )}
                  {evalResult.score_coverage?.excluded_dimensions?.length > 0 && (
                    <div>
                      Excluded from score:
                      <ul>
                        {evalResult.score_coverage.excluded_dimensions.map((item) => (
                          <li key={item.dimension}>
                            {item.dimension.replaceAll('_', ' ')} ({item.configured_weight} configured weight):
                            {' '}{item.reason}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}

              {evalResult.evidence_coverage && (
                <div>
                  <h4>Evidence Coverage</h4>
                  <ul>
                    {Object.entries(evalResult.evidence_coverage).map(([name, status]) => (
                      <li key={name}>
                        <strong>{name.replaceAll('_', ' ')}</strong>: {status.replaceAll('_', ' ')}
                        {evalResult.evidence_coverage_reasons?.[name] && (
                          <div>{evalResult.evidence_coverage_reasons[name]}</div>
                        )}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {evalResult.score_dimensions?.length > 0 && (
                <div>
                  <h4>Dimensions included in the score</h4>
                  <ul>
                    {evalResult.score_dimensions.map((name) => (
                      <li key={name}>
                        {name.replaceAll('_', ' ')} (configured weight{' '}
                        {evalResult.score_coverage?.configured_weights?.[name] ?? '—'}; normalized weight{' '}
                        {((evalResult.score_weights?.[name] || 0) * 100).toFixed(4)}%)
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {evalResult.recommendations && evalResult.recommendations.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    AI Recommendations:
                  </h4>
                  <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                    {evalResult.recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {evalResult.ai_analysis?.strengths?.length > 0 && (
                <div>
                  <h4>Strengths</h4>
                  <ul>{evalResult.ai_analysis.strengths.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
                </div>
              )}

              {evalResult.ai_analysis?.weaknesses?.length > 0 && (
                <div>
                  <h4>Weaknesses</h4>
                  <ul>{evalResult.ai_analysis.weaknesses.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
                </div>
              )}

              {evalResult.evidence_references?.length > 0 && (
                <div>
                  <h4>Evidence References</h4>
                  <ul>
                    {evalResult.evidence_references.map((item, idx) => (
                      <li key={idx}>
                        {item.file || item.commit_sha || item.check_name || item.review_id || item.comment_id || 'PR evidence'}
                        {item.line ? `:${item.line}` : ''}
                        {item.excerpt ? ` — “${item.excerpt}”` : ''}
                        : {item.reason || 'Referenced by the evaluation'}
                        {item.recommendation && <div>Recommendation: {item.recommendation}</div>}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {evalResult.evidence_manifest?.files?.length > 0 && (
                <div>
                  <h4>Pull request evidence manifest</h4>
                  <ul>
                    {evalResult.evidence_manifest.files.map((file, idx) => (
                      <li key={`${file.file}-${idx}`}>
                        {file.file}{file.status ? ` (${file.status})` : ''}
                      </li>
                    ))}
                  </ul>
                  <div>
                    Retrieved {evalResult.evidence_manifest.commits?.length || 0} commit(s),{' '}
                    {evalResult.evidence_manifest.check_runs?.length || 0} check(s),{' '}
                    {evalResult.evidence_manifest.reviews?.length || 0} review(s), and{' '}
                    {evalResult.evidence_manifest.comments?.length || 0} comment(s).
                  </div>
                </div>
              )}

              {evalResult.limitations?.length > 0 && (
                <div>
                  <h4>Limitations</h4>
                  <ul>{evalResult.limitations.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
                </div>
              )}

              {evalResult.ai_analysis?.dimensions && (
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    AI Evidence Breakdown
                  </h4>
                  <div style={{ display: 'grid', gap: '0.4rem' }}>
                    {Object.entries(evalResult.ai_analysis.dimensions).map(([name, dimension]) => {
                      const status = evalResult.evidence_coverage?.[name] || 'not_assessed';
                      const hasScore =
                        typeof dimension.score === 'number' &&
                        (status === 'assessed' || status === 'partially_assessable');
                      const statusLabel = hasScore
                        ? 'Assessed'
                        : status === 'not_assessed' ||
                            status === 'assessed' ||
                            status === 'partially_assessable'
                          ? 'Not assessed'
                          : 'Insufficient evidence';
                      const reason =
                        evalResult.evidence_coverage_reasons?.[name] ||
                        (!evalResult.evidence_coverage?.[name]
                          ? 'Evidence eligibility was not recorded for this historical result.'
                          : statusLabel === 'Not assessed'
                            ? 'No validated score is available for this dimension.'
                            : 'The retrieved evidence does not support scoring this dimension.');
                      return (
                        <div
                          key={name}
                          style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr auto',
                            gap: '0.25rem 1rem',
                            fontSize: '0.8125rem',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          <strong>{name.replaceAll('_', ' ')}</strong>
                          <strong>
                            {hasScore
                              ? `${dimension.score} / 10`
                              : statusLabel}
                          </strong>
                          <span>{statusLabel}</span>
                          {hasScore && dimension.reasoning && <span>{dimension.reasoning}</span>}
                          {hasScore && dimension.evidence?.map((reference, idx) => (
                            <span key={`${name}-evidence-${idx}`}>
                              Evidence: {reference.file || reference.commit_sha || reference.check_name || reference.review_id || reference.comment_id}
                              {reference.line ? `:${reference.line}` : ''}
                              {reference.excerpt ? ` — “${reference.excerpt}”` : ''}
                              {reference.reason ? `: ${reference.reason}` : ''}
                            </span>
                          ))}
                          {hasScore && !dimension.evidence?.length && (
                            <span>Dimension-level evidence citations were not recorded for this historical result.</span>
                          )}
                          {!hasScore && reason && <span>{reason}</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Fill in parameters and click 'Run AI Evaluation' to begin.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
