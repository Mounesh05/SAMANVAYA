import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { BarChart3, Users, AlertTriangle, TrendingUp, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { pmAPI } from '../../services/api';


export default function PMWorkload() {
    const [workloadData, setWorkloadData] = useState([]);
    const [redistributed, setRedistributed] = useState({});
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        setLoading(true);
        pmAPI.workload()
            .then(data => { if (data?.length) setWorkloadData(data); })
            .catch(err => console.error('Failed to fetch PM Workload:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading workload data...</div>;

    const avgCapacity = workloadData.length ? Math.round(workloadData.reduce((a, w) => a + w.capacity, 0) / workloadData.length) : 0;
    const totalOverdue = workloadData.reduce((a, w) => a + (w.overdue || 0), 0);
    const capacityChart = workloadData.map(w => ({ name: w.name ? w.name.split(' ')[0] : 'Member', capacity: w.capacity || 0, assigned: Math.round((w.assigned || 0) / 10 * 100) }));

    const handleRedistribute = (memberName) => {
        const overloaded = workloadData.find(w => w.name === memberName);
        if (!overloaded) return;

        /* Find member with lowest capacity load */
        const others = workloadData.filter(w => w.name !== memberName && w.capacity < 70);
        if (others.length === 0) return;
        const target = others.reduce((min, w) => w.capacity < min.capacity ? w : min, others[0]);

        setWorkloadData(prev => {
            const tasksToMove = Math.ceil((overloaded.overdue + overloaded.pending) / 2);
            return prev.map(w => {
                if (w.name === memberName) {
                    const newAssigned = Math.max(w.assigned - tasksToMove, w.completed);
                    const newPending = Math.max(w.pending - Math.ceil(tasksToMove / 2), 0);
                    const newOverdue = Math.max(w.overdue - Math.floor(tasksToMove / 2), 0);
                    return { ...w, assigned: newAssigned, pending: newPending, overdue: newOverdue, capacity: Math.max(w.capacity - tasksToMove * 8, 40) };
                }
                if (w.name === target.name) {
                    return { ...w, assigned: w.assigned + tasksToMove, pending: w.pending + tasksToMove, capacity: Math.min(w.capacity + tasksToMove * 8, 100) };
                }
                return w;
            });
        });

        // Persist change
        pmAPI.redistributeWorkload({
            overloaded_name: memberName,
            target_name: target.name
        }).catch(err => console.error('Failed to redistribute PM workload:', err));

        setRedistributed(prev => ({ ...prev, [memberName]: true }));
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={workloadData.length} label="Team Members" color="blue" delay={0} />
                <StatsCard icon={<BarChart3 size={24} />} value={`${avgCapacity}%`} label="Avg Capacity" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={workloadData.filter(w => w.capacity > 80).length} label="Overloaded" color="red" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value={totalOverdue} label="Total Overdue" color="orange" delay={0.24} />
            </div>

            {/* Workload Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Workload Overview</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>Member</th><th>Assigned</th><th>Completed</th><th>Pending</th><th>Overdue</th><th>Capacity %</th></tr>
                            </thead>
                            <tbody>
                                {workloadData.map(w => (
                                    <tr key={w.name} style={{ background: w.capacity > 80 ? '#fef2f2' : 'transparent' }}>
                                        <td style={{ fontWeight: 600 }}>{w.name}</td>
                                        <td style={{ fontWeight: 700 }}>{w.assigned}</td>
                                        <td><span style={{ color: '#10b981', fontWeight: 700 }}>{w.completed}</span></td>
                                        <td><span style={{ color: '#f59e0b', fontWeight: 700 }}>{w.pending}</span></td>
                                        <td><span style={{ color: w.overdue > 0 ? '#ef4444' : '#10b981', fontWeight: 700 }}>{w.overdue}</span></td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ flex: 1, height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden', maxWidth: 120 }}>
                                                    <div style={{ width: `${w.capacity}%`, height: '100%', background: w.capacity > 80 ? '#ef4444' : w.capacity > 60 ? '#f59e0b' : '#10b981', borderRadius: 4, transition: 'width 0.5s ease' }} />
                                                </div>
                                                <span style={{ fontWeight: 700, fontSize: '0.85rem', color: w.capacity > 80 ? '#ef4444' : 'var(--text-primary)' }}>{w.capacity}%</span>
                                                {w.capacity > 80 && <span style={{ fontSize: '0.72rem', color: '#ef4444', fontWeight: 600 }}>⚠ OVERLOADED</span>}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Capacity vs Assigned Chart */}
            <AnimatedCard delay={0.38} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title">Capacity vs Workload</span>
                </div>
                <div className="card-body">
                    <div className="chart-container">
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={capacityChart}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                                <YAxis tick={{ fontSize: 12 }} domain={[0, 100]} />
                                <Tooltip formatter={(v) => `${v}%`} />
                                <Legend />
                                <Bar dataKey="capacity" name="Current Load" radius={[4, 4, 0, 0]}>
                                    {capacityChart.map((entry, i) => (
                                        <Cell key={i} fill={entry.capacity > 80 ? '#ef4444' : entry.capacity > 60 ? '#f59e0b' : '#10b981'} />
                                    ))}
                                </Bar>
                                <Bar dataKey="assigned" fill="#94a3b8" name="Ideal Capacity" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </AnimatedCard>

            {/* Overload Alerts */}
            <AnimatedCard delay={0.46} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">⚠ Overload Alerts</span></div>
                <div className="card-body">
                    {workloadData.filter(w => w.capacity > 80).length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                            {workloadData.filter(w => w.capacity > 80).map(w => (
                                <div key={w.name} style={{ padding: '12px 16px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 'var(--radius-sm)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <span style={{ fontWeight: 700, color: '#991b1b' }}>{w.name}</span>
                                        <span style={{ color: '#b91c1c', fontSize: '0.85rem', marginLeft: 8 }}>is at {w.capacity}% capacity with {w.overdue} overdue task(s)</span>
                                    </div>
                                    <button
                                        className="btn btn-sm"
                                        onClick={() => handleRedistribute(w.name)}
                                        disabled={redistributed[w.name]}
                                        style={{
                                            background: redistributed[w.name] ? '#d1d5db' : '#ef4444',
                                            color: redistributed[w.name] ? '#6b7280' : '#fff',
                                            border: 'none', borderRadius: 'var(--radius-sm)',
                                            padding: '6px 14px', cursor: redistributed[w.name] ? 'default' : 'pointer',
                                            fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6
                                        }}>
                                        <RefreshCw size={13} /> {redistributed[w.name] ? 'Redistributed ✓' : 'Redistribute'}
                                    </button>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div style={{ textAlign: 'center', padding: 20, color: '#10b981', fontWeight: 600 }}>
                            ✅ No members are currently overloaded
                        </div>
                    )}
                </div>
            </AnimatedCard>
        </div>
    );
}
