import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { ArrowRight, Briefcase, Download, TrendingUp, Layers, Award, ShieldCheck } from 'lucide-react';
import { canOpenPage } from '../../routes/access';
import { hasPermission, PERMISSIONS } from '../../auth/permissions';
import { reportsApi } from '../../api/reports.api';

/**
 * CR-011: each card links to the live page behind the report and, when the
 * backend lists the report for you, offers a CSV download. Downloads need a
 * short purpose, which the backend keeps in the audit log.
 */
const REPORTS = [
  {
    report: 'sprint_velocity',
    title: 'Sprint Velocity & Completion',
    description: 'Story points committed vs delivered across sprints.',
    icon: <Layers size={22} style={{ color: 'var(--cyan)' }} />,
    targets: [{ page: 'sprints', to: '/sprints' }],
  },
  {
    report: 'quality_trends',
    title: 'Engineering Quality & Static Analysis',
    description: 'Quality score, grade and risk for each analysis run.',
    icon: <ShieldCheck size={22} style={{ color: 'var(--success)' }} />,
    targets: [{ page: 'ceoQuality', to: '/quality' }, { page: 'codeQuality', to: '/code-quality' }],
  },
  {
    report: 'performance_distribution',
    title: 'Workforce Performance',
    description: 'Number of people per grade and team. Groups under 5 people are not shown exactly.',
    icon: <Award size={22} style={{ color: 'var(--purple)' }} />,
    targets: [{ page: 'performance', to: '/performance' }],
  },
  {
    report: 'delivery_risk',
    title: 'Delivery & Risk Governance',
    description: 'Project status with open, high and critical risks.',
    icon: <TrendingUp size={22} style={{ color: 'var(--primary)' }} />,
    targets: [{ page: 'ceoRisk', to: '/risk' }, { page: 'projects', to: '/projects' }],
  },
  {
    report: null,
    title: 'Project Portfolio',
    description: 'Status of every project you can access.',
    icon: <Briefcase size={22} style={{ color: 'var(--warning)' }} />,
    targets: [{ page: 'projects', to: '/projects' }],
  },
];

function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function readError(error) {
  const data = error?.response?.data;
  if (data instanceof Blob) {
    // A refused CSV download arrives as a Blob holding the JSON error.
    try {
      const text = typeof data.text === 'function'
        ? await data.text()
        : await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.onerror = reject;
          reader.readAsText(data);
        });
      return JSON.parse(text).detail;
    } catch {
      return null;
    }
  }
  return data?.detail || error?.message;
}

export function ReportsPage() {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const canExport = hasPermission(user, PERMISSIONS.EXPORT_DATA);
  const [purposes, setPurposes] = useState({});
  const [busy, setBusy] = useState(null);
  const [notice, setNotice] = useState(null);

  const available = useQuery({ queryKey: ['reports'], queryFn: reportsApi.list, enabled: canExport });
  const downloadable = new Set((available.data?.reports || []).map((r) => r.type));

  const reports = REPORTS
    .map((r) => ({
      ...r,
      target: r.targets.find((t) => canOpenPage(user, t.page)),
      canDownload: Boolean(r.report) && downloadable.has(r.report),
    }))
    .filter((r) => r.target || r.canDownload);

  const download = async (r) => {
    setBusy(r.report);
    setNotice(null);
    try {
      const blob = await reportsApi.downloadCsv(r.report, { purpose: purposes[r.report].trim() });
      saveBlob(blob, `${r.report}_${new Date().toISOString().slice(0, 10)}.csv`);
      setNotice({ tone: 'success', text: `${r.title} downloaded. The download is recorded in the audit log.` });
    } catch (error) {
      setNotice({ tone: 'danger', text: (await readError(error)) || 'The report could not be downloaded' });
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <PageHeader
        title="Reports & Analytics Center"
        subtitle="Open the live data behind each report, or download it as CSV where your role allows."
      />

      {notice && (
        <p role={notice.tone === 'danger' ? 'alert' : 'status'} style={{ color: `var(--${notice.tone})` }}>{notice.text}</p>
      )}
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

            <div style={{ marginTop: '1.5rem', paddingTop: '1rem', borderTop: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {r.canDownload && (
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                  <input
                    aria-label={`Purpose for downloading ${r.title}`}
                    placeholder="Purpose (kept in the audit log)"
                    value={purposes[r.report] || ''}
                    onChange={(event) => setPurposes({ ...purposes, [r.report]: event.target.value })}
                    style={{ flex: '1 1 160px', minWidth: 0, padding: '0.4rem 0.6rem' }}
                  />
                  <Button
                    variant="primary"
                    size="sm"
                    leftIcon={<Download size={14} />}
                    onClick={() => download(r)}
                    disabled={(purposes[r.report] || '').trim().length < 3 || busy === r.report}
                  >
                    Download CSV
                  </Button>
                </div>
              )}
              {r.target && (
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <Button
                    variant="secondary"
                    size="sm"
                    rightIcon={<ArrowRight size={14} />}
                    onClick={() => navigate(r.target.to)}
                  >
                    Open {r.title}
                  </Button>
                </div>
              )}
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
