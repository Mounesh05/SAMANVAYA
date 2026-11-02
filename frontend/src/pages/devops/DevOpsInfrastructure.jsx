import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Server, AlertTriangle, Shield, Clock, AlertOctagon } from 'lucide-react';
import { devopsAPI } from '../../services/api';

const riskConfig = {
    Low: { bg: '#ecfdf5', color: '#10b981', label: '🟢 Low' },
    Medium: { bg: '#fffbeb', color: '#f59e0b', label: '🟡 Medium' },
    High: { bg: '#fef2f2', color: '#ef4444', label: '🔴 High' },
};

const typeIcons = {
    'Docker Config Update': '🐳',
    'Kubernetes Scaling': '☸️',
    'Environment Variable': '🔑',
    'Terraform Modification': '🏗️',
};

export default function DevOpsInfrastructure() {
    const [changes, setChanges] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        devopsAPI.infrastructure()
            .then(data => {
                if (Array.isArray(data)) setChanges(data);
            })
            .catch(err => console.error('Failed to load infra changes:', err))
            .finally(() => setLoading(false));
    }, []);

    const highRisk = changes.filter(c => c.risk === 'High').length;
    const unauthorized = changes.filter(c => !c.approved).length;
    const driftDetected = changes.filter(c => (c.details || '').toLowerCase().includes('drift')).length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Server size={24} />} value={changes.length} label="Total Changes" color="blue" delay={0} />
                <StatsCard icon={<AlertTriangle size={24} />} value={highRisk} label="High Risk" color="red" delay={0.08} />
                <StatsCard icon={<AlertOctagon size={24} />} value={unauthorized} label="Unauthorized" color="red" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={driftDetected} label="Drift Detected" color="orange" delay={0.24} />
            </div>

            {/* Alert Banners */}
            {changes.filter(c => !c.approved).map((c, idx) => (
                <AnimatedCard key={c.id || idx} delay={0.28} style={{ marginBottom: 12, border: '1px solid #fecaca' }}>
                    <div style={{
                        padding: '14px 20px', background: '#fef2f2', borderRadius: 'var(--radius-md)',
                        display: 'flex', alignItems: 'center', gap: 12
                    }}>
                        <AlertOctagon size={20} style={{ color: '#ef4444', flexShrink: 0 }} />
                        <div style={{ flex: 1 }}>
                            <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#991b1b' }}>
                                ⚠️ {c.approved === false ? 'Unauthorized Change Alert' : 'Drift Detection'}
                            </div>
                            <div style={{ fontSize: '0.82rem', color: '#b91c1c', marginTop: 2 }}>
                                {c.type} on <strong>{c.service}</strong> by {c.changedBy} — {c.details}
                            </div>
                        </div>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', flexShrink: 0 }}>{c.timestamp}</span>
                    </div>
                </AnimatedCard>
            ))}

            <AnimatedCard delay={0.35}>
                <div className="card-header">
                    <span className="card-title">Infrastructure Changes</span>
                    <span className="badge badge-info">{changes.length} changes</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Change Type</th><th>Service</th><th>Changed By</th>
                                    <th>Timestamp</th><th>Risk Level</th><th>Approved</th><th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {changes.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No infrastructure change events recorded.
                                        </td>
                                    </tr>
                                )}
                                {changes.map((c, i) => {
                                    const risk = riskConfig[c.risk] || riskConfig.Low;
                                    return (
                                        <tr key={c.id || i} style={{ background: !c.approved ? '#fef2f220' : 'transparent' }}>
                                            <td>
                                                <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                                                    {typeIcons[c.type] || '📦'} {c.type}
                                                </span>
                                            </td>
                                            <td style={{ fontWeight: 600, fontSize: '0.82rem' }}>{c.service}</td>
                                            <td style={{ fontSize: '0.82rem', color: c.changedBy === 'Unknown' ? '#ef4444' : 'var(--text-primary)' }}>
                                                {c.changedBy}
                                            </td>
                                            <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{c.timestamp}</td>
                                            <td>
                                                <span className="badge" style={{ background: risk.bg, color: risk.color }}>{risk.label}</span>
                                            </td>
                                            <td>
                                                {c.approved ? (
                                                    <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        <Shield size={13} /> Yes
                                                    </span>
                                                ) : (
                                                    <span style={{ color: '#ef4444', fontWeight: 600, fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        <AlertOctagon size={13} /> No
                                                    </span>
                                                )}
                                            </td>
                                            <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', maxWidth: 250 }}>{c.details}</td>
                                        </tr>
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
