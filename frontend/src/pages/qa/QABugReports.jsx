import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Bug, AlertTriangle, AlertOctagon, RefreshCw, Image, FileText, Monitor } from 'lucide-react';
import { qaAPI } from '../../services/api';

const severityConfig = {
    Critical: { bg: '#fef2f2', color: '#dc2626', icon: '🔴' },
    High: { bg: '#fff7ed', color: '#ea580c', icon: '🟠' },
    Medium: { bg: '#fffbeb', color: '#d97706', icon: '🟡' },
    Low: { bg: '#f0fdf4', color: '#16a34a', icon: '🟢' },
};

const statusBadge = {
    Open: { bg: '#fef2f2', color: '#ef4444' },
    'In Progress': { bg: '#eff6ff', color: '#3b82f6' },
    Resolved: { bg: '#ecfdf5', color: '#10b981' },
    Reopened: { bg: '#f5f3ff', color: '#7c3aed' },
};

export default function QABugReports() {
    const [bugs, setBugs] = useState([]);
    const [expanded, setExpanded] = useState(null);
    const [filter, setFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        qaAPI.bugReports().then(data => { if (data?.length) setBugs(data); })
            .catch(err => console.error('Failed to fetch bug reports:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading bug reports...</div>;

    const severities = ['All', 'Critical', 'High', 'Medium', 'Low'];
    const filtered = filter === 'All' ? bugs : bugs.filter(b => b.severity === filter);
    const openCount = bugs.filter(b => b.status === 'Open').length;
    const criticalCount = bugs.filter(b => b.severity === 'Critical').length;
    const reopenedCount = bugs.filter(b => b.reopenCount > 0).length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Bug size={24} />} value={bugs.length} label="Total Bugs" color="blue" delay={0} />
                <StatsCard icon={<AlertOctagon size={24} />} value={criticalCount} label="Critical" color="red" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={openCount} label="Open" color="orange" delay={0.16} />
                <StatsCard icon={<RefreshCw size={24} />} value={reopenedCount} label="With Reopens" color="red" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Bug Reports</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                        {severities.map(s => (
                            <button key={s} onClick={() => setFilter(s)} style={{
                                padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                background: filter === s ? 'var(--brand-primary)' : 'var(--bg-page)',
                                color: filter === s ? '#fff' : 'var(--text-secondary)',
                                border: filter === s ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s ease'
                            }}>{s}</button>
                        ))}
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>Bug ID</th><th>Story</th><th>Severity</th><th>Status</th><th>Assigned To</th><th>Reopen</th><th>Attachments</th><th></th></tr>
                            </thead>
                            <tbody>
                                {filtered.map(b => {
                                    const sev = severityConfig[b.severity];
                                    const st = statusBadge[b.status];
                                    return (
                                        <>
                                            <tr key={b.id} onClick={() => setExpanded(expanded === b.id ? null : b.id)} style={{ cursor: 'pointer' }}>
                                                <td style={{ fontWeight: 700, fontFamily: "'Courier New', monospace", fontSize: '0.82rem' }}>{b.id}</td>
                                                <td style={{ fontWeight: 600, fontSize: '0.82rem' }}>{b.story}</td>
                                                <td><span className="badge" style={{ background: sev.bg, color: sev.color }}>{sev.icon} {b.severity}</span></td>
                                                <td><span className="badge" style={{ background: st.bg, color: st.color }}>{b.status}</span></td>
                                                <td style={{ fontSize: '0.82rem' }}>{b.assignedTo}</td>
                                                <td>
                                                    {b.reopenCount > 0 ? (
                                                        <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '0.82rem' }}>{b.reopenCount}x</span>
                                                    ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>}
                                                </td>
                                                <td>
                                                    <div style={{ display: 'flex', gap: 6 }}>
                                                        {b.hasScreenshot && <Image size={14} style={{ color: '#3b82f6' }} title="Screenshot" />}
                                                        {b.hasLogs && <FileText size={14} style={{ color: '#8b5cf6' }} title="Logs" />}
                                                        {!b.hasScreenshot && !b.hasLogs && <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>}
                                                    </div>
                                                </td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>{expanded === b.id ? '▲' : '▼'}</td>
                                            </tr>
                                            {expanded === b.id && (
                                                <tr key={`${b.id}-detail`}>
                                                    <td colSpan={8} style={{ padding: 0 }}>
                                                        <div style={{ padding: '16px 20px', background: 'var(--bg-page)', borderTop: '1px solid var(--border-light)' }}>
                                                            <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 6 }}>{b.summary}</div>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 12 }}>
                                                                <Monitor size={13} style={{ color: 'var(--text-tertiary)' }} />
                                                                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>Environment: <strong>{b.env}</strong></span>
                                                            </div>
                                                            <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Reproduction Steps</div>
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                                                {b.steps.map((s, i) => (
                                                                    <div key={i} style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', paddingLeft: 8 }}>{s}</div>
                                                                ))}
                                                            </div>
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
