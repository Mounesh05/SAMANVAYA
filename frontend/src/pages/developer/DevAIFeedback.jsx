import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Cpu, TrendingUp, AlertTriangle, Shield, Lightbulb, BarChart3, GitCommit, FileWarning, Brain, RefreshCw, Loader2, Sparkles, CheckCircle, XCircle, ThumbsUp, ThumbsDown } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { devAPI } from '../../services/api';

const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';
const getDriftColor = (v) => v <= 10 ? '#10b981' : v <= 20 ? '#f59e0b' : '#ef4444';
const typeConfig = {
    success: { bg: 'var(--success-bg)', border: 'var(--success)', color: '#065f46' },
    warning: { bg: 'var(--warning-bg)', border: 'var(--warning)', color: '#92400e' },
    danger: { bg: 'var(--danger-bg)', border: 'var(--danger)', color: '#991b1b' },
    info: { bg: 'var(--info-bg)', border: 'var(--info)', color: '#1e40af' },
};
const priorityColors = { High: '#ef4444', Medium: '#f59e0b', Low: '#10b981' };

export default function DevAIFeedback() {
    const [alignmentData, setAlignmentData] = useState([]);
    const [suggestions, setSuggestions] = useState([]);

    // Code Review Agent state
    const [goodPractices, setGoodPractices] = useState([]);
    const [issuesFound, setIssuesFound] = useState([]);
    const [actionItems, setActionItems] = useState([]);
    const [aiSummary, setAiSummary] = useState('');
    const [chainOfThought, setChainOfThought] = useState('');
    const [loading, setLoading] = useState(false);
    const [showCoT, setShowCoT] = useState(false);
    const [source, setSource] = useState('');
    const [scorecards, setScorecards] = useState([]);
    const [avgScore, setAvgScore] = useState(0);

    useEffect(() => {
        devAPI.aiFeedback().then(data => {
            if (!data) return;
            if (data.alignment_data?.length) setAlignmentData(data.alignment_data);
            if (data.suggestions?.length) setSuggestions(data.suggestions);
            // Load cached code review
            if (data.code_review) {
                const cr = data.code_review;
                if (cr.good_practices?.length) setGoodPractices(cr.good_practices);
                if (cr.issues_found?.length) setIssuesFound(cr.issues_found);
                if (cr.action_items?.length) setActionItems(cr.action_items);
                if (cr.ai_summary) setAiSummary(cr.ai_summary);
                if (cr.chain_of_thought) setChainOfThought(cr.chain_of_thought);
                if (cr.source) setSource(cr.source);
                if (cr.scorecards?.length) setScorecards(cr.scorecards);
                if (cr.avg_score != null) setAvgScore(cr.avg_score);
            }
        }).catch(() => { });
    }, []);

    // Generate code review
    const handleGenerate = async () => {
        setLoading(true);
        try {
            const res = await devAPI.generateCodeReview();
            if (res?.ok) {
                setGoodPractices(res.good_practices || []);
                setIssuesFound(res.issues_found || []);
                setActionItems(res.action_items || []);
                setAiSummary(res.ai_summary || '');
                setChainOfThought(res.chain_of_thought || '');
                setSource(res.source || '');
                setScorecards(res.scorecards || []);
                setAvgScore(res.avg_score || 0);
            }
        } catch (err) {
            console.error('Code review generation failed:', err);
        } finally {
            setLoading(false);
        }
    };

    const overallAlignment = alignmentData.filter(d => !d.invert).length ?
        Math.round(alignmentData.filter(d => !d.invert).reduce((a, d) => a + d.value, 0) / alignmentData.filter(d => !d.invert).length) : 0;

    const scoreColor = (v) => v >= 75 ? '#10b981' : v >= 55 ? '#f59e0b' : '#ef4444';
    const factorLabels = {
        branch_created: 'Branch Created',
        commits_pushed: 'Commits Pushed',
        pr_created: 'PR Created',
        pr_reviewed: 'PR Reviewed',
        pr_merged: 'PR Merged',
        file_alignment: 'File Alignment',
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Cpu size={24} />} value={`${overallAlignment}%`} label="Overall Alignment" color="green" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${avgScore}/100`} label="Avg PR Score" color="blue" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={`${(alignmentData.find(d => d.invert) || { value: 0 }).value}%`} label="Scope Drift" color="red" delay={0.16} />
                <StatsCard icon={<BarChart3 size={24} />} value={scorecards.length} label="PRs Scored" color="orange" delay={0.24} />
            </div>

            {/* ── Code Reviewer AI Agent ── */}
            <AnimatedCard delay={0}>
                <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Sparkles size={22} style={{ color: '#8b5cf6' }} />
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '1rem' }}>Code Reviewer AI Agent</div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                                {source === 'ai' ? '🤖 AI-powered analysis' : source === 'rule_based' ? '📊 Rule-based analysis of PRs & branches' : 'Click generate to analyse code quality across PRs & branches'}
                            </div>
                        </div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {chainOfThought && (
                            <button className="btn btn-sm btn-secondary" onClick={() => setShowCoT(!showCoT)}
                                style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.78rem' }}>
                                <Brain size={14} /> {showCoT ? 'Hide CoT' : 'Show Chain-of-Thought'}
                            </button>
                        )}
                        <button className="btn btn-primary" onClick={handleGenerate} disabled={loading}
                            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', fontWeight: 700, fontSize: '0.88rem' }}>
                            {loading ? <><Loader2 size={16} className="spin" /> Analysing...</> : <><RefreshCw size={16} /> Generate Code Review</>}
                        </button>
                    </div>
                </div>

                {/* Chain of Thought Panel */}
                {showCoT && chainOfThought && (
                    <div style={{
                        padding: '16px 24px', borderTop: '1px solid var(--border-color)',
                        background: 'linear-gradient(135deg, #f0f9ff, #e0f2fe)', fontSize: '0.82rem',
                        lineHeight: 1.7, color: '#0c4a6e', whiteSpace: 'pre-wrap', fontFamily: 'monospace',
                    }}>
                        <div style={{ fontWeight: 700, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6, color: '#0369a1' }}>
                            <Brain size={14} /> Chain-of-Thought Reasoning
                        </div>
                        {chainOfThought}
                    </div>
                )}
            </AnimatedCard>

            {/* Good Practices & Issues */}
            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                {/* Good Practices */}
                <AnimatedCard delay={0.1}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <ThumbsUp size={18} style={{ color: '#10b981' }} /> Good Practices
                        </span>
                        <span className="badge badge-success">{goodPractices.length} items</span>
                    </div>
                    <div className="card-body">
                        {goodPractices.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                No data yet. Click "Generate Code Review" to analyse.
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: 10 }}>
                                {goodPractices.map((item, i) => (
                                    <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#f0fdf4', borderRadius: 'var(--radius-sm)', border: '1px solid #bbf7d0' }}>
                                        <CheckCircle size={16} style={{ color: '#10b981', flexShrink: 0, marginTop: 2 }} />
                                        <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{typeof item === 'string' ? item : item?.text || ''}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </AnimatedCard>

                {/* Issues Found */}
                <AnimatedCard delay={0.18}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <ThumbsDown size={18} style={{ color: '#ef4444' }} /> Issues Found
                        </span>
                        <span className="badge badge-danger">{issuesFound.length} items</span>
                    </div>
                    <div className="card-body">
                        {issuesFound.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                No data yet. Click "Generate Code Review" to analyse.
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: 10 }}>
                                {issuesFound.map((item, i) => (
                                    <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#fef2f2', borderRadius: 'var(--radius-sm)', border: '1px solid #fecaca' }}>
                                        <XCircle size={16} style={{ color: '#ef4444', flexShrink: 0, marginTop: 2 }} />
                                        <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{typeof item === 'string' ? item : item?.text || ''}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </AnimatedCard>
            </div>

            {/* Action Items */}
            <AnimatedCard delay={0.26}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Lightbulb size={18} style={{ color: '#f59e0b' }} /> Action Items
                    </span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Action</th>
                                    <th>Assignee</th>
                                    <th>Deadline</th>
                                    <th>Priority</th>
                                </tr>
                            </thead>
                            <tbody>
                                {actionItems.map((item, i) => (
                                    <tr key={i}>
                                        <td style={{ fontWeight: 500 }}>{item.action}</td>
                                        <td>{item.assignee || item.owner}</td>
                                        <td>{item.deadline || item.due}</td>
                                        <td><span className="badge" style={{ background: priorityColors[item.priority] || '#6b7280', color: '#fff' }}>{item.priority || 'Medium'}</span></td>
                                    </tr>
                                ))}
                                {actionItems.length === 0 && (
                                    <tr>
                                        <td colSpan={4} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>
                                            No action items yet. Generate a code review to see results.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* AI Code Review Summary */}
            <AnimatedCard delay={0.34} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Brain size={18} style={{ color: '#8b5cf6' }} /> AI Code Review Summary
                    </span>
                    <span className="badge" style={{ background: '#8b5cf620', color: '#8b5cf6' }}>AI Generated</span>
                </div>
                <div className="card-body">
                    {aiSummary ? (
                        <div style={{ padding: '20px 24px', background: 'linear-gradient(135deg, #f5f3ff, #ede9fe)', borderRadius: 'var(--radius-md)', border: '1px solid #c4b5fd', lineHeight: 1.8, fontSize: '0.9rem', color: '#3b0764' }}>
                            {aiSummary}
                        </div>
                    ) : (
                        <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                            AI summary will appear here after generating a code review.
                        </div>
                    )}
                </div>
            </AnimatedCard>

            {/* Per-PR Scorecards */}
            {scorecards.length > 0 && (
                <AnimatedCard delay={0.4} style={{ marginTop: 20 }}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <BarChart3 size={18} style={{ color: '#3b82f6' }} /> Per-PR Scorecards
                        </span>
                        <span className="badge" style={{ background: '#3b82f620', color: '#3b82f6', fontWeight: 700 }}>
                            WEIGHTS: 10 + 20 + 20 + 15 + 20 + 15 = 100
                        </span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>PR</th>
                                        <th>Branch (10)</th>
                                        <th>Commits (20)</th>
                                        <th>PR Created (20)</th>
                                        <th>Reviewed (15)</th>
                                        <th>Merged (20)</th>
                                        <th>Alignment (15)</th>
                                        <th>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {scorecards.map((card, i) => (
                                        <tr key={i}>
                                            <td>
                                                <div style={{ fontWeight: 700, fontSize: '0.82rem' }}>{card.pr_id}</div>
                                                <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{card.title}</div>
                                            </td>
                                            {Object.keys(factorLabels).map(key => {
                                                const f = card.breakdown?.[key];
                                                if (!f) return <td key={key}>—</td>;
                                                const pct = f.max > 0 ? (f.earned / f.max) * 100 : 0;
                                                return (
                                                    <td key={key}>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                            <div style={{ width: 40, height: 5, borderRadius: 3, background: '#e5e7eb' }}>
                                                                <div style={{
                                                                    height: '100%', borderRadius: 3,
                                                                    width: `${pct}%`,
                                                                    background: pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444',
                                                                }} />
                                                            </div>
                                                            <span style={{ fontWeight: 600, fontSize: '0.75rem', color: pct >= 80 ? '#10b981' : pct >= 50 ? '#f59e0b' : '#ef4444' }}>
                                                                {f.earned}/{f.max}
                                                            </span>
                                                        </div>
                                                    </td>
                                                );
                                            })}
                                            <td>
                                                <span style={{
                                                    fontWeight: 800, fontSize: '0.95rem',
                                                    color: scoreColor(card.total_score),
                                                }}>
                                                    {card.total_score}
                                                </span>
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>/100</span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}

            {/* Alignment Breakdown & Commit Frequency */}
            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                <AnimatedCard delay={0.42}>
                    <div className="card-header">
                        <span className="card-title">Alignment Breakdown</span>
                        <span className="badge badge-info">AI</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={alignmentData} layout="vertical" margin={{ left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 12 }} />
                                    <YAxis type="category" dataKey="metric" tick={{ fontSize: 11 }} width={120} />
                                    <Tooltip formatter={(v, n, p) => [`${v}%`, p.payload.metric]} />
                                    <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                                        {alignmentData.map((d, i) => (
                                            <Cell key={i} fill={d.invert ? getDriftColor(d.value) : getColor(d.value)} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                        {/* Detail bars below chart */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 16 }}>
                            {alignmentData.map((d, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                    <span style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', width: 130, flexShrink: 0 }}>{d.metric}</span>
                                    <div style={{ flex: 1, height: 8, borderRadius: 4, background: '#e5e7eb' }}>
                                        <div style={{
                                            height: '100%', borderRadius: 4, width: `${d.value}%`,
                                            background: d.invert ? getDriftColor(d.value) : getColor(d.value),
                                            transition: 'width 0.8s ease'
                                        }} />
                                    </div>
                                    <span style={{
                                        fontWeight: 700, fontSize: '0.82rem', width: 40, textAlign: 'right',
                                        color: d.invert ? getDriftColor(d.value) : getColor(d.value)
                                    }}>{d.value}%</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </AnimatedCard>

                {/* Commit Frequency */}
                <AnimatedCard delay={0.5}>
                    <div className="card-header">
                        <span className="card-title">Commit Frequency</span>
                        <span className="badge badge-neutral">This Week</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={commitFrequency}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Bar dataKey="commits" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Commits">
                                        {commitFrequency.map((d, i) => (
                                            <Cell key={i} fill={d.commits >= 6 ? '#10b981' : d.commits >= 3 ? '#3b82f6' : '#f59e0b'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* Code Quality Insights */}
            <AnimatedCard delay={0.58}>
                <div className="card-header">
                    <span className="card-title">Code Quality Insights</span>
                    <span className="badge badge-info"><Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />AI Powered</span>
                </div>
                <div className="card-body" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                    {qualityInsights.map((qi, i) => {
                        const cfg = typeConfig[qi.type];
                        return (
                            <div key={i} style={{
                                padding: '14px 18px', borderRadius: 'var(--radius-sm)',
                                background: cfg.bg, borderLeft: `3px solid ${cfg.border}`,
                            }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                                    <span style={{ color: cfg.border }}>{qi.icon}</span>
                                    <span style={{ fontWeight: 700, fontSize: '0.85rem', color: cfg.color }}>{qi.title}</span>
                                </div>
                                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>{qi.desc}</div>
                            </div>
                        );
                    })}
                </div>
            </AnimatedCard>

            {/* AI Suggestions */}
            <AnimatedCard delay={0.66} style={{ marginTop: 16 }}>
                <div className="card-header">
                    <span className="card-title">AI Suggestions</span>
                    <span className="badge badge-warning">{suggestions.length} suggestions</span>
                </div>
                <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    {suggestions.map((s, i) => (
                        <div key={i} style={{
                            display: 'flex', alignItems: 'flex-start', gap: 12,
                            padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                            background: '#f5f3ff', border: '1px solid #e9d5ff',
                        }}>
                            <Lightbulb size={16} style={{ color: '#7c3aed', flexShrink: 0, marginTop: 2 }} />
                            <div style={{ flex: 1 }}>
                                <div style={{ fontSize: '0.85rem', color: '#4c1d95', lineHeight: 1.5 }}>{s.text}</div>
                            </div>
                            <span style={{
                                padding: '2px 8px', borderRadius: 10, fontSize: '0.68rem', fontWeight: 700,
                                background: priorityColors[s.priority] + '20', color: priorityColors[s.priority],
                                flexShrink: 0
                            }}>{s.priority}</span>
                        </div>
                    ))}
                </div>
            </AnimatedCard>

            {/* Loading spinner animation */}
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
