import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { ThumbsUp, ThumbsDown, Lightbulb, Brain, MessageSquare, RefreshCw, Loader2, Sparkles, Target, TrendingUp, CheckCircle, AlertTriangle } from 'lucide-react';
import { pmAPI } from '../../services/api';

const priorityColors = { High: '#ef4444', Medium: '#f59e0b', Low: '#10b981' };

export default function PMRetrospective() {
    const [retroSummary, setRetroSummary] = useState(null);
    const [wentWell, setWentWell] = useState([]);
    const [didntGoWell, setDidntGoWell] = useState([]);
    const [improvements, setImprovements] = useState([]);
    const [aiSummary, setAiSummary] = useState('');
    const [chainOfThought, setChainOfThought] = useState('');
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [showCoT, setShowCoT] = useState(false);
    const [source, setSource] = useState('');

    // Load cached data on mount
    useEffect(() => {
        const fetchData = async () => {
            try {
                const [summary, impr] = await Promise.all([
                    pmAPI.retroSummary(),
                    pmAPI.improvements()
                ]);
                if (summary) setRetroSummary(Array.isArray(summary) ? summary[0] : summary);
                if (Array.isArray(impr)) {
                    const well = impr.filter(i => i.category === 'went_well').map(i => typeof i === 'string' ? i : (i.text || i.action || ''));
                    const didnt = impr.filter(i => i.category === 'didnt_go_well').map(i => typeof i === 'string' ? i : (i.text || i.action || ''));
                    const actions = impr.filter(i => i.category === 'improvement');
                    if (well.length) setWentWell(well);
                    if (didnt.length) setDidntGoWell(didnt);
                    if (actions.length) setImprovements(actions);
                }
            } catch (err) {
                console.error('Failed to fetch PM Retrospective data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    // Generate retrospective via AI agent
    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const res = await pmAPI.generateRetrospective();
            if (res?.ok) {
                setWentWell(res.went_well || []);
                setDidntGoWell(res.didnt_go_well || []);
                setImprovements(res.improvements || []);
                setAiSummary(res.ai_summary || '');
                setChainOfThought(res.chain_of_thought || '');
                setSource(res.source || '');
            }
        } catch (err) {
            console.error('Retrospective generation failed:', err);
        } finally {
            setGenerating(false);
        }
    };

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading retrospective...</div>;

    const retroData = retroSummary || { sprintName: 'N/A', completionPct: 0, alignmentAvg: 0, behaviourAvg: 0, bottleneck: 'None' };

    return (
        <div>
            {/* Stats Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Target size={24} />} value={`${retroData.completionPct}%`} label="Sprint Completion" trend={retroData.completionPct >= 80 ? 'On track' : 'Spillover'} trendDir={retroData.completionPct >= 80 ? 'up' : 'down'} color="blue" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${retroData.alignmentAvg}%`} label="Alignment Avg" trend="+3.2%" trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<CheckCircle size={24} />} value={`${retroData.behaviourAvg}/10`} label="Behaviour Avg" color="purple" delay={0.16} />
                <StatsCard icon={<AlertTriangle size={24} />} value={retroData.bottleneck} label="Bottleneck Area" color="red" delay={0.24} />
            </div>

            {/* Generate Button Bar */}
            <AnimatedCard delay={0}>
                <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Sparkles size={22} style={{ color: '#8b5cf6' }} />
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '1rem' }}>Sprint Retrospective Agent</div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                                {source === 'ai' ? '🤖 AI-powered analysis' : source === 'rule_based' ? '📊 Rule-based analysis' : 'Click generate to analyse sprint data'}
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
                        <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}
                            style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 20px', fontWeight: 700, fontSize: '0.88rem' }}>
                            {generating ? <><Loader2 size={16} className="spin" /> Analysing...</> : <><RefreshCw size={16} /> Generate Retrospective</>}
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

            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                {/* What Went Well */}
                <AnimatedCard delay={0.1}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <ThumbsUp size={18} style={{ color: '#10b981' }} /> What Went Well
                        </span>
                        <span className="badge badge-success">{wentWell.length} items</span>
                    </div>
                    <div className="card-body">
                        {wentWell.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                No data yet. Click "Generate Retrospective" to analyse.
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: 10 }}>
                                {wentWell.map((item, i) => (
                                    <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#f0fdf4', borderRadius: 'var(--radius-sm)', border: '1px solid #bbf7d0' }}>
                                        <span style={{ color: '#10b981', fontWeight: 700, flexShrink: 0 }}>✓</span>
                                        <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{typeof item === 'string' ? item : (item?.text || item?.action || '')}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </AnimatedCard>

                {/* What Didn't Go Well */}
                <AnimatedCard delay={0.18}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <ThumbsDown size={18} style={{ color: '#ef4444' }} /> What Didn't Go Well
                        </span>
                        <span className="badge badge-danger">{didntGoWell.length} items</span>
                    </div>
                    <div className="card-body">
                        {didntGoWell.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                No data yet. Click "Generate Retrospective" to analyse.
                            </div>
                        ) : (
                            <div style={{ display: 'grid', gap: 10 }}>
                                {didntGoWell.map((item, i) => (
                                    <div key={i} style={{ display: 'flex', gap: 12, padding: '12px 16px', background: '#fef2f2', borderRadius: 'var(--radius-sm)', border: '1px solid #fecaca' }}>
                                        <span style={{ color: '#ef4444', fontWeight: 700, flexShrink: 0 }}>✗</span>
                                        <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>{typeof item === 'string' ? item : (item?.text || item?.action || '')}</span>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </AnimatedCard>
            </div>

            {/* Improvement Actions */}
            <AnimatedCard delay={0.26}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Lightbulb size={18} style={{ color: '#f59e0b' }} /> Improvement Actions
                    </span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Action Item</th>
                                    <th>Assignee</th>
                                    <th>Deadline</th>
                                    <th>Priority</th>
                                </tr>
                            </thead>
                            <tbody>
                                {improvements.map((item, i) => (
                                    <tr key={i}>
                                        <td style={{ fontWeight: 500 }}>{item.action}</td>
                                        <td>{item.assignee || item.owner}</td>
                                        <td>{item.deadline || item.due}</td>
                                        <td><span className="badge" style={{ background: priorityColors[item.priority] || '#6b7280', color: '#fff' }}>{item.priority || 'Medium'}</span></td>
                                    </tr>
                                ))}
                                {improvements.length === 0 && (
                                    <tr>
                                        <td colSpan={4} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>
                                            No improvement actions yet. Generate a retrospective to see results.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* AI Retrospective Summary */}
            <AnimatedCard delay={0.34} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Brain size={18} style={{ color: '#8b5cf6' }} /> AI-Generated Retrospective Summary
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
                            AI summary will appear here after generating a retrospective.
                        </div>
                    )}
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
