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
import { BarList, SegmentedBar } from '../../components/charts/Charts';
import { DEFAULT_ORG_ID } from '../../utils/constants';
import '../../components/dashboard/Dashboard.css';
import {
  TrendingUp,
  FolderGit2,
  ShieldAlert,
  Siren,
  Award,
  FileBarChart,
  Activity,
  Sparkles,
} from 'lucide-react';

/* A plain summary written from the figures on this page. */
function portfolioSummary({ total, healthy, atRisk, critical, incidents }) {
  if (!total) return 'No active projects yet.';
  const parts = [`${healthy} of ${total} projects risk-free`];
  if (critical) parts.push(`${critical} critical`);
  else if (atRisk) parts.push(`${atRisk} with open risks`);
  if (incidents) parts.push(`${incidents} open incident${incidents === 1 ? '' : 's'}`);
  return `${parts.join(' · ')}.`;
}

export function CEODashboardPage() {
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['role-dashboard', 'ceo'],
    queryFn: () => rolesApi.getCEODashboard(),
  });
  const { data: executionHealth } = useQuery({
    queryKey: ['ceo-execution-health', DEFAULT_ORG_ID],
    queryFn: () => rolesApi.getExecutionHealth(DEFAULT_ORG_ID),
  });

  if (isLoading) return <LoadingState message="Loading the executive dashboard..." />;
  if (error) return <ErrorState message={error.message} onRetry={refetch} />;

  const organizationHealth = data?.organization_health || {};
  const projects = executionHealth?.projects || [];
  const total = executionHealth?.total_projects ?? organizationHealth.total_projects ?? 0;
  const critical = projects.filter((project) => project.critical_risks > 0).length;
  const healthy = executionHealth
    ? projects.filter((project) => !project.open_risks).length
    : organizationHealth.healthy_projects ?? 0;
  const atRisk = executionHealth
    ? projects.length - healthy - critical
    : organizationHealth.at_risk_projects ?? 0;
  const incidents = data?.active_incidents ?? 0;

  return (
    <div className="dash">
      <PageHeader
        title="Executive overview"
        subtitle="Organisation-wide delivery and risk."
        actions={
          <Button variant="primary" leftIcon={<FileBarChart size={16} />} onClick={() => navigate('/reports')}>
            Executive reports
          </Button>
        }
      />

      <div className="dash-kpis">
        <MetricCard
          title="Delivery confidence"
          value={data?.delivery_confidence ?? '—'}
          subtitle="Active sprint average"
          icon={<TrendingUp size={18} />}
          color="success"
        />
        <MetricCard
          title="Active projects"
          value={total}
          subtitle={`${healthy} risk-free`}
          icon={<FolderGit2 size={18} />}
          color="primary"
          onClick={() => navigate('/projects')}
        />
        <MetricCard
          title="Critical risks"
          value={data?.critical_risks ?? 0}
          subtitle="All projects"
          icon={<ShieldAlert size={18} />}
          color={data?.critical_risks > 0 ? 'danger' : 'success'}
        />
        <MetricCard
          title="Open incidents"
          value={incidents}
          subtitle="Currently open"
          icon={<Siren size={18} />}
          color={incidents > 0 ? 'warning' : 'success'}
        />
      </div>

      <div className="dash-row dash-row--wide">
        <Card title="Portfolio health" subtitle="By highest open risk">
          <SegmentedBar
            label="Portfolio health"
            emptyText="No active projects yet."
            parts={[
              { label: 'No open risks', value: healthy, tone: 'good' },
              { label: 'Open risks', value: atRisk, tone: 'warning' },
              { label: 'Critical risk', value: critical, tone: 'critical' },
            ]}
          />
          <h4 className="dash-sub">Open risks by project</h4>
          <BarList
            label="Open risks"
            emptyText="No open risks."
            items={projects.map((project) => ({
              key: project.project_id,
              label: project.name,
              value: project.open_risks,
              tone: project.critical_risks > 0 ? 'critical' : 'warning',
              note: project.critical_risks ? `${project.critical_risks} critical` : undefined,
            }))}
            onSelect={(item) => navigate(`/projects/${item.key}`)}
          />
        </Card>

        <div className="dash-stack">
          <Card title="Summary">
            <div className="dash-note">
              <Sparkles size={18} aria-hidden="true" />
              <div>
                {portfolioSummary({ total, healthy, atRisk, critical, incidents })}
              </div>
            </div>
          </Card>
          <Card title="Quick actions">
            <div className="dash-actions">
              <Button variant="secondary" leftIcon={<Award size={16} />} onClick={() => navigate('/performance')}>
                Performance reviews
              </Button>
              <Button variant="secondary" leftIcon={<Activity size={16} />} onClick={() => navigate('/reports')}>
                Reports
              </Button>
              <Button variant="secondary" leftIcon={<FolderGit2 size={16} />} onClick={() => navigate('/projects')}>
                Project portfolio
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
