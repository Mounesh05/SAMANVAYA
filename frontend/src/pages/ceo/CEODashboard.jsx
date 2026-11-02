import { useState, useEffect } from 'react';
import { Briefcase, Activity, AlertTriangle, Users } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import {
    AreaChart, Area, PieChart, Pie, Cell,
    XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';
import { ceoAPI, dashboardAPI } from '../../services/api';

/* Custom label renderer for pie chart – shows percentage */
const renderPercentLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent }) => {
    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    if (percent < 0.05) return null;
    return (
        <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central"
            style={{ fontSize: '0.75rem', fontWeight: 700 }}>
            {`${(percent * 100).toFixed(0)}%`}
        </text>
    );
};

export default function CEODashboard() {
    const navigate = useNavigate();
    const [executionData, setExecutionData] = useState([]);
    const [sprintStatus, setSprintStatus] = useState([]);
    const [escalations, setEscalations] = useState([]);
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [exec, sprint, esc, s] = await Promise.all([
                    ceoAPI.executionWeeks(),
                    ceoAPI.sprintStatus(),
                    ceoAPI.escalations(),
                    dashboardAPI.ceo()
                ]);
                setExecutionData(exec || []);
                setSprintStatus(sprint || []);
                setEscalations(esc || []);
                setStats(s);
            } catch (err) {
                console.error('Failed to fetch CEO dashboard data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading dashboard...</div>;
    }

    const statusList = Array.isArray(sprintStatus) && sprintStatus.length > 0 ? sprintStatus : [
        { name: 'On Track', value: 14, color: '#10b981' },
        { name: 'At Risk', value: 3, color: '#f59e0b' },
        { name: 'Delayed', value: 1, color: '#ef4444' },
        { name: 'Completed', value: 18, color: '#3b82f6' },
    ];
    const totalSprints = statusList.reduce((sum, s) => sum + (s.value || 0), 0) || 1;

    return (
        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Briefcase size={24} />} value={stats?.active_sprints || '0'} label="Active Sprints" trend="+3 new" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<Activity size={24} />} value="91%" label="Execution Health" trend="+5.2%" trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={stats?.open_escalations || '0'} label="Open Escalations" trend="-2 this week" trendDir="down" color="orange" delay={0.16} />
                <StatsCard icon={<Users size={24} />} value={stats?.total_employees?.toLocaleString() || '0'} label="Total Employees" trend="+18 this month" trendDir="up" color="purple" delay={0.24} />
            </div>

            {/* Charts Row */}
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">Execution Health Trend</span>
                        <span className="badge badge-info">Last 8 Weeks</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={executionData}>
                                    <defs>
                                        <linearGradient id="healthGrad" x1="0" y1="0" x2="0" y2="1">
                                            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                                            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                                        </linearGradient>
                                    </defs>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} domain={[60, 100]} />
                                    <Tooltip />
                                    <Area type="monotone" dataKey="target" stroke="#d1d5db" strokeDasharray="5 5" fill="none" />
                                    <Area type="monotone" dataKey="health" stroke="#10b981" fill="url(#healthGrad)" strokeWidth={2.5} dot={{ r: 4, fill: '#10b981' }} />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Sprint Status Distribution</span>
                        <span className="badge badge-info">{totalSprints} Sprints</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        <div className="chart-container" style={{ display: 'flex', alignItems: 'center' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie
                                        data={statusList}
                                        cx="50%"
                                        cy="50%"
                                        innerRadius={60}
                                        outerRadius={100}
                                        dataKey="value"
                                        paddingAngle={3}
                                        label={renderPercentLabel}
                                        labelLine={false}
                                    >
                                        {statusList.map((entry, i) => (
                                            <Cell key={i} fill={entry.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip formatter={(value, name) => [`${value} (${((value / totalSprints) * 100).toFixed(1)}%)`, name]} />
                                    <Legend formatter={(value) => {
                                        const item = statusList.find(s => s.name === value);
                                        return item ? `${value} – ${((item.value / totalSprints) * 100).toFixed(0)}%` : value;
                                    }} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* Escalations – full width */}
            <AnimatedCard delay={0.46}>
                <div className="card-header">
                    <span className="card-title">Recent Escalations</span>
                    <button className="btn btn-sm btn-secondary" onClick={() => navigate('/escalations')}>View All</button>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Issue</th>
                                    <th>Severity</th>
                                    <th>Status</th>
                                    <th>Time</th>
                                </tr>
                            </thead>
                            <tbody>
                                {escalations.map(esc => (
                                    <tr key={esc.id}>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{esc.title}</div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>{esc.project}</div>
                                        </td>
                                        <td>
                                            <span className={`badge ${esc.severity === 'Critical' ? 'badge-danger' : esc.severity === 'High' ? 'badge-warning' : 'badge-info'}`}>
                                                {esc.severity}
                                            </span>
                                        </td>
                                        <td>
                                            <span className={`badge ${esc.status === 'Resolved' ? 'badge-success' : esc.status === 'Open' ? 'badge-warning' : 'badge-danger'}`}>
                                                {esc.status}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{esc.time}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
