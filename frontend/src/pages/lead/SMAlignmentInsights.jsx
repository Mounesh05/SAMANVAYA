import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Cpu, TrendingDown, AlertTriangle, RefreshCw } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { leadAPI } from '../../services/api';

export default function SMAlignmentInsights() {
    const [alignmentBreakdown, setAlignmentBreakdown] = useState([]);
    const [lowAlignmentStories, setLowAlignmentStories] = useState([]);
    const [trendData, setTrendData] = useState([]);

    useEffect(() => {
        leadAPI.alignmentInsights().then(data => {
            if (!data) return;
            if (Array.isArray(data.alignment_breakdown)) setAlignmentBreakdown(data.alignment_breakdown);
            if (Array.isArray(data.low_alignment_stories)) setLowAlignmentStories(data.low_alignment_stories);
            if (Array.isArray(data.trend_data)) setTrendData(data.trend_data);
        }).catch(() => { });
    }, []);

    const getColor = v => v >= 80 ? '#10b981' : v >= 65 ? '#f59e0b' : '#ef4444';

    const teamAvg = alignmentBreakdown.length ? Math.round(alignmentBreakdown.reduce((a, b) => a + (((b.keyword || 0) + (b.filePath || 0) + (b.semantic || 0)) / 3), 0) / alignmentBreakdown.length) : 0;
    const repeatOffenders = lowAlignmentStories.filter(s => (s.offenses || 0) > 1).length;
    const sprintTrendVal = trendData.length >= 2 ? (trendData[trendData.length - 1].avg - trendData[trendData.length - 2].avg) : 0;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Cpu size={24} />} value={`${teamAvg}%`} label="Team Avg Alignment" color="blue" delay={0} />
                <StatsCard icon={<TrendingDown size={24} />} value={lowAlignmentStories.length} label="Low Alignment Stories" color="red" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={repeatOffenders} label="Repeat Offenders" color="orange" delay={0.16} />
                <StatsCard icon={<RefreshCw size={24} />} value={`${sprintTrendVal >= 0 ? '+' : ''}${sprintTrendVal}%`} label="Sprint-on-Sprint Trend" color="green" delay={0.24} />
            </div>

            {/* Alignment Breakdown */}
            <AnimatedCard delay={0.3}>
                <div className="card-header"><span className="card-title">Alignment Breakdown by Developer</span></div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>Developer</th><th>Keyword Match %</th><th>File Path Relevance %</th><th>Semantic Match %</th><th>Scope Drift %</th></tr>
                            </thead>
                            <tbody>
                                {alignmentBreakdown.map(d => (
                                    <tr key={d.name}>
                                        <td style={{ fontWeight: 600 }}>{d.name}</td>
                                        <td><span style={{ fontWeight: 700, color: d.keyword >= 80 ? '#10b981' : d.keyword >= 65 ? '#f59e0b' : '#ef4444' }}>{d.keyword}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: d.filePath >= 80 ? '#10b981' : d.filePath >= 65 ? '#f59e0b' : '#ef4444' }}>{d.filePath}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: d.semantic >= 80 ? '#10b981' : d.semantic >= 65 ? '#f59e0b' : '#ef4444' }}>{d.semantic}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: d.scopeDrift > 20 ? '#ef4444' : d.scopeDrift > 10 ? '#f59e0b' : '#10b981' }}>{d.scopeDrift}%</span></td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Top 5 Low Alignment */}
            <AnimatedCard delay={0.38} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">⚠ Top 5 Low Alignment Stories</span></div>
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {lowAlignmentStories.map((s, i) => (
                        <div key={s.id} style={{ padding: '12px 16px', background: s.alignment < 65 ? '#fef2f2' : '#fffbeb', border: `1px solid ${s.alignment < 65 ? '#fecaca' : '#fde68a'}`, borderRadius: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                                <span style={{ fontWeight: 700, fontSize: '0.88rem' }}>#{i + 1} {s.title}</span>
                                <span style={{ marginLeft: 8, fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{s.id} · {s.developer}</span>
                                <div style={{ fontSize: '0.75rem', color: s.offenses >= 3 ? '#ef4444' : '#f59e0b', marginTop: 2, fontWeight: 600 }}>{s.note}</div>
                            </div>
                            <div style={{ textAlign: 'right' }}>
                                <div style={{ fontWeight: 800, fontSize: '1.1rem', color: s.alignment < 65 ? '#ef4444' : '#f59e0b' }}>{s.alignment}%</div>
                                {s.offenses >= 2 && <span style={{ fontSize: '0.7rem', background: '#ef444420', color: '#ef4444', padding: '2px 6px', borderRadius: 100, fontWeight: 700 }}>REPEAT OFFENDER</span>}
                            </div>
                        </div>
                    ))}
                </div>
            </AnimatedCard>

            {/* Trend Graph */}
            <AnimatedCard delay={0.46} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">Sprint-to-Sprint Alignment Trend</span></div>
                <div className="card-body">
                    <div className="chart-container">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={trendData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                <YAxis domain={[60, 100]} tick={{ fontSize: 12 }} unit="%" />
                                <Tooltip formatter={v => `${v}%`} />
                                <Line type="monotone" dataKey="avg" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 4 }} name="Avg Alignment" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
