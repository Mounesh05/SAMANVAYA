import { useState, useEffect } from 'react';
import { Users, CheckSquare, Inbox, Cpu, TrendingUp } from 'lucide-react';
import { dashboardAPI } from '../../services/api';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import {
    BarChart, Bar, LineChart, Line,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

export default function LeadDashboard() {
    const [stats, setStats] = useState(null);
    const [teamMembersData, setTeamMembersData] = useState([]);
    const [workloadData, setWorkloadData] = useState([]);
    const [perfTrend, setPerfTrend] = useState([]);
    const [reviewQueue, setReviewQueue] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [members, workload, perf, review] = await Promise.all([
                    leadAPI.dashboardTeamMembers(),
                    leadAPI.dashboardWorkloadChart(),
                    leadAPI.dashboardPerfTrend(),
                    leadAPI.dashboardReviewQueue()
                ]);

                setTeamMembersData(members || []);
                setWorkloadData(workload || []);
                setPerfTrend(perf || []);
                setReviewQueue(review || []);

                // Calculate stats from members data if needed, or fetch from a dashboard stats endpoint
                // For now, using length of members and active tasks count from stories could be alternatives
            } catch (err) {
                console.error('Failed to fetch Lead Dashboard data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading dashboard...</div>;
    }

    return (
        <div>
            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={teamMembersData.length.toString()} label="Team Members" color="blue" delay={0} />
                <StatsCard icon={<CheckSquare size={24} />} value={teamMembersData.reduce((acc, m) => acc + (m.tasks || 0), 0).toString()} label="Total Tasks" trend={`${teamMembersData.reduce((acc, m) => acc + (m.completed || 0), 0)} completed`} trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<Inbox size={24} />} value={reviewQueue.length.toString()} label="Review Queue" trend="2 urgent" color="orange" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value={(perfTrend[perfTrend.length - 1]?.score || 0) + '%'} label="Current Performance" trend="+7%" trendDir="up" color="green" delay={0.24} />
            </div>
            {/* Team Table + Review Queue */}
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">My Team</span>
                        <span className="badge badge-info">{teamMembersData.length} members</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <thead>
                                <tr><th>Name</th><th>Role</th><th>Tasks</th><th>Status</th></tr>
                            </thead>
                            <tbody>
                                {teamMembersData.map(m => (
                                    <tr key={m.id}>
                                        <td style={{ fontWeight: 600 }}>{m.name}</td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{m.role}</td>
                                        <td>
                                            <span style={{ fontWeight: 600 }}>{m.completed}</span>
                                            <span style={{ color: 'var(--text-tertiary)' }}>/{m.tasks}</span>
                                        </td>
                                        <td>
                                            <span className={`badge ${m.status === 'Active' ? 'badge-success' : 'badge-warning'}`}>{m.status}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Review Queue</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <thead>
                                <tr><th>Item</th><th>Priority</th><th>Submitted</th></tr>
                            </thead>
                            <tbody>
                                {reviewQueue.map(r => (
                                    <tr key={r.id}>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{r.title}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>by {r.author}</div>
                                        </td>
                                        <td>
                                            <span className={`badge ${r.priority === 'High' ? 'badge-danger' : r.priority === 'Medium' ? 'badge-warning' : 'badge-info'}`}>
                                                {r.priority}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{r.submitted}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>
            </div >

            {/* Charts */}
            < div className="grid-2" >
                <AnimatedCard delay={0.46}>
                    <div className="card-header">
                        <span className="card-title">Workload Overview</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={workloadData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Legend />
                                    <Bar dataKey="assigned" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Assigned" />
                                    <Bar dataKey="completed" fill="#10b981" radius={[4, 4, 0, 0]} name="Completed" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.54}>
                    <div className="card-header">
                        <span className="card-title">Team Performance Trend</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={perfTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} domain={[60, 100]} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Line type="monotone" dataKey="score" stroke="#c0392b" strokeWidth={2.5} dot={{ r: 5, fill: '#c0392b' }} />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div >
        </div >
    );
}
