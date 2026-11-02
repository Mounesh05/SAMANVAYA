import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { ShieldAlert, Clock, AlertOctagon, CheckCircle } from 'lucide-react';
import { leadAPI } from '../../services/api';

const typeColors = {
    'Rejection Loop': '#ef4444', 'DevOps Failure': '#8b5cf6', 'Scope Drift': '#f59e0b',
    'Approval Delay': '#3b82f6', 'Overload': '#ef4444',
};
const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };

export default function SMRiskBlockers() {
    const [blockers, setBlockers] = useState([]);

    useEffect(() => {
        leadAPI.riskBlockers().then(data => { if (Array.isArray(data)) setBlockers(data); }).catch(() => { });
    }, []);

    const toggle = id => {
        const blocker = blockers.find(b => b.id === id);
        const newResolved = !blocker?.resolved;
        setBlockers(prev => prev.map(b => b.id === id ? { ...b, resolved: newResolved } : b));
        leadAPI.updateBlocker(id, { resolved: newResolved }).catch(err => console.error('Failed to update blocker:', err));
    };

    const active = blockers.filter(b => !b.resolved);
    const resolved = blockers.filter(b => b.resolved);

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<ShieldAlert size={24} />} value={active.length} label="Active Blockers" color="red" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={`${Math.max(...active.map(b => b.daysBlocked), 0)}d`} label="Max Days Blocked" color="orange" delay={0.08} />
                <StatsCard icon={<AlertOctagon size={24} />} value={active.filter(b => b.risk === 'High').length} label="High Risk" color="red" delay={0.16} />
                <StatsCard icon={<CheckCircle size={24} />} value={resolved.length} label="Resolved" color="green" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header"><span className="card-title">Active Blockers</span></div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>Story</th><th>Blocker Type</th><th>Owner</th><th>Days Blocked</th><th>Risk Level</th><th>Action</th></tr>
                            </thead>
                            <tbody>
                                {active.map(b => (
                                    <tr key={b.id}>
                                        <td>
                                            <div style={{ fontWeight: 600 }}>{b.title}</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{b.story}</div>
                                        </td>
                                        <td>
                                            <span className="badge" style={{ background: (typeColors[b.blockerType] || '#6b7280') + '20', color: typeColors[b.blockerType] || '#6b7280', fontWeight: 700 }}>
                                                {b.blockerType}
                                            </span>
                                        </td>
                                        <td style={{ fontWeight: 600 }}>{b.owner}</td>
                                        <td>
                                            <span style={{ fontWeight: 700, color: b.daysBlocked >= 3 ? '#ef4444' : b.daysBlocked >= 1 ? '#f59e0b' : '#6b7280' }}>
                                                {b.daysBlocked > 0 ? `${b.daysBlocked}d` : 'Today'}
                                            </span>
                                        </td>
                                        <td><span style={{ fontWeight: 700, color: riskColors[b.risk] }}>{b.risk}</span></td>
                                        <td>
                                            <button onClick={() => toggle(b.id)}
                                                style={{ padding: '4px 12px', borderRadius: 6, border: 'none', background: '#10b98120', color: '#10b981', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                Mark Resolved ✓
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {active.length === 0 && (
                                    <tr><td colSpan={6} style={{ textAlign: 'center', padding: 28, color: '#10b981', fontWeight: 600 }}>✅ No active blockers</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {resolved.length > 0 && (
                <AnimatedCard delay={0.4} style={{ marginTop: 20 }}>
                    <div className="card-header"><span className="card-title">✅ Resolved Blockers</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr><th>Story</th><th>Blocker Type</th><th>Owner</th><th>Risk</th><th>Action</th></tr>
                                </thead>
                                <tbody>
                                    {resolved.map(b => (
                                        <tr key={b.id} style={{ opacity: 0.65 }}>
                                            <td>
                                                <div style={{ fontWeight: 600, textDecoration: 'line-through' }}>{b.title}</div>
                                                <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{b.story}</div>
                                            </td>
                                            <td><span className="badge badge-neutral">{b.blockerType}</span></td>
                                            <td>{b.owner}</td>
                                            <td><span style={{ color: riskColors[b.risk], fontWeight: 600 }}>{b.risk}</span></td>
                                            <td>
                                                <button onClick={() => toggle(b.id)}
                                                    style={{ padding: '4px 12px', borderRadius: 6, border: 'none', background: '#f3f4f6', color: '#6b7280', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                    Reopen
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
