import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { rolesApi } from '../../api/roles.api';
import { PageHeader } from '../../components/layout/PageHeader';
import { MetricCard } from '../../components/common/MetricCard';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import {
  ShieldCheck,
  CheckCircle2,
  Bug,
  AlertTriangle,
  MessageSquareQuote,
  Flame,
  ArrowRight,
} from 'lucide-react';

export function QADashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'qa'],
    queryFn: () => rolesApi.getQADashboard(),
  });

  if (isLoading) return <LoadingState message="Loading QA Engineering dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};

  return (
    <div>
      <PageHeader
        title="Quality & Test Engineering Dashboard"
        subtitle="Track test suite execution, regression risk, defect resolution, and software quality evidence."
        actions={
          <Button
            variant="primary"
            leftIcon={<MessageSquareQuote size={16} />}
            onClick={() => navigate('/feedback')}
          >
            Submit QA Feedback
          </Button>
        }
      />

      {/* Metrics Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '1.25rem',
          marginBottom: '1.75rem',
        }}
      >
        <MetricCard
          title="Test Pass Rate"
          value="98.4%"
          subtitle="1,420 test cases run"
          icon={<CheckCircle2 size={20} />}
          color="success"
        />
        <MetricCard
          title="Open Defects"
          value={summary.open_bugs || 0}
          subtitle={`${summary.critical_bugs || 0} critical defects`}
          icon={<Bug size={20} />}
          color={summary.critical_bugs > 0 ? 'danger' : 'primary'}
        />
        <MetricCard
          title="Regression Risk"
          value={summary.regression_risk || 'LOW'}
          subtitle="Release stability score"
          icon={<ShieldCheck size={20} />}
          color="cyan"
        />
        <MetricCard
          title="Flaky Tests"
          value="3"
          subtitle="Tests needing triage"
          icon={<Flame size={20} />}
          color="warning"
        />
      </div>

      {/* Main QA Content Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '1.5rem',
        }}
      >
        <Card
          title="Code Quality & Static Analysis"
          subtitle="Multi-language analyzer evidence"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/code-quality')}>
              Inspect Findings <ArrowRight size={14} />
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            The Intelligence Engine continuously monitors repository pull requests for security vulnerabilities,
            code smells, and complexity anomalies across all languages.
          </p>
          <div style={{ marginTop: '1.25rem' }}>
            <Button variant="primary" size="sm" onClick={() => navigate('/code-quality')}>
              Open Code Quality Module
            </Button>
          </div>
        </Card>

        <Card
          title="CI/CD Failure Diagnostic"
          subtitle="AI Agent log analyzer for broken builds and tests"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/cicd-logs')}>
              Open Diagnostic <ArrowRight size={14} />
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Paste failed test runner output or CI build logs to automatically detect root causes and get fix
            recommendations.
          </p>
          <div style={{ marginTop: '1.25rem' }}>
            <Button variant="secondary" size="sm" onClick={() => navigate('/cicd-logs')}>
              Analyze Test Logs with AI
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
