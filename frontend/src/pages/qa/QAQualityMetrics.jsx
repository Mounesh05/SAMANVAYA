import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { BarChart2, TrendingUp, Bug, RefreshCw, Shield } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { qaAPI } from '../../services/api';

export default function QAQualityMetrics() {
    const [qualityFormula, setQualityFormula] = useState([]);
    const [sprintTrend, setSprintTrend] = useState([]);

    useEffect(() => {
        qaAPI.qualityMetrics().then(data => {
            if (!data) return;
            if (data.quality_formula?.length) setQualityFormula(data.quality_formula);
            if (data.sprint_trend?.length) setSprintTrend(data.sprint_trend);
        }).catch(() => { });
    }, []);

    const qualityScore = qualityFormula.length
        ? Math.round(qualityFormula[0].value * 0.4 + (qualityFormula[1]?.value || 0) * 0.2 +
            (qualityFormula[2]?.value || 0) * 0.15 + (qualityFormula[3]?.value || 0) * 0.15 +
            (qualityFormula[4]?.value || 0) * 0.1)
        : 0;
    const radialData = [{ name: 'Quality', value: qualityScore, fill: qualityScore >= 80 ? '#10b981' : qualityScore >= 70 ? '#f59e0b' : '#ef4444' }];

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Shield size={24} />} value={`${qualityScore}%`} label="Quality Score" color="green" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={qualityFormula[0] ? `${qualityFormula[0].value}%` : '--'} label="Test Pass Rate" color="green" delay={0.08} />
                <StatsCard icon={<Bug size={24} />} value={qualityFormula[1] ? `${qualityFormula[1].value}%` : '--'} label="Defect Density Score" color="blue" delay={0.16} />
                <StatsCard icon={<RefreshCw size={24} />} value={qualityFormula[2] ? `${qualityFormula[2].value}%` : '--'} label="Reopen Rate Score" color="green" delay={0.24} />
            </div>

            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header"><span className="card-title">Quality Score Formula</span></div>
                    <div className="card-body">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {qualityFormula.map((q, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <div style={{ width: 120, fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>{q.label}</div>
                                    <span style={{ fontSize: '0.72rem', fontWeight: 700, color: 'var(--text-tertiary)', minWidth: 32 }}>{q.weight}</span>
                                    <div style={{ flex: 1, height: 8, borderRadius: 4, background: '#e5e7eb' }}>
                                        <div style={{ height: '100%', borderRadius: 4, width: `${q.value}%`, background: q.color, transition: 'width 0.5s ease' }} />
                                    </div>
                                    <span style={{ fontWeight: 700, fontSize: '0.82rem', color: q.color, minWidth: 36, textAlign: 'right' }}>{q.value}%</span>
                                </div>
                            ))}
                        </div>
                        <div style={{
                            marginTop: 20, padding: '14px 18px', borderRadius: 'var(--radius-md)',
                            background: qualityScore >= 80 ? 'var(--success-bg)' : 'var(--warning-bg)',
                            borderLeft: `4px solid ${qualityScore >= 80 ? 'var(--success)' : 'var(--warning)'}`,
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>Overall Quality Score</span>
                            <span style={{ fontWeight: 800, fontSize: '1.4rem', color: qualityScore >= 80 ? '#10b981' : '#f59e0b' }}>{qualityScore}%</span>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.38}>
                    <div className="card-header"><span className="card-title">Quality Score Gauge</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px 16px' }}>
                        {(() => {
                            const size = 220;
                            const cx = 110, cy = 115;
                            const r = 80;
                            const startAngle = 180; // left
                            const endAngle = 0;     // right
                            const pct = Math.min(100, Math.max(0, qualityScore)) / 100;
                            const scoreAngle = 180 - pct * 180; // angle in degrees (180→0)
                            const toRad = d => (d * Math.PI) / 180;

                            // Arc helper
                            const arcPath = (from, to, isBg) => {
                                const x1 = cx + r * Math.cos(toRad(from));
                                const y1 = cy - r * Math.sin(toRad(from));
                                const x2 = cx + r * Math.cos(toRad(to));
                                const y2 = cy - r * Math.sin(toRad(to));
                                const large = (from - to) > 180 ? 1 : 0;
                                return `M ${x1} ${y1} A ${r} ${r} 0 ${large} 1 ${x2} ${y2}`;
                            };

                            // Needle tip point
                            const needleAngle = scoreAngle;
                            const nx = cx + (r - 10) * Math.cos(toRad(needleAngle));
                            const ny = cy - (r - 10) * Math.sin(toRad(needleAngle));

                            const gaugeColor = qualityScore >= 80 ? '#10b981' : qualityScore >= 65 ? '#f59e0b' : '#ef4444';
                            const label = qualityScore >= 85 ? 'Excellent' : qualityScore >= 75 ? 'Good' : qualityScore >= 65 ? 'Needs Improvement' : 'At Risk';

                            return (
                                <div style={{ position: 'relative', textAlign: 'center' }}>
                                    <svg width={size} height={size * 0.65} viewBox={`0 0 ${size} ${size * 0.65}`}>
                                        {/* Background arc */}
                                        <path d={arcPath(180, 0, true)} fill="none" stroke="#e5e7eb" strokeWidth={18} strokeLinecap="round" />
                                        {/* Score arc */}
                                        <path d={arcPath(180, scoreAngle, false)} fill="none" stroke={gaugeColor} strokeWidth={18} strokeLinecap="round" />
                                        {/* Tick marks */}
                                        {[0, 25, 50, 75, 100].map(pct => {
                                            const a = 180 - pct * 1.8;
                                            const inner = r - 26, outer = r - 10;
                                            return (
                                                <line key={pct}
                                                    x1={cx + inner * Math.cos(toRad(a))} y1={cy - inner * Math.sin(toRad(a))}
                                                    x2={cx + outer * Math.cos(toRad(a))} y2={cy - outer * Math.sin(toRad(a))}
                                                    stroke="#9ca3af" strokeWidth={1.5} />
                                            );
                                        })}
                                        {/* Tick labels */}
                                        {[{ v: 0, label: '0' }, { v: 50, label: '50' }, { v: 100, label: '100' }].map(({ v, label }) => {
                                            const a = 180 - v * 1.8;
                                            const lx = cx + (r - 38) * Math.cos(toRad(a));
                                            const ly = cy - (r - 38) * Math.sin(toRad(a));
                                            return <text key={v} x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize={9} fill="#9ca3af">{label}</text>;
                                        })}
                                        {/* Needle */}
                                        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="#374151" strokeWidth={2.5} strokeLinecap="round" />
                                        {/* Center dot */}
                                        <circle cx={cx} cy={cy} r={6} fill={gaugeColor} />
                                    </svg>
                                    <div style={{ marginTop: -8 }}>
                                        <div style={{ fontSize: '2.2rem', fontWeight: 800, color: gaugeColor, lineHeight: 1 }}>{qualityScore}%</div>
                                        <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', fontWeight: 600, marginTop: 4 }}>{label}</div>
                                    </div>
                                </div>
                            );
                        })()}
                    </div>
                </AnimatedCard>
            </div>

            <AnimatedCard delay={0.46}>
                <div className="card-header"><span className="card-title">Sprint-to-Sprint Quality Trend</span></div>
                <div className="card-body">
                    <div className="chart-container">
                        <ResponsiveContainer width="100%" height="100%">
                            <LineChart data={sprintTrend}>
                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                <YAxis domain={[60, 100]} tick={{ fontSize: 12 }} />
                                <Tooltip formatter={(v) => `${v}%`} />
                                <Legend />
                                <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 5, fill: '#3b82f6' }} name="Quality Score %" />
                            </LineChart>
                        </ResponsiveContainer>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
