import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { cicdLogsApi } from '../../api/cicdLogs.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { Select } from '../../components/common/Select';
import { RiskBadge } from '../../components/common/RiskBadge';
import { LoadingState } from '../../components/common/LoadingState';
import { Terminal, Sparkles, AlertTriangle, ShieldCheck, CheckCircle2, Flame } from 'lucide-react';

export function CicdLogsPage() {
  const [logType, setLogType] = useState('build');
  const [logContent, setLogContent] = useState(
    'ERROR: npm ERR! code ELIFECYCLE\nnpm ERR! errno 1\nnpm ERR! build failed: TypeScript syntax error in auth.ts:42\nnpm ERR! TS2304: Cannot find name "jwtSecret".'
  );

  const [analysisResult, setAnalysisResult] = useState(null);

  const analyzeMutation = useMutation({
    mutationFn: (data) => cicdLogsApi.analyzeLog(data),
    onSuccess: (res) => {
      setAnalysisResult(res);
    },
  });

  const handleAnalyze = (e) => {
    e.preventDefault();
    analyzeMutation.mutate({
      log_content: logContent,
      log_type: logType,
      use_ai: true,
    });
  };

  return (
    <div>
      <PageHeader
        title="CI/CD Log Intelligence & Diagnostic"
        subtitle="Analyze build errors, test failures, and deployment incidents using Layer 5 Rule Engine + Layer 6 AI Agents."
      />

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: '1.5rem' }}>
        {/* Input Card */}
        <Card title="Raw CI/CD Log Input" subtitle="Paste log excerpt from GitHub Actions, Jenkins, or Docker">
          <form onSubmit={handleAnalyze} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div style={{ width: '220px' }}>
              <Select
                label="Log Type"
                value={logType}
                onChange={(e) => setLogType(e.target.value)}
                options={[
                  { value: 'build', label: 'Build Log' },
                  { value: 'test', label: 'Test Suite Log' },
                  { value: 'deployment', label: 'Deployment Log' },
                ]}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.8125rem', fontWeight: '600', color: 'var(--text-secondary)' }}>
                Log Content / Stack Trace
              </label>
              <textarea
                rows={10}
                value={logContent}
                onChange={(e) => setLogContent(e.target.value)}
                style={{
                  width: '100%',
                  padding: '0.85rem',
                  fontSize: '0.8125rem',
                  backgroundColor: 'var(--bg-input)',
                  color: '#38bdf8',
                  border: '1px solid var(--border-default)',
                  borderRadius: 'var(--radius-md)',
                  fontFamily: 'var(--font-mono)',
                  outline: 'none',
                  marginTop: '0.35rem',
                  lineHeight: '1.5',
                }}
                required
              />
            </div>

            <Button
              type="submit"
              variant="primary"
              isLoading={analyzeMutation.isPending}
              leftIcon={<Terminal size={16} />}
            >
              Diagnose Log with AI
            </Button>
          </form>
        </Card>

        {/* Diagnostic Results Card */}
        <Card title="AI Diagnostic & Root Cause" subtitle="Extracted evidence and fix recommendations">
          {analyzeMutation.isPending ? (
            <LoadingState message="Parsing log patterns and running AI agent..." />
          ) : analysisResult ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              {/* Header Risk & Type */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '0.85rem 1rem',
                  backgroundColor: 'var(--bg-elevated)',
                  borderRadius: 'var(--radius-md)',
                }}
              >
                <div>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontWeight: '600' }}>
                    FAILURE TYPE
                  </span>
                  <div style={{ fontSize: '1rem', fontWeight: '800', color: 'var(--text-primary)', textTransform: 'capitalize' }}>
                    {analysisResult.failure_type || analysisResult.log_type}
                  </div>
                </div>
                <RiskBadge level={analysisResult.risk_level || 'HIGH'} score={analysisResult.risk_score} size="md" />
              </div>

              {/* Root Cause Card */}
              {analysisResult.root_cause && (
                <div
                  style={{
                    padding: '0.85rem 1rem',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(239, 68, 68, 0.08)',
                    border: '1px solid rgba(239, 68, 68, 0.25)',
                  }}
                >
                  <div style={{ fontSize: '0.8125rem', fontWeight: '700', color: 'var(--danger)', marginBottom: '0.25rem' }}>
                    Root Cause:
                  </div>
                  <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    {analysisResult.root_cause}
                  </p>
                </div>
              )}

              {/* Fix Recommendations */}
              {analysisResult.fix_recommendations && analysisResult.fix_recommendations.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)', marginBottom: '0.5rem' }}>
                    Recommended Fixes:
                  </h4>
                  <ul style={{ paddingLeft: '1.25rem', fontSize: '0.8125rem', color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                    {analysisResult.fix_recommendations.map((rec, idx) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ) : (
            <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
              Click 'Diagnose Log with AI' to process the stack trace.
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
