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
  Terminal,
  Activity,
  Server,
  AlertTriangle,
  MessageSquareQuote,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react';

export function DevOpsDashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'devops'],
    queryFn: () => rolesApi.getDevOpsDashboard(),
  });

  if (isLoading) return <LoadingState message="Loading DevOps Engineering dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const summary = data?.summary || {};

  return (
    <div>
      <PageHeader
        title="DevOps & Reliability Dashboard"
        subtitle="CI/CD pipeline metrics, deployment telemetry, live infrastructure status, and AI log diagnostics."
        actions={
          <Button
            variant="primary"
            leftIcon={<MessageSquareQuote size={16} />}
            onClick={() => navigate('/feedback')}
          >
            Submit DevOps Feedback
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
          title="Pipeline Health"
          value="99.2%"
          subtitle="Build & release pipelines"
          icon={<Activity size={20} />}
          color="success"
        />
        <MetricCard
          title="Deployments Today"
          value="14"
          subtitle="Automated canary & prod"
          icon={<Server size={20} />}
          color="cyan"
        />
        <MetricCard
          title="Active Incidents"
          value={summary.active_incidents || 0}
          subtitle="Severity 1 & 2 incidents"
          icon={<AlertTriangle size={20} />}
          color={summary.active_incidents > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          title="System Health"
          value={summary.system_health || 'HEALTHY'}
          subtitle="Cluster & infra status"
          icon={<ShieldCheck size={20} />}
          color="primary"
        />
      </div>

      {/* Main DevOps Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '1.5rem',
        }}
      >
        <Card
          title="AI CI/CD Log Analyzer"
          subtitle="Automated failure diagnosis using Layer 5 + Layer 6 agents"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/cicd-logs')}>
              Open Analyzer <ArrowRight size={14} />
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Paste stack traces or raw build logs from Docker, Kubernetes, GitHub Actions, or Jenkins to extract
            evidence, identify affected components, and receive actionable remediation suggestions.
          </p>
          <div style={{ marginTop: '1.25rem' }}>
            <Button variant="primary" size="sm" leftIcon={<Terminal size={16} />} onClick={() => navigate('/cicd-logs')}>
              Analyze Build / Deployment Log
            </Button>
          </div>
        </Card>

        <Card
          title="Code Security & Dependency Risks"
          subtitle="Static analysis across repositories"
          action={
            <Button variant="ghost" size="sm" onClick={() => navigate('/code-quality')}>
              View Report <ArrowRight size={14} />
            </Button>
          }
        >
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            Inspect security vulnerabilities and deployment risks detected across Java, C++, TypeScript, and Python codebases.
          </p>
          <div style={{ marginTop: '1.25rem' }}>
            <Button variant="secondary" size="sm" onClick={() => navigate('/code-quality')}>
              Inspect Quality & Vulnerabilities
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
