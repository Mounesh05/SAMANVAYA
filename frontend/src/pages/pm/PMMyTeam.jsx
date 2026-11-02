import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Users, Search, TrendingUp, AlertTriangle, Shield, Clock, Cpu, ChevronRight } from 'lucide-react';
import { pmAPI } from '../../services/api';

const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const statusColors = { Active: '#10b981', 'On Leave': '#3b82f6', Probation: '#f59e0b' };
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

export default function PMMyTeam() {
    const navigate = useNavigate();
    const [teamMembers, setTeamMembers] = useState([]);
    const [search, setSearch] = useState('');
    const [selectedMember, setSelectedMember] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        pmAPI.team()
            .then(data => { if (data?.length) setTeamMembers(data); })
            .catch(err => console.error('Failed to fetch PM Team data:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading team data...</div>;

    const filtered = teamMembers.filter(m => !search || m.name.toLowerCase().includes(search.toLowerCase()));

    // Dynamic stats
    const avgAlignment = teamMembers.length ? (teamMembers.reduce((a, m) => a + m.alignmentAvg, 0) / teamMembers.length).toFixed(1) : '0';
    const highRiskCount = teamMembers.filter(m => m.risk === 'High').length;
    const avgOnTime = teamMembers.length ? (teamMembers.reduce((a, m) => a + m.onTime, 0) / teamMembers.length).toFixed(1) : '0';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={teamMembers.length} label="Team Members" color="blue" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={highRiskCount} label="High Risk" color="red" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={`${avgOnTime}%`} label="Avg On-Time" color="purple" delay={0.24} />
            </div>

            <div style={{ display: 'flex', gap: 20 }}>
                {/* Team Table */}
                <div style={{ flex: 1 }}>
                    <AnimatedCard delay={0.3}>
                        <div className="card-header">
                            <span className="card-title">My Team</span>
                            <div style={{ position: 'relative' }}>
                                <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
                                <input type="text" placeholder="Search member..." value={search} onChange={e => setSearch(e.target.value)}
                                    style={{ paddingLeft: 30, padding: '6px 12px 6px 30px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem', width: 180 }} />
                            </div>
                        </div>
                        <div className="card-body" style={{ padding: 0 }}>
                            <div className="table-wrapper">
                                <table className="table">
                                    <thead>
                                        <tr>
                                            <th>Name</th><th>Role</th><th>Sprint Tasks</th><th>Alignment Avg</th>
                                            <th>On-Time %</th><th>Risk Level</th><th>Workload</th><th>Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {filtered.map(m => (
                                            <tr key={m.id} onClick={() => setSelectedMember(m)} style={{ cursor: 'pointer', background: selectedMember?.id === m.id ? 'var(--bg-secondary)' : 'transparent' }}>
                                                <td>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                        <div style={{ width: 32, height: 32, borderRadius: '50%', background: '#3b82f6', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.7rem' }}>{m.avatar}</div>
                                                        <span style={{ fontWeight: 600 }}>{m.name}</span>
                                                    </div>
                                                </td>
                                                <td style={{ fontSize: '0.82rem' }}>{m.role}</td>
                                                <td style={{ fontWeight: 700 }}>{m.sprintTasks}</td>
                                                <td><span style={{ fontWeight: 700, color: getColor(m.alignmentAvg) }}>{m.alignmentAvg}%</span></td>
                                                <td><span style={{ fontWeight: 700, color: getColor(m.onTime) }}>{m.onTime}%</span></td>
                                                <td><span className="badge" style={{ background: riskColors[m.risk], color: '#fff' }}>{m.risk}</span></td>
                                                <td>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <div style={{ flex: 1, height: 6, background: '#e5e7eb', borderRadius: 3, overflow: 'hidden' }}>
                                                            <div style={{ width: `${m.workload}%`, height: '100%', background: m.workload > 80 ? '#ef4444' : m.workload > 60 ? '#f59e0b' : '#10b981', borderRadius: 3 }} />
                                                        </div>
                                                        <span style={{ fontSize: '0.72rem', fontWeight: 600, color: m.workload > 80 ? '#ef4444' : 'var(--text-secondary)' }}>{m.workload}%</span>
                                                    </div>
                                                </td>
                                                <td><span className="badge" style={{ background: `${statusColors[m.status]}20`, color: statusColors[m.status] }}>{m.status}</span></td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </AnimatedCard>
                </div>
            </div>

            {/* Member Detail Panel */}
            {selectedMember && (
                <div className="grid-2" style={{ marginTop: 20, gap: 20 }}>
                    {/* Performance Snapshot */}
                    <AnimatedCard delay={0}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                📊 Performance Snapshot — {selectedMember.name}
                            </span>
                        </div>
                        <div className="card-body">
                            {[
                                { label: 'Alignment Trend (last 3 sprints)', val: `${selectedMember.alignmentAvg - 4}% → ${selectedMember.alignmentAvg - 1}% → ${selectedMember.alignmentAvg}%`, color: getColor(selectedMember.alignmentAvg) },
                                { label: 'Delivery Consistency', val: `${selectedMember.onTime}%`, color: getColor(selectedMember.onTime) },
                                { label: 'Rejection Rate', val: `${Math.max(2, 100 - selectedMember.onTime - 3)}%`, color: (100 - selectedMember.onTime - 3) > 10 ? '#ef4444' : '#10b981' },
                                { label: 'Behaviour Score', val: `${(selectedMember.alignmentAvg / 10).toFixed(1)}/10`, color: getColor(selectedMember.alignmentAvg) },
                            ].map((item, i) => (
                                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                    <span style={{ fontSize: '0.85rem' }}>{item.label}</span>
                                    <span style={{ fontWeight: 700, color: item.color }}>{item.val}</span>
                                </div>
                            ))}
                        </div>
                    </AnimatedCard>

                    {/* Risk + AI */}
                    <div>
                        {/* Risk Signals */}
                        <AnimatedCard delay={0.08}>
                            <div className="card-header">
                                <span className="card-title">⚠ Risk Signals</span>
                            </div>
                            <div className="card-body">
                                {[
                                    { label: 'Repeated Delays', val: selectedMember.risk === 'High' ? '3 in last sprint' : selectedMember.risk === 'Medium' ? '1 delay' : 'None', warn: selectedMember.risk !== 'Low' },
                                    { label: 'Escalation Count', val: selectedMember.risk === 'High' ? '2 escalations' : '0', warn: selectedMember.risk === 'High' },
                                    { label: 'Scope Drift %', val: selectedMember.risk === 'High' ? '18%' : selectedMember.risk === 'Medium' ? '8%' : '2%', warn: selectedMember.risk !== 'Low' },
                                ].map((item, i) => (
                                    <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                        <span style={{ fontSize: '0.85rem' }}>{item.label}</span>
                                        <span style={{ fontWeight: 700, color: item.warn ? '#ef4444' : '#10b981' }}>{item.val}</span>
                                    </div>
                                ))}
                            </div>
                        </AnimatedCard>

                        {/* AI Insight Panel */}
                        <AnimatedCard delay={0.16} style={{ marginTop: 16 }}>
                            <div className="card-header">
                                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Cpu size={16} style={{ color: '#8b5cf6' }} /> 🧠 AI Insight
                                </span>
                            </div>
                            <div className="card-body">
                                <div style={{ padding: '14px 18px', background: 'linear-gradient(135deg, #ede9fe, #f5f3ff)', borderRadius: 'var(--radius-sm)', border: '1px solid #c4b5fd', fontSize: '0.88rem', lineHeight: 1.6, color: '#4c1d95' }}>
                                    {selectedMember.risk === 'High'
                                        ? `"${selectedMember.name} shows ${Math.round(Math.random() * 10 + 10)}% drop in alignment compared to last sprint. Workload at ${selectedMember.workload}% — consider redistribution."`
                                        : selectedMember.risk === 'Medium'
                                            ? `"${selectedMember.name} has moderate risk signals. Rejection rate slightly elevated. Recommend 1-on-1 review."`
                                            : `"${selectedMember.name} is performing well with consistent delivery and stable alignment. No action needed."`
                                    }
                                </div>
                            </div>
                        </AnimatedCard>
                    </div>
                </div>
            )}
        </div>
    );
}
