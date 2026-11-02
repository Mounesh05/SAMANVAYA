import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Cpu, TrendingUp, AlertTriangle, BarChart3, Search, Sparkles, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    PieChart, Pie, Cell, Area, AreaChart
} from 'recharts';
import { pmAPI } from '../../services/api';

export default function PMAlignmentReports() {
    const [companyAlignment, setCompanyAlignment] = useState(0);
    const [projectAlignment, setProjectAlignment] = useState([]);
    const [memberAlignment, setMemberAlignment] = useState([]);
    const [alignmentTrend, setAlignmentTrend] = useState([]);
    const [offenseBreakdown, setOffenseBreakdown] = useState([]);
    const [scopeDrift, setScopeDrift] = useState([]);
    const [loading, setLoading] = useState(true);
    const [reviewStats, setReviewStats] = useState({ projectAlignment: 0, avgScopeDrift: 0 });

    // Review / CoT state
    const [reviewLoading, setReviewLoading] = useState(false);
    const [reviewData, setReviewData] = useState(null);
    const [showCoT, setShowCoT] = useState(false);
    const [cotExpanded, setCotExpanded] = useState(false);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [reports, trend] = await Promise.all([
                    pmAPI.alignmentReports(),
                    pmAPI.alignmentTrend()
                ]);

                if (reports) {
                    if (reports.company_alignment) setCompanyAlignment(reports.company_alignment);
                    if (reports.project_alignment?.length) setProjectAlignment(reports.project_alignment);
                    if (reports.member_alignment?.length) setMemberAlignment(reports.member_alignment);
                    if (reports.offense_breakdown?.length) setOffenseBreakdown(reports.offense_breakdown);
                    if (reports.scope_drift?.length) setScopeDrift(reports.scope_drift);
                    setReviewStats({
                        projectAlignment: reports.project_alignment_avg || 0,
                        avgScopeDrift: reports.avg_scope_drift || 0
                    });
                }

                if (Array.isArray(trend) && trend.length > 0) {
                    setAlignmentTrend(trend.map(d => ({
                        sprint: d.sprint || d.id,
                        alignment: d.alignment || d.avg || 0,
                    })));
                }
            } catch (err) {
                console.error('Failed to fetch PM alignment reports:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

    // Computed chart data
    const highDev = memberAlignment.filter(m => m.deviation > 15).length;
    const medDev = memberAlignment.filter(m => m.deviation > 8 && m.deviation <= 15).length;
    const lowDev = memberAlignment.filter(m => m.deviation <= 8).length;
    const riskDistribution = [
        { name: 'High Risk', value: highDev || 0, color: '#ef4444' },
        { name: 'Medium Risk', value: medDev || 0, color: '#f59e0b' },
        { name: 'Low Risk', value: lowDev || 0, color: '#10b981' },
    ];

    // Run AI Alignment Review
    const handleReview = async () => {
        setReviewLoading(true);
        setReviewData(null);
        setShowCoT(false);
        try {
            const data = await pmAPI.alignmentReview();
            setReviewData(data);
            setShowCoT(true);
        } catch (err) {
            setReviewData({ error: 'Failed to run alignment review. Please try again.' });
            setShowCoT(true);
        } finally {
            setReviewLoading(false);
        }
    };

    // Parse CoT steps into array for display
    const parseCotSteps = (cot) => {
        if (!cot) return [];
        return cot.split('\n').filter(s => s.trim());
    };

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading alignment reports...</div>;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Cpu size={24} />} value={`${companyAlignment}%`} label="Company Alignment" trend="+1.8%" trendDir="up" color="purple" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${reviewStats.projectAlignment}%`} label="Project Alignment" trend="+2.4%" trendDir="up" color="blue" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={memberAlignment.filter(m => m.deviation > 15).length} label="High Deviation" color="red" delay={0.16} />
                <StatsCard icon={<BarChart3 size={24} />} value={`${reviewStats.avgScopeDrift}%`} label="Avg Scope Drift" color="orange" delay={0.24} />
            </div>

            {/* AI Review Button + CoT Panel */}
            <AnimatedCard delay={0.28}>
                <div className="card-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Sparkles size={18} style={{ color: '#8b5cf6' }} /> AI Alignment Review
                    </span>
                    <button
                        onClick={handleReview}
                        disabled={reviewLoading}
                        style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            padding: '10px 24px',
                            background: reviewLoading
                                ? 'linear-gradient(135deg, #6b7280, #9ca3af)'
                                : 'linear-gradient(135deg, #8b5cf6, #a78bfa)',
                            color: '#fff',
                            border: 'none', borderRadius: '8px',
                            fontSize: '0.85rem', fontWeight: 700,
                            cursor: reviewLoading ? 'not-allowed' : 'pointer',
                            transition: 'all 0.3s ease',
                            boxShadow: reviewLoading ? 'none' : '0 4px 14px rgba(139, 92, 246, 0.4)',
                            letterSpacing: '0.5px',
                        }}
                    >
                        {reviewLoading ? (
                            <><Loader2 size={16} className="spin" /> Analyzing...</>
                        ) : (
                            <><Search size={16} /> Review</>
                        )}
                    </button>
                </div>
                <div className="card-body">
                    {!reviewData && !reviewLoading && (
                        <div style={{
                            textAlign: 'center', padding: '24px',
                            color: 'var(--text-tertiary)', fontSize: '0.88rem',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
                        }}>
                            <Sparkles size={32} style={{ color: '#d1d5db' }} />
                            Click <strong>Review</strong> to run an AI-powered alignment analysis with Chain-of-Thought reasoning.
                        </div>
                    )}

                    {reviewLoading && (
                        <div style={{
                            textAlign: 'center', padding: '32px',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12,
                        }}>
                            <Loader2 size={40} className="spin" style={{ color: '#8b5cf6' }} />
                            <span style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
                                Running AI Chain-of-Thought analysis...
                            </span>
                        </div>
                    )}

                    {showCoT && reviewData && !reviewData.error && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                            {/* Summary Row */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
                                <div style={{
                                    padding: '16px', borderRadius: '10px', textAlign: 'center',
                                    background: 'linear-gradient(135deg, #f0fdf4, #dcfce7)',
                                    border: '1px solid #bbf7d0',
                                }}>
                                    <div style={{ fontSize: '0.72rem', color: '#166534', textTransform: 'uppercase', letterSpacing: '1px' }}>AVG ALIGNMENT</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#166534' }}>{reviewData.avg_alignment}%</div>
                                </div>
                                <div style={{
                                    padding: '16px', borderRadius: '10px', textAlign: 'center',
                                    background: reviewData.risk_level === 'HIGH' ? 'linear-gradient(135deg, #fef2f2, #fee2e2)' : reviewData.risk_level === 'MEDIUM' ? 'linear-gradient(135deg, #fffbeb, #fef3c7)' : 'linear-gradient(135deg, #f0fdf4, #dcfce7)',
                                    border: `1px solid ${reviewData.risk_level === 'HIGH' ? '#fecaca' : reviewData.risk_level === 'MEDIUM' ? '#fde68a' : '#bbf7d0'}`,
                                }}>
                                    <div style={{ fontSize: '0.72rem', color: reviewData.risk_level === 'HIGH' ? '#991b1b' : reviewData.risk_level === 'MEDIUM' ? '#92400e' : '#166534', textTransform: 'uppercase', letterSpacing: '1px' }}>RISK LEVEL</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: reviewData.risk_level === 'HIGH' ? '#ef4444' : reviewData.risk_level === 'MEDIUM' ? '#f59e0b' : '#10b981' }}>{reviewData.risk_level}</div>
                                </div>
                                <div style={{
                                    padding: '16px', borderRadius: '10px', textAlign: 'center',
                                    background: 'linear-gradient(135deg, #eff6ff, #dbeafe)',
                                    border: '1px solid #bfdbfe',
                                }}>
                                    <div style={{ fontSize: '0.72rem', color: '#1e40af', textTransform: 'uppercase', letterSpacing: '1px' }}>MEMBERS</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#1e40af' }}>{reviewData.total_members}</div>
                                </div>
                                <div style={{
                                    padding: '16px', borderRadius: '10px', textAlign: 'center',
                                    background: reviewData.high_risk_count > 0 ? 'linear-gradient(135deg, #fef2f2, #fee2e2)' : 'linear-gradient(135deg, #f0fdf4, #dcfce7)',
                                    border: `1px solid ${reviewData.high_risk_count > 0 ? '#fecaca' : '#bbf7d0'}`,
                                }}>
                                    <div style={{ fontSize: '0.72rem', color: reviewData.high_risk_count > 0 ? '#991b1b' : '#166534', textTransform: 'uppercase', letterSpacing: '1px' }}>AT RISK</div>
                                    <div style={{ fontSize: '1.5rem', fontWeight: 800, color: reviewData.high_risk_count > 0 ? '#ef4444' : '#10b981' }}>{reviewData.high_risk_count}</div>
                                </div>
                            </div>

                            {/* Highlights */}
                            {reviewData.highlights?.length > 0 && (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {reviewData.highlights.map((h, i) => (
                                        <div key={i} style={{
                                            padding: '10px 14px', borderRadius: '8px', fontSize: '0.84rem', lineHeight: 1.5,
                                            background: h.type === 'success' ? '#f0fdf4' : h.type === 'warning' ? '#fffbeb' : h.type === 'danger' ? '#fef2f2' : '#eff6ff',
                                            border: `1px solid ${h.type === 'success' ? '#bbf7d0' : h.type === 'warning' ? '#fde68a' : h.type === 'danger' ? '#fecaca' : '#bfdbfe'}`,
                                            color: h.type === 'success' ? '#166534' : h.type === 'warning' ? '#92400e' : h.type === 'danger' ? '#991b1b' : '#1e40af',
                                        }}>
                                            {h.type === 'success' ? '✅' : h.type === 'warning' ? '⚠️' : h.type === 'danger' ? '🔴' : 'ℹ️'} {h.text}
                                        </div>
                                    ))}
                                </div>
                            )}

                            {/* Recommendations */}
                            {reviewData.recommendations?.length > 0 && (
                                <div style={{
                                    padding: '14px 16px', borderRadius: '10px',
                                    background: 'linear-gradient(135deg, #faf5ff, #f3e8ff)',
                                    border: '1px solid #e9d5ff',
                                }}>
                                    <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#6b21a8', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        💡 Recommendations
                                    </div>
                                    <ul style={{ margin: 0, paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                                        {reviewData.recommendations.map((r, i) => (
                                            <li key={i} style={{ fontSize: '0.84rem', color: '#581c87', lineHeight: 1.5 }}>{r}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Chain-of-Thought Expandable */}
                            {reviewData.chain_of_thought && (
                                <div style={{
                                    borderRadius: '10px', overflow: 'hidden',
                                    border: '1px solid #e5e7eb',
                                    background: '#fafafa',
                                }}>
                                    <button
                                        onClick={() => setCotExpanded(!cotExpanded)}
                                        style={{
                                            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                            padding: '12px 16px', background: 'none', border: 'none',
                                            cursor: 'pointer', fontSize: '0.82rem', fontWeight: 700,
                                            color: '#6b7280',
                                        }}
                                    >
                                        <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <Cpu size={14} style={{ color: '#8b5cf6' }} />
                                            Chain-of-Thought Reasoning ({reviewData.source === 'rule_based' ? 'Rule-Based' : 'AI'})
                                        </span>
                                        {cotExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                                    </button>
                                    {cotExpanded && (
                                        <div style={{
                                            padding: '0 16px 16px', maxHeight: 400, overflowY: 'auto',
                                        }}>
                                            {parseCotSteps(reviewData.chain_of_thought).map((step, i) => {
                                                const isStep = step.startsWith('Step');
                                                const stepMatch = step.match(/^Step (\d+) — ([A-Z\s]+):/);
                                                return (
                                                    <div key={i} style={{
                                                        padding: '10px 14px', marginBottom: 8,
                                                        borderRadius: '8px',
                                                        background: isStep ? '#fff' : '#f9fafb',
                                                        border: isStep ? '1px solid #e5e7eb' : 'none',
                                                        fontSize: '0.82rem', lineHeight: 1.6,
                                                        color: '#374151',
                                                    }}>
                                                        {stepMatch ? (
                                                            <>
                                                                <span style={{
                                                                    display: 'inline-flex', alignItems: 'center', gap: 6,
                                                                    fontWeight: 800, color: '#8b5cf6', fontSize: '0.78rem',
                                                                    marginBottom: 4,
                                                                }}>
                                                                    <span style={{
                                                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                                                        width: 22, height: 22, borderRadius: '50%',
                                                                        background: '#8b5cf6', color: '#fff',
                                                                        fontSize: '0.7rem', fontWeight: 800,
                                                                    }}>{stepMatch[1]}</span>
                                                                    {stepMatch[2]}
                                                                </span>
                                                                <div style={{ marginTop: 4, color: '#4b5563' }}>
                                                                    {step.replace(stepMatch[0], '').trim()}
                                                                </div>
                                                            </>
                                                        ) : (
                                                            step
                                                        )}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Source Badge */}
                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, alignItems: 'center' }}>
                                <span style={{
                                    fontSize: '0.72rem', padding: '4px 10px',
                                    borderRadius: '20px', fontWeight: 600,
                                    background: reviewData.source === 'ai' ? '#ede9fe' : '#f0fdf4',
                                    color: reviewData.source === 'ai' ? '#6b21a8' : '#166534',
                                }}>
                                    {reviewData.source === 'ai' ? '🤖 AI Engine' : '⚙️ Rule-Based'}
                                </span>
                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                                    {reviewData.reviewed_at ? new Date(reviewData.reviewed_at).toLocaleString() : ''}
                                </span>
                            </div>
                        </div>
                    )}

                    {showCoT && reviewData?.error && (
                        <div style={{
                            padding: '16px', borderRadius: '8px',
                            background: '#fef2f2', border: '1px solid #fecaca',
                            color: '#991b1b', fontSize: '0.88rem',
                        }}>
                            ❌ {reviewData.error}
                        </div>
                    )}
                </div>
            </AnimatedCard>

            {/* Member Alignment Breakdown */}
            <AnimatedCard delay={0.34} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title">🔹 Member-wise Alignment Breakdown</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead><tr><th>Member</th><th>Alignment Score</th><th>Deviation %</th><th>Visual</th></tr></thead>
                            <tbody>
                                {memberAlignment.map(m => (
                                    <tr key={m.name}>
                                        <td style={{ fontWeight: 600 }}>{m.name}</td>
                                        <td><span style={{ fontWeight: 700, color: getColor(m.alignment) }}>{m.alignment}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: m.deviation > 15 ? '#ef4444' : m.deviation > 8 ? '#f59e0b' : '#10b981' }}>{m.deviation}%</span></td>
                                        <td style={{ width: 180 }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ flex: 1, height: 8, background: '#e5e7eb', borderRadius: 4, overflow: 'hidden' }}>
                                                    <div style={{ width: `${m.alignment}%`, height: '100%', background: getColor(m.alignment), borderRadius: 4 }} />
                                                </div>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                {/* Alignment Trend per Sprint (from DB) */}
                <AnimatedCard delay={0.42}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <TrendingUp size={16} style={{ color: '#8b5cf6' }} />
                            Alignment Trend per Sprint
                        </span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            {alignmentTrend.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={alignmentTrend}>
                                        <defs>
                                            <linearGradient id="alignGradient" x1="0" y1="0" x2="0" y2="1">
                                                <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                                                <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                                            </linearGradient>
                                        </defs>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[50, 100]} tick={{ fontSize: 11 }} />
                                        <Tooltip
                                            formatter={(v) => [`${v}%`, 'Alignment']}
                                            contentStyle={{ borderRadius: 8, border: '1px solid #e5e7eb', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}
                                        />
                                        <Area type="monotone" dataKey="alignment" stroke="#8b5cf6" strokeWidth={2.5} fill="url(#alignGradient)" dot={{ fill: '#8b5cf6', r: 5, strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 7, stroke: '#8b5cf6', strokeWidth: 2 }} />
                                    </AreaChart>
                                </ResponsiveContainer>
                            ) : (
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                    No trend data available
                                </div>
                            )}
                        </div>
                    </div>
                </AnimatedCard>

                {/* High-Risk Story Distribution */}
                <AnimatedCard delay={0.50}>
                    <div className="card-header"><span className="card-title">High-Risk Story Distribution</span></div>
                    <div className="card-body">
                        <div className="chart-container" style={{ display: 'flex', alignItems: 'center' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={riskDistribution} cx="50%" cy="50%" innerRadius={50} outerRadius={90} dataKey="value" paddingAngle={3} label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}>
                                        {riskDistribution.map((e, i) => <Cell key={i} fill={e.color} />)}
                                    </Pie>
                                    <Tooltip />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            <div className="grid-2">
                {/* Scope Drift Frequency */}
                <AnimatedCard delay={0.58}>
                    <div className="card-header"><span className="card-title">Scope Drift Frequency</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={scopeDrift}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Bar dataKey="drift" fill="#f59e0b" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* AI Summary Box */}
                <AnimatedCard delay={0.66}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Cpu size={16} style={{ color: '#8b5cf6' }} /> AI Alignment Summary
                        </span>
                    </div>
                    <div className="card-body">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            {(reviewData?.highlights || [
                                { text: 'Backend tasks show 18% higher deviation than frontend.', type: 'warning' },
                                { text: 'Sprint Alpha has the highest alignment consistency at 88%.', type: 'success' },
                                { text: 'Karan Joshi and Rahul Verma need alignment coaching — deviation > 15%.', type: 'danger' },
                                { text: 'Scope drift decreased by 3% compared to last quarter.', type: 'info' },
                            ]).map((item, i) => (
                                <div key={i} style={{
                                    padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                                    background: item.type === 'success' ? '#f0fdf4' : item.type === 'warning' ? '#fffbeb' : item.type === 'danger' ? '#fef2f2' : '#eff6ff',
                                    border: `1px solid ${item.type === 'success' ? '#bbf7d0' : item.type === 'warning' ? '#fde68a' : item.type === 'danger' ? '#fecaca' : '#bfdbfe'}`,
                                    fontSize: '0.85rem', lineHeight: 1.5,
                                    color: item.type === 'success' ? '#166534' : item.type === 'warning' ? '#92400e' : item.type === 'danger' ? '#991b1b' : '#1e40af'
                                }}>
                                    {item.type === 'success' ? '✅' : item.type === 'warning' ? '⚠️' : item.type === 'danger' ? '🔴' : 'ℹ️'} {item.text}
                                </div>
                            ))}
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* Project Alignment */}
            <AnimatedCard delay={0.74} style={{ marginTop: 20 }}>
                <div className="card-header"><span className="card-title">🔹 Project Alignment Average</span></div>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16 }}>
                        {projectAlignment.map(p => (
                            <div key={p.project} style={{ textAlign: 'center', padding: '20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>{p.project}</div>
                                <div style={{ fontWeight: 800, fontSize: '1.8rem', color: getColor(p.avg) }}>{p.avg}%</div>
                            </div>
                        ))}
                    </div>
                </div>
            </AnimatedCard>

            <style>{`
                .spin {
                    animation: spin 1s linear infinite;
                }
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </div>
    );
}
