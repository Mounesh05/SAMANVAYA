import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { TrendingUp, CheckCircle, Clock, Star } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { leadAPI } from '../../services/api';

export default function SMTeamPerformance() {
    const [memberPerf, setMemberPerf] = useState([]);
    const [sprintTrend, setSprintTrend] = useState([]);

    useEffect(() => {
        leadAPI.teamPerformance().then(data => {
            if (!data) return;
            if (Array.isArray(data.member_perf)) setMemberPerf(data.member_perf);
            if (Array.isArray(data.sprint_trend)) setSprintTrend(data.sprint_trend);
        }).catch(() => { });
    }, []);

    const getColor = v => v >= 80 ? '#10b981' : v >= 65 ? '#f59e0b' : '#ef4444';

    const avgCompletion = memberPerf.length ? Math.round(memberPerf.reduce((a, b) => a + (b.completion || 0), 0) / memberPerf.length) : 0;
    const avgAlignment = memberPerf.length ? Math.round(memberPerf.reduce((a, b) => a + (b.alignmentAvg || 0), 0) / memberPerf.length) : 0;
    const avgDelay = memberPerf.length ? (memberPerf.reduce((a, b) => a + parseFloat(b.reviewDelayAvg || 0), 0) / memberPerf.length).toFixed(1) : '0';
    const avgBehaviour = memberPerf.length ? (memberPerf.reduce((a, b) => a + (b.behaviourScore || 0), 0) / memberPerf.length).toFixed(1) : '0';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckCircle size={24} />} value={`${avgCompletion}%`} label="Sprint Completion" color="green" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${avgAlignment}%`} label="Avg AI Alignment" color="blue" delay={0.08} />
                <StatsCard icon={<Clock size={24} />} value={`${avgDelay}d`} label="Avg Review Delay" color="orange" delay={0.16} />
                <StatsCard icon={<Star size={24} />} value={avgBehaviour} label="Avg Behaviour Score" color="purple" delay={0.24} />
            </div>

            {/* Per-Member Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header"><span className="card-title">Sprint-Level Performance by Member</span></div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>Member</th><th>Completion %</th><th>Alignment Avg</th><th>Review Delay Avg</th><th>Rejection Rate</th><th>Behaviour Score</th></tr>
                            </thead>
                            <tbody>
                                {memberPerf.map(m => (
                                    <tr key={m.name}>
                                        <td style={{ fontWeight: 600 }}>{m.name}</td>
                                        <td><span style={{ fontWeight: 700, color: getColor(m.completion) }}>{m.completion}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: getColor(m.alignmentAvg) }}>{m.alignmentAvg}%</span></td>
                                        <td style={{ color: parseFloat(m.reviewDelayAvg) > 3 ? '#ef4444' : 'var(--text-primary)', fontWeight: 600 }}>{m.reviewDelayAvg}</td>
                                        <td><span style={{ fontWeight: 700, color: m.rejectionRate > 15 ? '#ef4444' : m.rejectionRate > 8 ? '#f59e0b' : '#10b981' }}>{m.rejectionRate}%</span></td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <span style={{ fontWeight: 700, color: m.behaviourScore >= 8 ? '#10b981' : m.behaviourScore >= 7 ? '#f59e0b' : '#ef4444' }}>{m.behaviourScore}</span>
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>/10</span>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Sprint Trend Graph */}
            <AnimatedCard delay={0.38} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">Sprint-to-Sprint Performance Trend</span></div>
                <div className="card-body">
                    <div style={{ maxWidth: 720, margin: '0 auto' }}>
                        <div style={{ height: 320 }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={sprintTrend} barCategoryGap="30%">
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} unit="%" />
                                    <Tooltip formatter={v => `${v}%`} />
                                    <Legend />
                                    <Bar dataKey="completion" name="Completion %" fill="#10b981" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="alignment" name="Alignment %" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                                    <Bar dataKey="rejection" name="Rejection Rate %" fill="#ef4444" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
