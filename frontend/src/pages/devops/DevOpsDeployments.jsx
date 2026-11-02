import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { UploadCloud, CheckCircle, XCircle, RotateCcw, Clock, Activity, AlertTriangle, Cpu } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { devopsAPI, deploymentsAPI } from '../../services/api';
import ConfirmToast from '../../components/ConfirmToast';

const statusConfig = {
    Stable: { bg: '#ecfdf5', color: '#10b981' },
    Warning: { bg: '#fffbeb', color: '#f59e0b' },
    Failed: { bg: '#fef2f2', color: '#ef4444' },
    'Rolled Back': { bg: '#fef2f2', color: '#ef4444' },
};

export default function DevOpsDeployments() {
    const [data, setData] = useState([]);
    const [deployFrequency, setDeployFrequency] = useState([]);
    const [mttr, setMttr] = useState('1h 45m');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        devopsAPI.deployments().then(d => {
            if (d?.length) setData(d);
        }).catch(() => {
        }).finally(() => setLoading(false));

        deploymentsAPI.metrics().then(m => {
            if (m?.deploy_frequency?.length) setDeployFrequency(m.deploy_frequency);
            if (m?.mttr) setMttr(m.mttr);
        }).catch(() => { });
    }, []);

    const stableCount = data.filter(d => d.status === 'Stable').length;
    const failedCount = data.filter(d => d.status === 'Failed' || d.status === 'Rolled Back').length;
    const rollbackCount = data.filter(d => d.status === 'Rolled Back').length;

    const [confirmRollback, setConfirmRollback] = useState(null);

    const handleRollback = (id) => {
        setConfirmRollback(id);
    };

    const handleConfirmRollback = () => {
        const id = confirmRollback;
        setConfirmRollback(null);
        setData(prev => prev.map(d => d.id === id ? { ...d, status: 'Rolled Back', canRollback: false } : d));
        deploymentsAPI.update(id, { status: 'Rolled Back', canRollback: false }).catch(err => console.error('Failed to rollback deployment:', err));
    };

    return (
        <div>
            {confirmRollback && (
                <ConfirmToast
                    message="Are you sure you want to rollback this deployment? This cannot be undone."
                    onConfirm={handleConfirmRollback}
                    onCancel={() => setConfirmRollback(null)}
                    variant="warning"
                />
            )}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<UploadCloud size={24} />} value={data.length} label="Total Deployments" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={stableCount} label="Stable" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={failedCount} label="Failed / Rolled Back" color="red" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={mttr} label="MTTR" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Deployments</span>
                    <span className="badge badge-info">{data.length} deployments</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Service</th><th>Environment</th><th>Version</th><th>Status</th>
                                    <th>Deployed At</th><th>Deployed By</th><th>Rollback</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map(d => {
                                    const cfg = statusConfig[d.status] || statusConfig.Stable;
                                    return (
                                        <tr key={d.id}>
                                            <td><span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{d.service}</span></td>
                                            <td>
                                                <span className="badge" style={{
                                                    background: d.env === 'Production' ? '#dbeafe' : '#f3e8ff',
                                                    color: d.env === 'Production' ? '#1d4ed8' : '#7c3aed'
                                                }}>{d.env}</span>
                                            </td>
                                            <td><span style={{ fontFamily: "'Courier New', monospace", fontWeight: 600, fontSize: '0.85rem' }}>{d.version}</span></td>
                                            <td>
                                                <span className="badge" style={{ background: cfg.bg, color: cfg.color }}>
                                                    {d.status === 'Stable' ? '🟢' : d.status === 'Warning' ? '🟡' : '🔴'} {d.status}
                                                </span>
                                            </td>
                                            <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{d.deployedAt}</td>
                                            <td style={{ fontSize: '0.82rem' }}>{d.deployedBy}</td>
                                            <td>
                                                {d.canRollback ? (
                                                    <button onClick={() => handleRollback(d.id)}
                                                        style={{
                                                            padding: '4px 10px', borderRadius: 'var(--radius-sm)',
                                                            background: '#fef2f2', color: '#ef4444', border: '1px solid #fecaca',
                                                            fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                                            display: 'flex', alignItems: 'center', gap: 4, transition: 'all 0.15s ease'
                                                        }}>
                                                        <RotateCcw size={12} /> Rollback
                                                    </button>
                                                ) : (
                                                    <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>
                                                )}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            <div className="grid-2" style={{ marginTop: 16 }}>
                <AnimatedCard delay={0.4}>
                    <div className="card-header"><span className="card-title">Deployment Frequency</span><span className="badge badge-neutral">This Week</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={deployFrequency}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Bar dataKey="deploys" radius={[4, 4, 0, 0]} name="Deployments">
                                        {deployFrequency.map((d, i) => (
                                            <Cell key={i} fill={d.deploys >= 5 ? '#10b981' : d.deploys >= 2 ? '#3b82f6' : '#f59e0b'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.48}>
                    <div className="card-header">
                        <span className="card-title">AI Suggestions</span>
                        <span className="badge badge-info"><Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />AI</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--danger-bg)', borderLeft: '3px solid var(--danger)' }}>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Cpu size={13} /> Frequent staging failures detected for beta-service. Check Docker image consistency.
                            </div>
                        </div>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--warning-bg)', borderLeft: '3px solid var(--warning)' }}>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Cpu size={13} /> notification-svc rolled back twice this month. Investigate dependency conflicts.
                            </div>
                        </div>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--success-bg)', borderLeft: '3px solid var(--success)' }}>
                            <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Cpu size={13} /> alpha-backend and auth-service deployments remain stable across all environments.
                            </div>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
