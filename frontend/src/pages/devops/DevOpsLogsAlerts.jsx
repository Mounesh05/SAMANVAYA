import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { FileText, AlertTriangle, Shield, AlertOctagon, Cpu, Bell, Clock } from 'lucide-react';
import { devopsAPI } from '../../services/api';

const categories = ['All', 'Error', 'Warning', 'Security', 'Memory'];
const severityConfig = {
    Critical: { bg: '#fef2f2', color: '#dc2626', border: '#ef4444' },
    High: { bg: '#fff7ed', color: '#ea580c', border: '#f97316' },
    Medium: { bg: '#fffbeb', color: '#d97706', border: '#f59e0b' },
    Low: { bg: '#f0fdf4', color: '#16a34a', border: '#22c55e' },
};

const categoryIcon = {
    Error: <AlertOctagon size={14} />,
    Warning: <AlertTriangle size={14} />,
    Security: <Shield size={14} />,
    Memory: <Bell size={14} />,
};

export default function DevOpsLogsAlerts() {
    const [logs, setLogs] = useState([]);
    const [aiAnalysis, setAiAnalysis] = useState([]);
    const [filter, setFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            devopsAPI.logsAlerts().catch(() => []),
            devopsAPI.logsMetrics().catch(() => ({})),
        ]).then(([logData, metricData]) => {
            if (Array.isArray(logData)) setLogs(logData);
            if (metricData?.ai_analysis) setAiAnalysis(metricData.ai_analysis);
        }).catch(err => {
            console.error('Failed to load logs or metrics', err);
        }).finally(() => setLoading(false));
    }, []);

    const filtered = filter === 'All' ? logs : logs.filter(l => l.category === filter);
    const criticalCount = logs.filter(l => l.severity === 'Critical').length;
    const highCount = logs.filter(l => l.severity === 'High').length;
    const securityCount = logs.filter(l => l.category === 'Security').length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<FileText size={24} />} value={logs.length} label="Total Logs" color="blue" delay={0} />
                <StatsCard icon={<AlertOctagon size={24} />} value={criticalCount} label="Critical" color="red" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={highCount} label="High Severity" color="orange" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={securityCount} label="Security Alerts" color="red" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Logs & Alerts</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                        {categories.map(c => (
                            <button key={c} onClick={() => setFilter(c)}
                                style={{
                                    padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                    background: filter === c ? 'var(--brand-primary)' : 'var(--bg-page)',
                                    color: filter === c ? '#fff' : 'var(--text-secondary)',
                                    border: filter === c ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s ease'
                                }}>{c}</button>
                        ))}
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Category</th><th>Severity</th><th>Service</th>
                                    <th>Message</th><th>Timestamp</th><th>Count</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={6} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No logs found matching "{filter}".
                                        </td>
                                    </tr>
                                )}
                                {filtered.map(l => {
                                    const sev = severityConfig[l.severity] || severityConfig.Low;
                                    return (
                                        <tr key={l.id || l._id} style={{ background: l.severity === 'Critical' ? '#fef2f210' : 'transparent' }}>
                                            <td>
                                                <span style={{
                                                    display: 'flex', alignItems: 'center', gap: 6, fontWeight: 600, fontSize: '0.82rem',
                                                    color: l.category === 'Error' ? '#ef4444' : l.category === 'Security' ? '#7c3aed' : l.category === 'Memory' ? '#f59e0b' : '#6b7280'
                                                }}>
                                                    {categoryIcon[l.category] || <AlertTriangle size={14} />} {l.category}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="badge" style={{ background: sev.bg, color: sev.color, border: `1px solid ${sev.border}` }}>
                                                    {l.severity}
                                                </span>
                                            </td>
                                            <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{l.service}</td>
                                            <td style={{ fontSize: '0.82rem', maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                {l.message}
                                            </td>
                                            <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                                                <Clock size={11} style={{ display: 'inline', marginRight: 4 }} />{l.timestamp}
                                            </td>
                                            <td>
                                                <span style={{ fontWeight: 700, fontSize: '0.82rem', color: l.count > 10 ? '#ef4444' : 'var(--text-secondary)' }}>
                                                    {l.count}
                                                </span>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {aiAnalysis.length > 0 && (
                <AnimatedCard delay={0.4} style={{ marginTop: 16 }}>
                    <div className="card-header">
                        <span className="card-title">AI Log Analyzer</span>
                        <span className="badge badge-info"><Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />AI</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {aiAnalysis.map((ai, i) => (
                            <div key={i} style={{
                                padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                                background: ai.type === 'danger' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                                borderLeft: `3px solid ${ai.type === 'danger' ? 'var(--danger)' : 'var(--warning)'}`,
                            }}>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'flex-start', gap: 6 }}>
                                    <Cpu size={14} style={{ flexShrink: 0, marginTop: 2 }} /> {ai.text}
                                </div>
                            </div>
                        ))}
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
