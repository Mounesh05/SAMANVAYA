import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { AlertOctagon, Clock, CheckCircle, XCircle, Cpu, Search, Activity } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { devopsAPI } from '../../services/api';

const severityConfig = {
    Critical: { bg: '#fef2f2', color: '#dc2626', icon: '🔴' },
    High: { bg: '#fff7ed', color: '#ea580c', icon: '🟠' },
    Medium: { bg: '#fffbeb', color: '#d97706', icon: '🟡' },
    Low: { bg: '#f0fdf4', color: '#16a34a', icon: '🟢' },
};

const parseMinutes = (str) => {
    if (!str) return 0;
    if (typeof str === 'number') return str;
    let total = 0;
    const hMatch = str.match(/(\d+)\s*h/);
    const mMatch = str.match(/(\d+)\s*m/);
    if (hMatch) total += parseInt(hMatch[1], 10) * 60;
    if (mMatch) total += parseInt(mMatch[1], 10);
    return total || 0;
};

export default function DevOpsIncidents() {
    const [incidents, setIncidents] = useState([]);
    const [expanded, setExpanded] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        devopsAPI.incidents()
            .then(data => {
                if (Array.isArray(data)) setIncidents(data);
            })
            .catch(err => console.error('Failed to load incidents:', err))
            .finally(() => setLoading(false));
    }, []);

    const criticalCount = incidents.filter(i => i.severity === 'Critical').length;
    const repeatCount = incidents.filter(i => i.repeat).length;
    const mttrData = incidents.map(inc => ({
        id: inc.id,
        mttr: parseMinutes(inc.mttr)
    }));
    const avgMttr = mttrData.length ? Math.round(mttrData.reduce((a, m) => a + m.mttr, 0) / mttrData.length) : 0;
    const mttdMinutes = incidents.map(i => parseMinutes(i.mttd));
    const avgMttdVal = mttdMinutes.length ? Math.round(mttdMinutes.reduce((a, m) => a + m, 0) / mttdMinutes.length) : 0;
    const avgMttd = `${avgMttdVal}m`;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<AlertOctagon size={24} />} value={incidents.length} label="Total Incidents" color="blue" delay={0} />
                <StatsCard icon={<XCircle size={24} />} value={criticalCount} label="Critical" color="red" delay={0.08} />
                <StatsCard icon={<Clock size={24} />} value={`${avgMttr}m`} label="Avg MTTR" color="orange" delay={0.16} />
                <StatsCard icon={<Search size={24} />} value={avgMttd} label="Avg MTTD" color="green" delay={0.24} />
            </div>

            {repeatCount > 0 && (
                <AnimatedCard delay={0.28} style={{ marginBottom: 12 }}>
                    <div style={{
                        padding: '14px 20px', background: '#fffbeb', borderRadius: 'var(--radius-md)', borderLeft: '4px solid #f59e0b',
                        display: 'flex', alignItems: 'center', gap: 12
                    }}>
                        <Activity size={20} style={{ color: '#f59e0b', flexShrink: 0 }} />
                        <div>
                            <span style={{ fontWeight: 700, fontSize: '0.88rem', color: '#92400e' }}>Repeat Incident Alert:</span>
                            <span style={{ fontSize: '0.85rem', color: '#78350f', marginLeft: 6 }}>{repeatCount} incident(s) are recurring. Root cause analysis recommended.</span>
                        </div>
                    </div>
                </AnimatedCard>
            )}

            <AnimatedCard delay={0.35}>
                <div className="card-header">
                    <span className="card-title">Incidents</span>
                    <span className="badge badge-danger">{incidents.length} total</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>ID</th><th>Incident</th><th>Severity</th><th>Service</th>
                                    <th>Opened</th><th>Resolved</th><th>MTTD</th><th>MTTR</th><th>Repeat</th><th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {incidents.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={10} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No incidents recorded.
                                        </td>
                                    </tr>
                                )}
                                {incidents.map(inc => {
                                    const sev = severityConfig[inc.severity] || severityConfig.Low;
                                    return (
                                        <tbody key={inc.id}>
                                            <tr onClick={() => setExpanded(expanded === inc.id ? null : inc.id)}
                                                style={{ cursor: 'pointer', background: inc.severity === 'Critical' ? '#fef2f210' : 'transparent' }}>
                                                <td><span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{inc.id}</span></td>
                                                <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{inc.incident || inc.title}</td>
                                                <td>
                                                    <span className="badge" style={{ background: sev.bg, color: sev.color }}>
                                                        {sev.icon} {inc.severity}
                                                    </span>
                                                </td>
                                                <td style={{ fontWeight: 600, fontSize: '0.82rem' }}>{inc.service}</td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{inc.openedAt || inc.created_at}</td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{inc.resolvedAt || 'Active'}</td>
                                                <td><span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>{inc.mttd}</span></td>
                                                <td><span className="badge badge-neutral" style={{ fontSize: '0.72rem' }}>{inc.mttr}</span></td>
                                                <td>
                                                    {inc.repeat ? (
                                                        <span style={{ color: '#ef4444', fontWeight: 700, fontSize: '0.78rem' }}>⚠️ Yes</span>
                                                    ) : (
                                                        <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.78rem' }}>No</span>
                                                    )}
                                                </td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>{expanded === inc.id ? '▲' : '▼'}</td>
                                            </tr>
                                            {expanded === inc.id && (
                                                <tr key={`${inc.id}-detail`}>
                                                    <td colSpan={10} style={{ padding: 0 }}>
                                                        <div style={{ padding: '16px 20px', background: 'var(--bg-page)', borderTop: '1px solid var(--border-light)' }}>
                                                            <div style={{ marginBottom: 10 }}>
                                                                <span style={{ fontWeight: 700, fontSize: '0.82rem' }}>Root Cause: </span>
                                                                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{inc.rootCause}</span>
                                                            </div>
                                                            {inc.aiSummary && (
                                                                <div style={{
                                                                    padding: '10px 14px', borderRadius: 'var(--radius-sm)',
                                                                    background: 'var(--warning-bg)', borderLeft: '3px solid var(--warning)',
                                                                    fontSize: '0.82rem', display: 'flex', alignItems: 'flex-start', gap: 6
                                                                }}>
                                                                    <Cpu size={14} style={{ flexShrink: 0, marginTop: 2 }} />
                                                                    <div><strong>AI Root Cause Summary:</strong> {inc.aiSummary}</div>
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {mttrData.length > 0 && (
                <AnimatedCard delay={0.45} style={{ marginTop: 16 }}>
                    <div className="card-header"><span className="card-title">Mean Time To Resolve (MTTR)</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={mttrData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="id" tick={{ fontSize: 11 }} />
                                    <YAxis tick={{ fontSize: 12 }} label={{ value: 'Minutes', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }} />
                                    <Tooltip formatter={(v) => [`${v} min`, 'MTTR']} />
                                    <Bar dataKey="mttr" radius={[4, 4, 0, 0]} name="MTTR (min)">
                                        {mttrData.map((d, i) => (
                                            <Cell key={i} fill={d.mttr > 120 ? '#ef4444' : d.mttr > 60 ? '#f59e0b' : '#10b981'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
