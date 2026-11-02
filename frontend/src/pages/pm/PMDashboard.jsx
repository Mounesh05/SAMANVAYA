import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI } from '../../services/api';
import { Folder, CheckSquare, CheckCircle, Zap, Clock } from 'lucide-react';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import {
    PieChart, Pie, Cell, BarChart, Bar,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

export default function PMDashboard() {
    const navigate = useNavigate();
    const [dashData, setDashData] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        dashboardAPI.pm().then(setDashData)
            .catch(err => console.error('Failed to fetch PM dashboard:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading dashboard...</div>;

    const taskDistribution = dashData?.task_distribution || [
        { name: 'To Do', value: 18, color: '#6b7280' },
        { name: 'In Progress', value: 24, color: '#3b82f6' },
        { name: 'In Review', value: 8, color: '#f59e0b' },
        { name: 'Done', value: 42, color: '#10b981' },
    ];
    const sprintProgress = dashData?.sprint_progress || [
        { name: 'Alpha', progress: 85, tasks: 34 },
        { name: 'Beta', progress: 62, tasks: 28 },
        { name: 'Gamma', progress: 94, tasks: 41 },
        { name: 'Delta', progress: 38, tasks: 22 },
        { name: 'Epsilon', progress: 71, tasks: 19 },
    ];
    const approvals = dashData?.approvals || [
        { id: 1, title: 'Feature Branch Merge – Auth Module', requester: 'Vikram Singh', type: 'Code Review', time: '30 min ago', priority: 'High' },
        { id: 2, title: 'Budget Increase – Cloud Infra', requester: 'Ananya Reddy', type: 'Budget', time: '2 hours ago', priority: 'Medium' },
        { id: 3, title: 'New Hire – Senior Dev', requester: 'Priya Sharma', type: 'HR', time: '5 hours ago', priority: 'Low' },
        { id: 4, title: 'Sprint Scope Change – Sprint Beta', requester: 'Sneha Iyer', type: 'Scope', time: '1 day ago', priority: 'High' },
    ];
    const signals = dashData?.signals || [
        { id: 1, title: 'Sprint velocity drop in Team Alpha', type: 'warning', time: '1 hour ago' },
        { id: 2, title: 'Sprint Gamma ahead of schedule', type: 'success', time: '3 hours ago' },
        { id: 3, title: 'Blocked dependency in Sprint Delta', type: 'danger', time: '6 hours ago' },
        { id: 4, title: 'Code quality metrics improving', type: 'info', time: '1 day ago' },
    ];

    return (

        <div>
            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Folder size={24} />} value={dashData?.active_sprints || '0'} label="Active Sprints" trend={dashData?.sprints_trend || ''} trendDir={dashData?.sprints_trend?.includes('+') ? 'up' : 'down'} color="blue" delay={0} />
                <StatsCard icon={<CheckSquare size={24} />} value={dashData?.total_tasks || '0'} label="Total Tasks" trend={dashData?.tasks_trend || ''} color="orange" delay={0.08} />
                <StatsCard icon={<CheckCircle size={24} />} value={dashData?.pending_approvals || '0'} label="Pending Approvals" color="red" delay={0.16} />
                <StatsCard icon={<Zap size={24} />} value={`${dashData?.sprint_velocity || '0'}%`} label="Sprint Velocity" trend={dashData?.velocity_trend || ''} trendDir={dashData?.velocity_trend?.includes('+') ? 'up' : 'down'} color="green" delay={0.24} />
            </div>

            <div className="grid-2 mb-lg">
                {/* Task Distribution */}
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">Task Distribution</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container" style={{ display: 'flex', alignItems: 'center' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={taskDistribution} cx="50%" cy="50%" innerRadius={55} outerRadius={95} dataKey="value" paddingAngle={3}>
                                        {taskDistribution.map((entry, i) => (
                                            <Cell key={i} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                    <Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Project Progress */}
                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Sprint Progress</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={sprintProgress} layout="vertical">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
                                    <YAxis dataKey="name" type="category" tick={{ fontSize: 12 }} width={60} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Bar dataKey="progress" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            <div className="grid-2">
                {/* Approvals */}
                <AnimatedCard delay={0.46}>
                    <div className="card-header">
                        <span className="card-title">Pending Approvals</span>
                        <button className="btn btn-sm btn-secondary" onClick={() => navigate('/approvals')}>View All</button>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table">
                            <thead>
                                <tr><th>Request</th><th>Type</th><th>Priority</th><th>Time</th></tr>
                            </thead>
                            <tbody>
                                {approvals.map(a => (
                                    <tr key={a.id}>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{a.title}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>by {a.requester}</div>
                                        </td>
                                        <td><span className="badge badge-neutral">{a.type}</span></td>
                                        <td>
                                            <span className={`badge ${a.priority === 'High' ? 'badge-danger' : a.priority === 'Medium' ? 'badge-warning' : 'badge-info'}`}>
                                                {a.priority}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{a.time}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </AnimatedCard>

                {/* Execution Signals */}
                <AnimatedCard delay={0.54}>
                    <div className="card-header">
                        <span className="card-title">Execution Signals</span>
                    </div>
                    <div className="card-body">
                        <div className="timeline">
                            {signals.map(s => (
                                <div key={s.id} className="timeline-item">
                                    <div className="timeline-item-title">
                                        <span className={`badge badge-${s.type}`} style={{ marginRight: 8 }}>
                                            {s.type === 'warning' ? '⚠' : s.type === 'success' ? '✓' : s.type === 'danger' ? '✕' : 'ℹ'}
                                        </span>
                                        {s.title}
                                    </div>
                                    <div className="timeline-item-time">{s.time}</div>
                                </div>
                            ))}
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
