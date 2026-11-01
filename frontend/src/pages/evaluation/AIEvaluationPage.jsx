import React, { useEffect, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { evaluationApi } from '../../api/evaluation.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { LoadingState } from '../../components/common/LoadingState';
import { useToast } from '../../components/common/Toast';
import { Cpu } from 'lucide-react';

export function AIEvaluationPage() {
  const toast = useToast();
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
    if (formData.human_score && (formData.human_score < 1 || formData.human_score > 10)) {
      toast.error('Human baseline score must be between 1 and 10');
      return;
    }
    
    evalMutation.mutate(formData);
  };

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
                label="PR Number (Optional)"
                type="number"
                min="1"
                step="1"
                value={formData.pr_number}
                onChange={(e) => setFormData({ ...formData, pr_number: e.target.value })}
                placeholder="e.g. 42"
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
              {evalResult.is_preliminary && (
                <div style={{ padding: '0.75rem', color: 'var(--warning)', backgroundColor: 'var(--bg-elevated)' }}>
                  Preliminary evaluation. Review evidence coverage before using this result.
                </div>
              )}
              {evalResult.unsupported_references?.length > 0 && (
                <div style={{ padding: '0.75rem', color: 'var(--danger)', backgroundColor: 'var(--bg-elevated)' }}>
                  Evidence validation warning: {evalResult.unsupported_references.length} unsupported reference(s) were detected.
                </div>
              )}
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
                    OVERALL EVALUATION
                  </span>
                  <div style={{ fontSize: '2rem', fontWeight: '900', color: 'var(--cyan)' }}>
                    {evalResult.overall_score == null ? 'Insufficient evidence' : `${evalResult.overall_score} / 10`}
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Human Baseline: <strong>{evalResult.human_score}</strong>
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Evidence Score: <strong>{evalResult.ai_analysis?.evidence_score ?? '—'} / 10</strong>
                  </div>
                </div>
              </div>

              <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                <strong>{evalResult.repo_owner}/{evalResult.repo_name}</strong>
                {evalResult.pr_number ? ` · PR #${evalResult.pr_number}` : ''}
                {evalResult.repo_info?.pr_title ? ` · ${evalResult.repo_info.pr_title}` : ''}
                <div>Focus: {evalResult.evaluation_focus || 'code_quality'}</div>
              </div>

              {evalResult.evidence_coverage && (
                <div>
                  <h4>Evidence Coverage</h4>
                  <ul>
                    {Object.entries(evalResult.evidence_coverage).map(([name, status]) => (
                      <li key={name}>{name.replaceAll('_', ' ')}: {status.replaceAll('_', ' ')}</li>
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
                      <li key={idx}>{item.file || 'PR evidence'}: {item.reason || item.recommendation || 'Referenced by the evaluation'}</li>
                    ))}
                  </ul>
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
                    {Object.entries(evalResult.ai_analysis.dimensions).map(([name, dimension]) => (
                      <div key={name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                        <span>{name.replaceAll('_', ' ')}</span>
                        <strong>{dimension.score} / 10</strong>
                      </div>
                    ))}
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
