import { useState, useEffect } from 'react';
import StatsCard from '../../components/StatsCard';
import { dashboardAPI } from '../../services/api';
import AnimatedCard from '../../components/AnimatedCard';
import { CheckSquare, Bug, FlaskConical, Shield, Cpu, TrendingUp, BarChart2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell } from 'recharts';

const testStatus = { Testing: 'badge-info', Passed: 'badge-success', Failed: 'badge-danger' };

export default function QADashboard() {
    const [loading, setLoading] = useState(true);
    const [recentStories, setRecentStories] = useState([]);
    const [bugsByStatus, setBugsByStatus] = useState([]);
    const [sprintQuality, setSprintQuality] = useState([]);

    useEffect(() => {
        setLoading(true);
        dashboardAPI.qa().then(data => {
            if (!data) return;
            if (data.recent_stories) setRecentStories(data.recent_stories);
            if (data.bugs_by_status) setBugsByStatus(data.bugs_by_status);
            if (data.sprint_quality) setSprintQuality(data.sprint_quality);
        }).catch(err => console.error('Failed to fetch QA dashboard:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading dashboard...</div>;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={recentStories.length.toString()} label="Active Testing" trend="+3 new" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<FlaskConical size={24} />} value="86" label="Total Test Cases" color="green" delay={0.08} />
                <StatsCard icon={<Bug size={24} />} value={bugsByStatus.find(b => b.name === 'Open')?.value.toString() || '0'} label="Open Bugs" trend="2 critical" color="red" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={(sprintQuality[sprintQuality.length - 1]?.score || 0) + '%'} label="Current Quality" trend="↑ 3%" trendDir="up" color="green" delay={0.24} />
            </div>
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header"><span className="card-title">Recent Stories</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <thead><tr><th>Story</th><th>Developer</th><th>Status</th><th>Priority</th></tr></thead>
                            <tbody>
                                {recentStories.map(s => (
                                    <tr key={s.id}>
                                        <td style={{ fontWeight: 600 }}>{s.story}</td>
                                        <td style={{ fontSize: '0.82rem' }}>{s.dev}</td>
                                        <td><span className={`badge ${testStatus[s.status]}`}>{s.status}</span></td>
                                        <td><span className={`badge ${s.priority === 'Critical' ? 'badge-danger' : s.priority === 'High' ? 'badge-warning' : 'badge-neutral'}`}>{s.priority}</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.38}>
                    <div className="card-header"><span className="card-title">Bugs by Status</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={bugsByStatus} cx="50%" cy="50%" outerRadius={75} innerRadius={40}
                                        dataKey="value" nameKey="name" label={({ name, value }) => `${name}: ${value}`}>
                                        {bugsByStatus.map((d, i) => <Cell key={i} fill={d.color} />)}
                                    </Pie>
                                    <Tooltip /><Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            <div className="grid-2">
                <AnimatedCard delay={0.46}>
                    <div className="card-header"><span className="card-title">Quality Score Trend</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={sprintQuality}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Bar dataKey="score" radius={[4, 4, 0, 0]} name="Quality %" fill="#3b82f6">
                                        {sprintQuality.map((d, i) => <Cell key={i} fill={d.score >= 80 ? '#10b981' : d.score >= 70 ? '#f59e0b' : '#ef4444'} />)}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.54}>
                    <div className="card-header"><span className="card-title">AI Highlights</span><span className="badge badge-info"><Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />AI</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--danger-bg)', borderLeft: '3px solid var(--danger)', fontSize: '0.85rem' }}>
                            <Cpu size={13} style={{ marginRight: 6, display: 'inline' }} /> 2 critical bugs in payment module remain open for 3+ days.
                        </div>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--warning-bg)', borderLeft: '3px solid var(--warning)', fontSize: '0.85rem' }}>
                            <Cpu size={13} style={{ marginRight: 6, display: 'inline' }} /> Regression pass rate dropped to 78%. Check backend logic stability.
                        </div>
                        <div style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: 'var(--success-bg)', borderLeft: '3px solid var(--success)', fontSize: '0.85rem' }}>
                            <Cpu size={13} style={{ marginRight: 6, display: 'inline' }} /> Test coverage improved to 82% this sprint — 4% above target.
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
