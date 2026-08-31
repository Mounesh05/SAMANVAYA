import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { evaluationApi } from '../../api/evaluation.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Input } from '../../components/common/Input';
import { LoadingState } from '../../components/common/LoadingState';
import { Cpu, Sparkles, CheckCircle2, Award } from 'lucide-react';
import { formatScore } from '../../utils/formatters';

export function AIEvaluationPage() {
  const [formData, setFormData] = useState({
    github_username: 'octocat',
    repo_owner: 'facebook',
    repo_name: 'react',
    pr_number: '',
    human_score: 8.0,
    evaluation_focus: 'code_quality',
  });

  const [evalResult, setEvalResult] = useState(null);

  const evalMutation = useMutation({
    mutationFn: (data) =>
      evaluationApi.evaluateDeveloperAI({
        ...data,
        pr_number: data.pr_number ? parseInt(data.pr_number, 10) : null,
        human_score: parseFloat(data.human_score),
      }),
    onSuccess: (res) => {
      setEvalResult(res);
    },
  });

  const handleEvaluate = (e) => {
    e.preventDefault();
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
              label="Developer GitHub Username"
              value={formData.github_username}
              onChange={(e) => setFormData({ ...formData, github_username: e.target.value })}
              placeholder="e.g. torvalds"
              required
            />

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="Repo Owner"
                value={formData.repo_owner}
                onChange={(e) => setFormData({ ...formData, repo_owner: e.target.value })}
                placeholder="e.g. facebook"
                required
              />
              <Input
                label="Repo Name"
                value={formData.repo_name}
                onChange={(e) => setFormData({ ...formData, repo_name: e.target.value })}
                placeholder="e.g. react"
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
              <Input
                label="PR Number (Optional)"
                type="number"
                value={formData.pr_number}
                onChange={(e) => setFormData({ ...formData, pr_number: e.target.value })}
                placeholder="e.g. 25840"
              />
              <Input
                label="Human Baseline Score (1-10)"
                type="number"
                step="0.1"
                min="1"
                max="10"
                value={formData.human_score}
                onChange={(e) => setFormData({ ...formData, human_score: e.target.value })}
                required
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
                    {evalResult.overall_score} / 10
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    Human Baseline: <strong>{evalResult.human_score}</strong>
                  </div>
                  <div style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                    AI Technical Score: <strong>{evalResult.ai_analysis?.technical_score || '—'}</strong>
                  </div>
                </div>
              </div>

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
