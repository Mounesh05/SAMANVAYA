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
  TrendingUp,
  FolderGit2,
  ShieldAlert,
  Award,
  Sparkles,
  ArrowRight,
  FileBarChart,
  Activity,
} from 'lucide-react';

export function CEODashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'ceo'],
    queryFn: () => rolesApi.getCEODashboard(),
  });

  if (isLoading) return <LoadingState message="Loading Executive CEO dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  return (
    <div>
      <PageHeader
        title="Executive Strategy & Governance Dashboard"
        subtitle="High-level visibility into company-wide project delivery, quality risk index, and talent health."
        actions={
          <Button
            variant="primary"
            leftIcon={<FileBarChart size={16} />}
            onClick={() => navigate('/reports')}
          >
            Executive Reports
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
          title="Delivery Confidence"
          value={data?.delivery_confidence || '82%'}
          subtitle="Portfolio roadmap alignment"
          icon={<TrendingUp size={20} />}
          color="success"
        />
        <MetricCard
          title="Active Projects"
          value="6"
          subtitle="All strategic initiatives"
          icon={<FolderGit2 size={20} />}
          color="primary"
          onClick={() => navigate('/projects')}
        />
        <MetricCard
          title="Critical Risks"
          value={data?.critical_risks || 0}
          subtitle="Company-level impediments"
          icon={<ShieldAlert size={20} />}
          color={data?.critical_risks > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          title="Engineering Health"
          value="88.2%"
          subtitle="Weighted quality index"
          icon={<Award size={20} />}
          color="purple"
          onClick={() => navigate('/code-quality')}
        />
      </div>

      {/* Strategic AI Summary & Health Cards */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))',
          gap: '1.5rem',
          marginBottom: '1.75rem',
        }}
      >
        <Card
          title="Executive AI Insights"
          subtitle="Strategic synthesis from Layer 5 and Layer 6 intelligence engines"
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            <div
              style={{
                padding: '0.85rem 1.15rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(168, 85, 247, 0.08)',
                border: '1px solid rgba(168, 85, 247, 0.2)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '0.75rem',
              }}
            >
              <Sparkles size={20} style={{ color: 'var(--purple)', flexShrink: 0, marginTop: '2px' }} />
              <div>
                <div style={{ fontSize: '0.875rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                  Delivery Pace & Quality Balance
                </div>
                <p style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)', marginTop: '0.25rem', lineHeight: '1.5' }}>
                  Delivery cadence across active engineering teams is maintaining strong velocity. Code quality metrics
                  reflect low regression risk across current sprint deliverables.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <Button variant="secondary" size="sm" onClick={() => navigate('/projects')}>
                Inspect Project Portfolio
              </Button>
              <Button variant="ghost" size="sm" onClick={() => navigate('/performance')}>
                View Organization Performance
              </Button>
            </div>
          </div>
        </Card>

        <Card title="Quick Governance Actions" subtitle="Key executive operations">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
            <Button
              variant="secondary"
              leftIcon={<Award size={16} />}
              onClick={() => navigate('/performance')}
              style={{ justifyContent: 'flex-start' }}
            >
              Review Organization Performance & AI Evaluations
            </Button>
            <Button
              variant="secondary"
              leftIcon={<Activity size={16} />}
              onClick={() => navigate('/reports')}
              style={{ justifyContent: 'flex-start' }}
            >
              Generate Formal Performance & Delivery Reports
            </Button>
            <Button
              variant="secondary"
              leftIcon={<FolderGit2 size={16} />}
              onClick={() => navigate('/projects')}
              style={{ justifyContent: 'flex-start' }}
            >
              Create Strategic Business Project
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
