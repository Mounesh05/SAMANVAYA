import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { BarChart2, AlertTriangle, Users, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Cell } from 'recharts';
import { leadAPI } from '../../services/api';

export default function SMWorkload() {
    const [data, setData] = useState([]);
    const [suggestions, setSuggestions] = useState([]);
    const [loading, setLoading] = useState(true);
    const [redistributed, setRedistributed] = useState({});

    useEffect(() => {
        leadAPI.workload().then(res => {
            if (!res) return;
            if (res.workload_data?.length) setData(res.workload_data);
            if (res.suggestions?.length) setSuggestions(res.suggestions);
        }).catch(err => console.error('Failed to fetch workload data:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading workload data...</div>;


    const handleRedistribute = (name) => {
        const overloaded = data.find(w => w.name === name);
        const target = data.filter(w => w.name !== name && w.capacity < 65).sort((a, b) => a.capacity - b.capacity)[0];
        if (!target) return;

        const updatedOverloaded = { ...overloaded, stories: overloaded.stories - 1, points: overloaded.points - 5, capacity: Math.max(overloaded.capacity - 14, 40) };
        const updatedTarget = { ...target, stories: target.stories + 1, points: target.points + 5, capacity: Math.min(target.capacity + 14, 100) };

        setData(prev => prev.map(w => {
            if (w.name === name) return updatedOverloaded;
            if (w.name === target.name) return updatedTarget;
            return w;
        }));
        setRedistributed(p => ({ ...p, [name]: true }));

        // Persist change via centralized endpoint
        leadAPI.redistributeWorkload({
            overloaded_name: name,
            target_name: target.name
        }).catch(err => console.error('Failed to redistribute workload:', err));
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={data.length} label="Team Members" color="blue" delay={0} />
                <StatsCard icon={<BarChart2 size={24} />} value={`${Math.round(data.reduce((a, w) => a + w.capacity, 0) / data.length)}%`} label="Avg Capacity" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={data.filter(w => w.capacity > 80).length} label="Overloaded" color="red" delay={0.16} />
                <StatsCard icon={<RefreshCw size={24} />} value={data.reduce((a, w) => a + w.points, 0)} label="Total Story Points" color="purple" delay={0.24} />
            </div>

            {/* Stories & Points per Developer */}
            <AnimatedCard delay={0.3}>
                <div className="card-header"><span className="card-title">Stories & Points per Developer</span></div>
                <div className="card-body">
                    <div style={{ height: 220 }}>
                        <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={data}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="name" tick={{ fontSize: 11 }} tickFormatter={v => v.split(' ')[0]} />
                                <YAxis tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Legend />
                                <Bar dataKey="stories" name="Active Stories" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="points" name="Story Points" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                                <Bar dataKey="reviewLoad" name="Review Load" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </AnimatedCard>

            {/* Capacity Bar Chart */}
            <AnimatedCard delay={0.38} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">Capacity Utilization</span></div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead><tr><th>Member</th><th>Stories</th><th>Story Points</th><th>Review Load</th><th>Capacity</th></tr></thead>
                            <tbody>
                                {data.map(w => (
                                    <tr key={w.name}>
                                        <td style={{ fontWeight: 600 }}>{w.name}</td>
                                        <td style={{ fontWeight: 700 }}>{w.stories}</td>
                                        <td style={{ fontWeight: 700 }}>{w.points} SP</td>
                                        <td>{w.reviewLoad}</td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ width: 100, height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
                                                    <div style={{ width: `${w.capacity}%`, height: '100%', background: w.capacity > 80 ? '#ef4444' : w.capacity > 60 ? '#f59e0b' : '#10b981', borderRadius: 4, transition: 'width 0.5s ease' }} />
                                                </div>
                                                <span style={{ fontWeight: 700, color: w.capacity > 80 ? '#ef4444' : 'inherit' }}>{w.capacity}%</span>
                                                {w.capacity > 80 && <span style={{ background: '#ef4444', color: '#fff', fontSize: '0.65rem', fontWeight: 700, padding: '2px 6px', borderRadius: 100 }}>OVERLOADED</span>}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Overload Suggestions */}
            {suggestions.length > 0 && (
                <AnimatedCard delay={0.46} style={{ marginTop: 20 }}>
                    <div className="card-header"><span className="card-title">⚠ Overload Alerts & Suggestions</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {suggestions.map(s => (
                            <div key={s.member} style={{ padding: '14px 16px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                <div>
                                    <span style={{ fontWeight: 700, color: '#991b1b' }}>{s.member}</span>
                                    <span style={{ color: '#b91c1c', marginLeft: 8, fontSize: '0.85rem' }}>is at {s.capacity}% capacity</span>
                                    <div style={{ fontSize: '0.8rem', color: '#374151', marginTop: 4 }}>💡 Suggestion: {s.suggestion}</div>
                                </div>
                                <button onClick={() => handleRedistribute(s.member)} disabled={redistributed[s.member]}
                                    style={{ padding: '6px 14px', borderRadius: 8, border: 'none', background: redistributed[s.member] ? '#d1d5db' : '#ef4444', color: redistributed[s.member] ? '#6b7280' : '#fff', fontWeight: 700, cursor: redistributed[s.member] ? 'default' : 'pointer', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <RefreshCw size={13} /> {redistributed[s.member] ? 'Done ✓' : 'Redistribute'}
                                </button>
                            </div>
                        ))}
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
