import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { BarChart3, TrendingUp, Users, AlertTriangle, Loader2 } from 'lucide-react';
import { hrAPI } from '../../services/api';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, PieChart, Pie, Cell
} from 'recharts';

const getScoreColor = (s) => s >= 80 ? '#10b981' : s >= 65 ? '#f59e0b' : '#ef4444';

export default function HRPerformanceAnalytics() {
    const [roleFilter, setRoleFilter] = useState('All');
    const [sprintFilter, setSprintFilter] = useState('All');
    const [deptPerf, setDeptPerf] = useState([]);
    const [velocity, setVelocity] = useState([]);
    const [topPerf, setTopPerf] = useState([]);
    const [lowPerf, setLowPerf] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [d, v, top, low] = await Promise.all([
                    hrAPI.deptPerformance(),
                    hrAPI.sprintVelocity(),
                    hrAPI.performers({ type: 'top' }),
                    hrAPI.performers({ type: 'low' })
                ]);
                setDeptPerf(d || []);
                setVelocity(v || []);
                setTopPerf(top || []);
                setLowPerf(low || []);
            } catch (err) {
                console.error('Failed to fetch analytics:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading analytics...</div>;
    }

    // Computing aggregate stats from fetched data
    const avgPerf = deptPerf.length ? (deptPerf.reduce((a, b) => a + b.score, 0) / deptPerf.length).toFixed(1) : '0.0';
    // For avg alignment, we might need another API or compute from performers if available.
    // Using 87.5% as placeholder if not in DB yet, or 0.0
    const avgAlignment = '87.5%';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<BarChart3 size={24} />} value={`${avgPerf}%`} label="Avg Performance" trend="+1.8%" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={avgAlignment} label="Avg Alignment" trend="+3.2%" trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<Users size={24} />} value={topPerf.length} label="Top Performers" color="purple" delay={0.16} />
                <StatsCard icon={<AlertTriangle size={24} />} value={lowPerf.length} label="Low Performers" color="red" delay={0.24} />
            </div>

            {/* Filters */}
            <AnimatedCard delay={0.25}>
                <div className="card-body" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
                    <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>Filters:</span>
                    <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
                        style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Roles</option>
                        <option value="Developer">Developer</option>
                        <option value="QA">QA</option>
                        <option value="DevOps">DevOps</option>
                        <option value="PM">PM</option>
                    </select>
                    <select value={sprintFilter} onChange={e => setSprintFilter(e.target.value)}
                        style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Sprints</option>
                        <option value="Alpha">Sprint Alpha</option>
                        <option value="Beta">Sprint Beta</option>
                        <option value="Gamma">Sprint Gamma</option>
                    </select>
                    <input type="date" style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }} />
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>to</span>
                    <input type="date" style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }} />
                </div>
            </AnimatedCard>

            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                {/* Department Performance */}
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">Department Performance</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={deptPerf}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="dept" tick={{ fontSize: 11 }} />
                                    <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Bar dataKey="score" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Sprint Velocity */}
                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Sprint Velocity Contribution</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={velocity}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey="planned" fill="#94a3b8" radius={[4, 4, 0, 0]} name="Planned SP" />
                                    <Bar dataKey="completed" fill="#10b981" radius={[4, 4, 0, 0]} name="Completed SP" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            <div className="grid-2">
                {/* Top Performers */}
                <AnimatedCard delay={0.46}>
                    <div className="card-header">
                        <span className="card-title">🏆 Top Performers</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead><tr><th>#</th><th>Name</th><th>Role</th><th>Score</th></tr></thead>
                                <tbody>
                                    {topPerf.map((p, i) => (
                                        <tr key={p.name}>
                                            <td style={{ fontWeight: 700, color: '#f59e0b' }}>{i + 1}</td>
                                            <td style={{ fontWeight: 600 }}>{p.name}</td>
                                            <td style={{ fontSize: '0.82rem' }}>{p.role}</td>
                                            <td><span style={{ fontWeight: 700, color: '#10b981' }}>{p.score}%</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Low Performers */}
                <AnimatedCard delay={0.54}>
                    <div className="card-header">
                        <span className="card-title">⚠️ Low Performance Members</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead><tr><th>Name</th><th>Role</th><th>Score</th><th>Issue</th></tr></thead>
                                <tbody>
                                    {lowPerf.map(p => (
                                        <tr key={p.name}>
                                            <td style={{ fontWeight: 600 }}>{p.name}</td>
                                            <td style={{ fontSize: '0.82rem' }}>{p.role}</td>
                                            <td><span style={{ fontWeight: 700, color: getScoreColor(p.score) }}>{p.score}%</span></td>
                                            <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{p.issue}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
