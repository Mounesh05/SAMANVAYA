import React, { useMemo } from 'react';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { FileBarChart, Download, TrendingUp, Layers, Award, ShieldCheck } from 'lucide-react';
import { ROLES } from '../../utils/constants';

export function ReportsPage() {
  const { user } = useAuthStore();
  const role = user?.role?.toUpperCase();

  const allReports = [
    {
      title: 'Sprint Velocity & Completion Report',
      description: 'Historical story points committed vs delivered across sprints.',
      icon: <Layers size={22} style={{ color: 'var(--cyan)' }} />,
      type: 'sprint_velocity',
      roles: [ROLES.PM, ROLES.LEAD, ROLES.DEVELOPER, ROLES.QA],
    },
    {
      title: 'Engineering Quality & Static Analysis Trends',
      description: 'Defect density, security vulnerability rate, and code maintainability metrics.',
      icon: <ShieldCheck size={22} style={{ color: 'var(--success)' }} />,
      type: 'quality_trends',
      roles: [ROLES.DEVELOPER, ROLES.LEAD, ROLES.QA, ROLES.DEVOPS],
    },
    {
      title: 'Workforce Performance Distribution Report',
      description: 'Individual and team-level performance breakdowns and AI evaluation summaries.',
      icon: <Award size={22} style={{ color: 'var(--purple)' }} />,
      type: 'performance_distribution',
      roles: [ROLES.HR, ROLES.CEO],
    },
    {
      title: 'Project Delivery & Risk Governance Summary',
      description: 'Executive overview of project health, delivery confidence, and active impediments.',
      icon: <TrendingUp size={22} style={{ color: 'var(--primary)' }} />,
      type: 'delivery_risk',
      roles: [ROLES.PM, ROLES.LEAD, ROLES.CEO],
    },
  ];

  const reports = useMemo(() => {
    return allReports.filter((r) => r.roles.includes(role));
  }, [role]);

  const handleExportCSV = (reportName) => {
    const csvContent = 'data:text/csv;charset=utf-8,Metric,Value,Date\nVelocity,42,2026-08-30\nPass Rate,98.4%,2026-08-30\nQuality Score,88,2026-08-30';
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', `${reportName}_report.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div>
      <PageHeader
        title="Reports & Analytics Center"
        subtitle="Generate authoritative reports, export analytics data, and audit organizational metrics."
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {reports.map((r) => (
          <Card key={r.type} padding="lg" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
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

            <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <Button
                variant="secondary"
                size="sm"
                leftIcon={<Download size={14} />}
                onClick={() => handleExportCSV(r.type)}
              >
                Export CSV
              </Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
