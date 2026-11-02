import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Users, AlertTriangle, TrendingUp, CheckCircle, BarChart2, X } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { leadAPI } from '../../services/api';

const riskColor = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', 'Done': '#10b981' };

export default function SMMyTeam() {
    const [teamData, setTeamData] = useState([]);
    const [selected, setSelected] = useState(null);
    const [notes, setNotes] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        leadAPI.myTeam().then(data => {
            if (data?.length) {
                setTeamData(data);
                setNotes(Object.fromEntries(data.map(m => [m.id, m.behaviourNotes || ''])));
            }
        }).catch(err => console.error('Failed to fetch team data:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading team members...</div>;
    }

    const member = teamData.find(m => m.id === selected);


    return (
        <div>
            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={teamData.length} label="Team Members" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={teamData.filter(m => m.risk === 'Low').length} label="Low Risk" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={teamData.filter(m => m.workload > 80).length} label="Overloaded" color="red" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${Math.round(teamData.reduce((a, m) => a + m.alignmentAvg, 0) / teamData.length)}%`} label="Avg Alignment" color="purple" delay={0.24} />
            </div>

            {/* Team Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Team Overview</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Member</th><th>Role</th><th>Active Stories</th><th>Alignment Avg</th>
                                    <th>Risk Level</th><th>Workload %</th><th>Behaviour</th><th>Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                {teamData.map(m => (
                                    <tr key={m.id} onClick={() => setSelected(m.id)} style={{ cursor: 'pointer' }}
                                        className="hover-row">
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                <div style={{ width: 34, height: 34, borderRadius: '50%', background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.75rem', fontWeight: 700 }}>{m.avatar}</div>
                                                <span style={{ fontWeight: 600 }}>{m.name}</span>
                                            </div>
                                        </td>
                                        <td><span className="badge badge-neutral">{m.role}</span></td>
                                        <td style={{ fontWeight: 700 }}>{m.activeStories}</td>
                                        <td><span style={{ fontWeight: 700, color: m.alignmentAvg >= 80 ? '#10b981' : m.alignmentAvg >= 65 ? '#f59e0b' : '#ef4444' }}>{m.alignmentAvg}%</span>
                                            {m.alignmentAvg < 65 && <span style={{ marginLeft: 6, fontSize: '0.7rem', color: '#ef4444', fontWeight: 600 }}>⚠ Low</span>}
                                        </td>
                                        <td>
                                            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontWeight: 600, fontSize: '0.8rem', color: riskColor[m.risk] }}>
                                                <span style={{ width: 8, height: 8, borderRadius: '50%', background: riskColor[m.risk], display: 'inline-block' }} />
                                                {m.risk}
                                            </span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ width: 80, height: 7, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
                                                    <div style={{ width: `${m.workload}%`, height: '100%', background: m.workload > 80 ? '#ef4444' : m.workload > 60 ? '#f59e0b' : '#10b981', borderRadius: 4 }} />
                                                </div>
                                                <span style={{ fontSize: '0.82rem', fontWeight: 700, color: m.workload > 80 ? '#ef4444' : 'inherit' }}>{m.workload}%</span>
                                                {m.workload > 80 && <span style={{ background: '#ef4444', color: '#fff', fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 100 }}>OVERLOADED</span>}
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <span style={{ fontWeight: 700, color: m.behaviourScore >= 8 ? '#10b981' : m.behaviourScore >= 6.5 ? '#f59e0b' : '#ef4444' }}>{m.behaviourScore}</span>
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>/10</span>
                                            </div>
                                        </td>
                                        <td><span className="badge" style={{ background: '#10b98120', color: '#10b981' }}>{m.status}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Member Detail Panel */}
            {member && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)', zIndex: 1000, display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end', padding: 0 }}>
                    <div style={{ width: 640, height: '100vh', background: '#fff', overflowY: 'auto', boxShadow: '-8px 0 40px rgba(0,0,0,0.18)', padding: 28, position: 'relative' }}>
                        <button onClick={() => setSelected(null)} style={{ position: 'absolute', top: 20, right: 20, background: 'none', border: 'none', cursor: 'pointer' }}><X size={22} /></button>

                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24, paddingBottom: 20, borderBottom: '1px solid var(--border-color)' }}>
                            <div style={{ width: 56, height: 56, borderRadius: '50%', background: 'linear-gradient(135deg,#3b82f6,#8b5cf6)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.1rem', fontWeight: 700 }}>{member.avatar}</div>
                            <div>
                                <h2 style={{ margin: 0, fontSize: '1.2rem' }}>{member.name}</h2>
                                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{member.role} · Rejection Rate: <strong style={{ color: member.rejectionRate > 15 ? '#ef4444' : '#10b981' }}>{member.rejectionRate}%</strong> · Blockers: <strong>{member.blockerInvolvement}</strong></p>
                            </div>
                        </div>

                        {/* Current Sprint Stories */}
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 10 }}>Current Sprint Stories</h4>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 20 }}>
                            {member.sprintStories.map(s => (
                                <div key={s.id} style={{ padding: '10px 14px', background: '#f8fafc', borderRadius: 8, border: '1px solid var(--border-color)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{s.title}</span>
                                        <span style={{ marginLeft: 8, fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{s.id} · {s.points} SP</span>
                                    </div>
                                    <div style={{ display: 'flex', gap: 8 }}>
                                        <span className="badge" style={{ background: `${statusColors[s.status]}20`, color: statusColors[s.status] }}>{s.status}</span>
                                        <span className="badge" style={{ background: (s.alignment >= 80 ? '#10b981' : s.alignment >= 65 ? '#f59e0b' : '#ef4444') + '20', color: s.alignment >= 80 ? '#10b981' : s.alignment >= 65 ? '#f59e0b' : '#ef4444' }}>AI: {s.alignment}%</span>
                                    </div>
                                </div>
                            ))}
                        </div>

                        {/* Alignment History */}
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 10 }}>Alignment History</h4>
                        <div style={{ height: 160, marginBottom: 20 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={member.alignmentHistory}>
                                    <defs><linearGradient id="aGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} /><stop offset="95%" stopColor="#3b82f6" stopOpacity={0} /></linearGradient></defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                    <YAxis domain={[50, 100]} tick={{ fontSize: 11 }} />
                                    <Tooltip formatter={v => `${v}%`} />
                                    <Area type="monotone" dataKey="score" stroke="#3b82f6" fill="url(#aGrad)" strokeWidth={2} dot={{ r: 3 }} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Workload Graph */}
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 10 }}>Workload Trend</h4>
                        <div style={{ height: 140, marginBottom: 20 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={member.workloadHistory}>
                                    <defs><linearGradient id="wGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} /><stop offset="95%" stopColor="#f59e0b" stopOpacity={0} /></linearGradient></defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                    <YAxis domain={[30, 110]} tick={{ fontSize: 11 }} unit="%" />
                                    <Tooltip formatter={v => `${v}%`} />
                                    <Area type="monotone" dataKey="load" stroke="#f59e0b" fill="url(#wGrad)" strokeWidth={2} dot={{ r: 3 }} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>

                        {/* Behaviour Notes */}
                        <h4 style={{ fontSize: '0.9rem', fontWeight: 700, marginBottom: 8 }}>Behaviour Notes <span style={{ fontWeight: 400, color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>(editable)</span></h4>
                        <textarea value={notes[member.id]} onChange={e => setNotes(prev => ({ ...prev, [member.id]: e.target.value }))}
                            style={{ width: '100%', minHeight: 90, padding: '10px 14px', borderRadius: 8, border: '1px solid var(--border-color)', fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.5 }} />
                        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                            <div style={{ flex: 1, padding: '12px', background: '#f0fdf4', borderRadius: 8, textAlign: 'center' }}>
                                <div style={{ fontWeight: 800, fontSize: '1.2rem', color: '#10b981' }}>{member.rejectionRate}%</div>
                                <div style={{ fontSize: '0.75rem', color: '#065f46' }}>Review Rejection Rate</div>
                            </div>
                            <div style={{ flex: 1, padding: '12px', background: '#fff7ed', borderRadius: 8, textAlign: 'center' }}>
                                <div style={{ fontWeight: 800, fontSize: '1.2rem', color: '#f59e0b' }}>{member.blockerInvolvement}</div>
                                <div style={{ fontSize: '0.75rem', color: '#92400e' }}>Blocker Involvements</div>
                            </div>
                            <div style={{ flex: 1, padding: '12px', background: '#eff6ff', borderRadius: 8, textAlign: 'center' }}>
                                <div style={{ fontWeight: 800, fontSize: '1.2rem', color: '#3b82f6' }}>{member.behaviourScore}</div>
                                <div style={{ fontSize: '0.75rem', color: '#1e3a8a' }}>Behaviour Score</div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
