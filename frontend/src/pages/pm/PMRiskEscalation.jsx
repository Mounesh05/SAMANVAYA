import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { AlertTriangle, Clock, Cpu, TrendingUp, Users, ChevronRight } from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';
import { pmAPI } from '../../services/api';

const sevColors = { High: '#ef4444', Medium: '#f59e0b', Low: '#10b981' };
const statusColors = { Open: '#ef4444', 'In Progress': '#f59e0b', Resolved: '#10b981' };

export default function PMRiskEscalation() {
    const [escalationTimeline, setEscalationTimeline] = useState([]);
    const [delayDistribution, setDelayDistribution] = useState([]);
    const [highRiskMembers, setHighRiskMembers] = useState([]);
    const [selectedEscalation, setSelectedEscalation] = useState(null);

    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [events, members, delay] = await Promise.all([
                    pmAPI.escalationEvents(),
                    pmAPI.highRiskMembers(),
                    pmAPI.delayDistribution()
                ]);
                if (events?.length) setEscalationTimeline(events);
                if (members?.length) setHighRiskMembers(members);
                if (delay?.length) setDelayDistribution(delay);
            } catch (err) {
                console.error('Failed to fetch PM Risk Escalation data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading risk data...</div>;
    // Compute stats
    const activeEscalations = escalationTimeline.filter(e => e.status !== 'Resolved').length;
    const resolvedCount = escalationTimeline.filter(e => e.status === 'Resolved').length;
    const resolutionRate = escalationTimeline.length > 0 ? Math.round((resolvedCount / escalationTimeline.length) * 100) : 0;
    const highSeverity = escalationTimeline.filter(e => e.severity === 'High').length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<AlertTriangle size={24} />} value={activeEscalations} label="Active Escalations" color="red" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={`${highSeverity}`} label="High Severity" color="orange" delay={0.08} />
                <StatsCard icon={<Users size={24} />} value={highRiskMembers.length} label="High Risk Members" color="purple" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${resolutionRate}%`} label="Resolution Rate" trend={resolutionRate >= 70 ? '+' : ''} trendDir={resolutionRate >= 70 ? 'up' : 'down'} color="green" delay={0.24} />
            </div>

            {/* ── Escalation Timeline (Visual) ─────────────────────── */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Clock size={16} style={{ color: '#8b5cf6' }} /> Escalation Timeline
                    </span>
                    <span style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>
                        {escalationTimeline.length} event{escalationTimeline.length !== 1 ? 's' : ''}
                    </span>
                </div>
                <div className="card-body" style={{ padding: '16px 0' }}>
                    {escalationTimeline.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.88rem' }}>
                            No escalation events found.
                        </div>
                    ) : (
                        <div style={{ position: 'relative', paddingLeft: 40 }}>
                            {/* Vertical timeline line */}
                            <div style={{
                                position: 'absolute', left: 27, top: 8, bottom: 8,
                                width: 3, background: 'linear-gradient(180deg, #8b5cf6, #c4b5fd, #e5e7eb)',
                                borderRadius: 2,
                            }} />

                            {escalationTimeline.map((e, i) => {
                                const isSelected = selectedEscalation === i;
                                return (
                                    <div
                                        key={i}
                                        onClick={() => setSelectedEscalation(isSelected ? null : i)}
                                        style={{
                                            position: 'relative',
                                            marginBottom: i < escalationTimeline.length - 1 ? 4 : 0,
                                            cursor: 'pointer',
                                            transition: 'all 0.2s ease',
                                        }}
                                    >
                                        {/* Timeline dot */}
                                        <div style={{
                                            position: 'absolute', left: -21, top: 18,
                                            width: 14, height: 14, borderRadius: '50%',
                                            background: sevColors[e.severity] || '#8b5cf6',
                                            border: '3px solid #fff',
                                            boxShadow: `0 0 0 2px ${(sevColors[e.severity] || '#8b5cf6')}40`,
                                            zIndex: 2,
                                        }} />

                                        {/* Card */}
                                        <div style={{
                                            marginLeft: 12, padding: '14px 18px',
                                            background: isSelected ? 'var(--bg-secondary)' : 'transparent',
                                            borderRadius: 'var(--radius-md)',
                                            border: isSelected ? '1px solid var(--border-color)' : '1px solid transparent',
                                            transition: 'all 0.2s ease',
                                        }}
                                            onMouseEnter={ev => { if (!isSelected) ev.currentTarget.style.background = 'var(--bg-secondary)'; }}
                                            onMouseLeave={ev => { if (!isSelected) ev.currentTarget.style.background = 'transparent'; }}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                <div style={{ flex: 1 }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                                                        <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>{e.event}</span>
                                                        <span style={{
                                                            fontSize: '0.68rem', padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                                                            background: `${statusColors[e.status]}18`,
                                                            color: statusColors[e.status],
                                                            border: `1px solid ${statusColors[e.status]}30`,
                                                        }}>{e.status}</span>
                                                        <span style={{
                                                            fontSize: '0.68rem', padding: '2px 8px', borderRadius: 20, fontWeight: 600,
                                                            background: `${sevColors[e.severity]}15`,
                                                            color: sevColors[e.severity],
                                                        }}>{e.severity}</span>
                                                    </div>
                                                    <div style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>
                                                        <span style={{ fontWeight: 600, color: 'var(--text-secondary)' }}>{e.who}</span> · {e.time}
                                                    </div>
                                                </div>
                                                <ChevronRight size={16} style={{
                                                    color: 'var(--text-tertiary)',
                                                    transform: isSelected ? 'rotate(90deg)' : 'rotate(0)',
                                                    transition: 'transform 0.2s ease',
                                                }} />
                                            </div>

                                            {/* Expanded detail */}
                                            {isSelected && (
                                                <div style={{
                                                    marginTop: 12, paddingTop: 12,
                                                    borderTop: '1px solid var(--border-color)',
                                                    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))', gap: 10,
                                                }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Severity</div>
                                                        <div style={{ fontWeight: 700, color: sevColors[e.severity], fontSize: '0.88rem' }}>{e.severity}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</div>
                                                        <div style={{ fontWeight: 700, color: statusColors[e.status], fontSize: '0.88rem' }}>{e.status}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Reported By</div>
                                                        <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{e.who}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Time</div>
                                                        <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{e.time}</div>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </AnimatedCard>

            <div className="grid-2" style={{ marginTop: 20 }}>
                {/* ── Delay Distribution (from DB) ─────────────────── */}
                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Clock size={16} style={{ color: '#f59e0b' }} /> Delay Distribution
                        </span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            {delayDistribution.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={delayDistribution} barCategoryGap="20%">
                                        <defs>
                                            <linearGradient id="delayGrad" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="0%" stopColor="#f59e0b" stopOpacity={1} />
                                                <stop offset="100%" stopColor="#fbbf24" stopOpacity={0.6} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis dataKey="range" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip
                                            formatter={(v) => [`${v} tasks`, 'Delayed']}
                                            contentStyle={{ borderRadius: 8, border: '1px solid #fde68a', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                                        />
                                        <Bar dataKey="count" fill="url(#delayGrad)" radius={[6, 6, 0, 0]} />
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                    No delay distribution data available
                                </div>
                            )}
                        </div>
                    </div>
                </AnimatedCard>

                {/* ── High-Risk Members ─────────────────────────────── */}
                <AnimatedCard delay={0.46}>
                    <div className="card-header"><span className="card-title">High-Risk Members</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead><tr><th>Member</th><th>Escalations</th><th>Avg Delay</th><th>Risk</th></tr></thead>
                                <tbody>
                                    {highRiskMembers.length > 0 ? highRiskMembers.map(m => (
                                        <tr key={m.name}>
                                            <td style={{ fontWeight: 600 }}>{m.name}</td>
                                            <td style={{ fontWeight: 700, color: m.escalations > 2 ? '#ef4444' : '#f59e0b' }}>{m.escalations}</td>
                                            <td style={{ fontWeight: 600 }}>{m.avgDelay}</td>
                                            <td><span className="badge" style={{ background: sevColors[m.risk], color: '#fff' }}>{m.risk}</span></td>
                                        </tr>
                                    )) : (
                                        <tr><td colSpan={4} style={{ textAlign: 'center', color: 'var(--text-tertiary)' }}>No high-risk members</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* ── Root Cause AI Summary ─────────────────────────────── */}
            <AnimatedCard delay={0.54} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <Cpu size={16} style={{ color: '#8b5cf6' }} /> Root Cause AI Summary
                    </span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {[
                            { text: `${highSeverity > 0 ? highSeverity + ' high severity escalation(s) active' : 'No high severity escalations'} — ${activeEscalations > 0 ? 'immediate attention may be required' : 'all escalations resolved'}.`, type: activeEscalations > 2 ? 'danger' : activeEscalations > 0 ? 'warning' : 'success' },
                            { text: `Resolution rate: ${resolutionRate}% — ${resolutionRate >= 70 ? 'on track' : 'below target, improve response times'}.`, type: resolutionRate >= 70 ? 'success' : 'warning' },
                            { text: `${highRiskMembers.length} members flagged as high risk — ${highRiskMembers.length > 2 ? 'workload redistribution recommended' : 'monitor closely'}.`, type: highRiskMembers.length > 2 ? 'danger' : highRiskMembers.length > 0 ? 'warning' : 'success' },
                            { text: `Delay distribution shows ${delayDistribution.length > 0 ? delayDistribution.reduce((max, d) => d.count > max.count ? d : max, delayDistribution[0])?.range + ' as the most common delay range' : 'no data yet'}.`, type: 'info' },
                        ].map((item, i) => (
                            <div key={i} style={{
                                padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                                background: item.type === 'success' ? '#f0fdf4' : item.type === 'warning' ? '#fffbeb' : item.type === 'danger' ? '#fef2f2' : '#eff6ff',
                                border: `1px solid ${item.type === 'success' ? '#bbf7d0' : item.type === 'warning' ? '#fde68a' : item.type === 'danger' ? '#fecaca' : '#bfdbfe'}`,
                                fontSize: '0.85rem', lineHeight: 1.5,
                                color: item.type === 'success' ? '#166534' : item.type === 'warning' ? '#92400e' : item.type === 'danger' ? '#991b1b' : '#1e40af'
                            }}>
                                {item.type === 'success' ? '✅' : item.type === 'warning' ? '⚠️' : item.type === 'danger' ? '🔴' : 'ℹ️'} {item.text}
                            </div>
                        ))}
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
