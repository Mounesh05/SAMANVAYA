import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { ArrowRight, Briefcase, TrendingUp, Layers, Award, ShieldCheck } from 'lucide-react';
import { canOpenPage } from '../../routes/access';

/**
 * CR-007: there is no reports backend yet, so this page no longer offers a
 * download (it used to export a hardcoded CSV). Each report links to the live
 * page that holds its data, and is shown only to people who can open that page
 * (the first target the user can open is used).
 */
const REPORTS = [
  {
    title: 'Sprint Velocity & Completion',
    description: 'Story points committed vs delivered across sprints.',
    icon: <Layers size={22} style={{ color: 'var(--cyan)' }} />,
    targets: [{ page: 'sprints', to: '/sprints' }],
  },
  {
    title: 'Engineering Quality & Static Analysis',
    description: 'Defect density, security findings, and code maintainability.',
    icon: <ShieldCheck size={22} style={{ color: 'var(--success)' }} />,
    targets: [{ page: 'ceoQuality', to: '/quality' }, { page: 'codeQuality', to: '/code-quality' }],
  },
  {
    title: 'Workforce Performance',
    description: 'Performance outcomes within your access scope.',
    icon: <Award size={22} style={{ color: 'var(--purple)' }} />,
    targets: [{ page: 'performance', to: '/performance' }],
  },
  {
    title: 'Delivery & Risk Governance',
    description: 'Project health, delivery confidence, and active risks.',
    icon: <TrendingUp size={22} style={{ color: 'var(--primary)' }} />,
    targets: [{ page: 'ceoRisk', to: '/risk' }],
  },
  {
    title: 'Project Portfolio',
    description: 'Status of every project you can access.',
    icon: <Briefcase size={22} style={{ color: 'var(--warning)' }} />,
    targets: [{ page: 'projects', to: '/projects' }],
  },
];

export function ReportsPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const reports = REPORTS
    .map((r) => ({ ...r, target: r.targets.find((t) => canOpenPage(user, t.page)) }))
    .filter((r) => r.target);

  return (
    <div>
      <PageHeader
        title="Reports & Analytics Center"
        subtitle="Open the live data behind each report. Downloadable reports need a reports backend and are not available yet."
      />

      {reports.length === 0 && (
        <p style={{ color: 'var(--text-muted)' }}>No reports are available for your role.</p>
      )}

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {reports.map((r) => (
          <Card key={r.title} padding="lg" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div
                style={{
                  width: '44px',
                  height: '44px',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--bg-elevated)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginBottom: '1rem',
                }}
              >
                {r.icon}
              </div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                {r.title}
              </h3>
              <p style={{ fontSize: '0.8125rem', color: 'var(--text-muted)', marginTop: '0.4rem', lineHeight: '1.5' }}>
                {r.description}
              </p>
            </div>

            <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end' }}>
              <Button
                variant="secondary"
                size="sm"
                rightIcon={<ArrowRight size={14} />}
                onClick={() => navigate(r.target.to)}
              >
                Open {r.title}
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
