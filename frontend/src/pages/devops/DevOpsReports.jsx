import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import {
    FileText, Download, BarChart2, Shield, Activity, AlertTriangle,
    Sparkles, Brain, RefreshCw, Loader2, CheckCircle2, XCircle, ListChecks, BarChart3
} from 'lucide-react';
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
    PieChart, Pie, Legend
} from 'recharts';
import { devopsAPI } from '../../services/api';

export default function DevOpsReports() {
    const [reports, setReports] = useState([]);
    const [incidentBySeverity, setIncidentBySeverity] = useState([]);
    const [pipelineSuccess, setPipelineSuccess] = useState([]);
    const [exporting, setExporting] = useState(null);

    // Ops Reviewer AI Agent state
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
        devopsAPI.reports().then(data => {
            if (!data) return;
            if (Array.isArray(data)) {
                setReports(data);
            } else {
                if (data.reports) setReports(data.reports);
                if (data.incident_by_severity) setIncidentBySeverity(data.incident_by_severity);
                if (data.pipeline_success) setPipelineSuccess(data.pipeline_success);
            }
        }).catch(() => { });
        // Load cached ops review
        devopsAPI.opsReview().then(data => {
            if (data?.ok) {
                if (data.good_practices?.length) setGoodPractices(data.good_practices);
                if (data.issues_found?.length) setIssuesFound(data.issues_found);
                if (data.action_items?.length) setActionItems(data.action_items);
                if (data.ai_summary) setAiSummary(data.ai_summary);
                if (data.chain_of_thought) setChainOfThought(data.chain_of_thought);
                if (data.source) setSource(data.source);
                if (data.scorecards?.length) setScorecards(data.scorecards);
                if (data.avg_score != null) setAvgScore(data.avg_score);
            }
        }).catch(() => { });
    }, []);

    const handleGenerate = async () => {
        setLoading(true);
        try {
            const res = await devopsAPI.generateOpsReview();
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
            console.error('Ops review generation failed:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleExport = (id) => {
        setExporting(id);
        setTimeout(() => setExporting(null), 1500);
    };

    const scoreColor = (v) => v >= 75 ? '#10b981' : v >= 55 ? '#f59e0b' : '#ef4444';
    const factorLabels = {
        ci_success: 'CI Success',
        deployment_success: 'Deploy Success',
        infra_files_changed: 'Infra Changes',
        monitoring_healthy: 'Monitoring',
        no_rollback: 'No Rollback',
    };

    const getReportIcon = (category) => {
        switch (category) {
            case 'CI/CD': return <BarChart2 size={16} />;
            case 'Deployments': return <Activity size={16} />;
            case 'Infrastructure': return <Shield size={16} />;
            case 'Incidents': return <AlertTriangle size={16} />;
            case 'Compliance': return <FileText size={16} />;
            default: return <FileText size={16} />;
        }
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<FileText size={24} />} value={reports.length || 5} label="Available Reports" color="blue" delay={0} />
                <StatsCard icon={<BarChart3 size={24} />} value={`${avgScore}/100`} label="Avg Ops Score" color="green" delay={0.08} />
                <StatsCard icon={<Activity size={24} />} value={scorecards.length} label="Deployments Scored" color="orange" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={issuesFound.filter(i => !i.includes('No critical')).length || 0} label="Issues Found" color="red" delay={0.24} />
            </div>

            {/* ── Ops Reviewer AI Agent ── */}
            <AnimatedCard delay={0}>
                <div className="card-body" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 24px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                        <Sparkles size={22} style={{ color: '#8b5cf6' }} />
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '1rem' }}>Ops Reviewer AI Agent</div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                                {source === 'ai' ? '🤖 AI-powered analysis' : source === 'rule_based' ? '📊 Rule-based analysis' : 'Click generate to analyse ops data'}
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
                            {loading ? <><Loader2 size={16} className="spin" /> Analysing...</> : <><RefreshCw size={16} /> Generate Ops Review</>}
                        </button>
                    </div>
                </div>
            </AnimatedCard>

            {/* Chain of Thought */}
            {showCoT && chainOfThought && (
                <AnimatedCard delay={0.05} style={{ marginTop: 10 }}>
                    <div className="card-header"><span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Brain size={16} /> Chain of Thought</span></div>
                    <div className="card-body" style={{ padding: 16, fontFamily: 'monospace', fontSize: '0.78rem', whiteSpace: 'pre-wrap', color: 'var(--text-secondary)', background: 'var(--bg-page)', borderRadius: 8 }}>
                        {chainOfThought}
                    </div>
                </AnimatedCard>
            )}

            {/* Good Practices & Issues Found */}
            {(goodPractices.length > 0 || issuesFound.length > 0) && (
                <div className="grid-2 mb-lg" style={{ marginTop: 16 }}>
                    <AnimatedCard delay={0.12}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <CheckCircle2 size={16} style={{ color: '#10b981' }} /> Good Practices
                            </span>
                            <span className="badge" style={{ background: '#10b98120', color: '#10b981' }}>{goodPractices.length}</span>
                        </div>
                        <div className="card-body">
                            {goodPractices.map((g, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10, padding: '8px 12px', borderRadius: 8, background: '#10b98108' }}>
                                    <CheckCircle2 size={14} style={{ color: '#10b981', flexShrink: 0, marginTop: 2 }} />
                                    <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{g}</span>
                                </div>
                            ))}
                        </div>
                    </AnimatedCard>
                    <AnimatedCard delay={0.18}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <XCircle size={16} style={{ color: '#ef4444' }} /> Issues Found
                            </span>
                            <span className="badge" style={{ background: '#ef444420', color: '#ef4444' }}>{issuesFound.length}</span>
                        </div>
                        <div className="card-body">
                            {issuesFound.map((issue, i) => (
                                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 10, padding: '8px 12px', borderRadius: 8, background: '#ef444408' }}>
                                    <XCircle size={14} style={{ color: '#ef4444', flexShrink: 0, marginTop: 2 }} />
                                    <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{issue}</span>
                                </div>
                            ))}
                        </div>
                    </AnimatedCard>
                </div>
            )}

            {/* Action Items */}
            {actionItems.length > 0 && (
                <AnimatedCard delay={0.24} style={{ marginTop: 4 }}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <ListChecks size={16} style={{ color: '#f59e0b' }} /> Action Items
                        </span>
                        <span className="badge" style={{ background: '#f59e0b20', color: '#f59e0b' }}>{actionItems.length}</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead><tr><th>Action</th><th>Assignee</th><th>Deadline</th><th>Priority</th></tr></thead>
                                <tbody>
                                    {actionItems.map((a, i) => (
                                        <tr key={i}>
                                            <td style={{ fontSize: '0.82rem' }}>{a.action}</td>
                                            <td>{a.assignee}</td>
                                            <td>{a.deadline}</td>
                                            <td><span className={`badge ${a.priority === 'Critical' ? 'badge-red' : a.priority === 'High' ? 'badge-orange' : a.priority === 'Medium' ? 'badge-yellow' : 'badge-green'}`}>{a.priority}</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}

            {/* AI Summary */}
            {aiSummary && (
                <AnimatedCard delay={0.3} style={{ marginTop: 16 }}>
                    <div className="card-body" style={{
                        background: 'linear-gradient(135deg, #8b5cf620, #6366f120)', borderRadius: 12,
                        padding: 20, border: '1px solid #8b5cf630'
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                            <Sparkles size={16} style={{ color: '#8b5cf6' }} />
                            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: '#8b5cf6' }}>AI Ops Review Summary</span>
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.7, margin: 0 }}>{aiSummary}</p>
                    </div>
                </AnimatedCard>
            )}

            {/* Per-Deployment Scorecards */}
            {scorecards.length > 0 && (
                <AnimatedCard delay={0.36} style={{ marginTop: 16 }}>
                    <div className="card-header">
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <BarChart3 size={18} style={{ color: '#3b82f6' }} /> Per-Deployment Scorecards
                        </span>
                        <span className="badge" style={{ background: '#3b82f620', color: '#3b82f6', fontWeight: 700 }}>
                            WEIGHTS: 30 + 30 + 15 + 15 + 10 = 100
                        </span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Deployment</th>
                                        <th>CI (30)</th>
                                        <th>Deploy (30)</th>
                                        <th>Infra (15)</th>
                                        <th>Monitor (15)</th>
                                        <th>Rollback (10)</th>
                                        <th>Total</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {scorecards.map((card, i) => (
                                        <tr key={i}>
                                            <td>
                                                <div style={{ fontWeight: 700, fontSize: '0.82rem' }}>{card.name}</div>
                                                <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{card.environment}</div>
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

            {/* Report Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16, marginTop: 20, marginBottom: 16 }}>
                {reports.map((r, idx) => (
                    <AnimatedCard key={r.id} delay={0.5 + idx * 0.08}>
                        <div className="card-header" style={{ borderBottom: `2px solid ${r.color}20` }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <div style={{
                                    width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    background: `${r.color}15`, color: r.color
                                }}>{r.icon || getReportIcon(r.category)}</div>
                                <div>
                                    <span className="card-title" style={{ fontSize: '0.9rem' }}>{r.name}</span>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{r.category}</div>
                                </div>
                            </div>
                            <span className="badge badge-neutral" style={{ fontSize: '0.68rem' }}>{r.lastGenerated}</span>
                        </div>
                        <div className="card-body">
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>{r.description}</p>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                                {r.data?.map((d, i) => (
                                    <div key={i} style={{
                                        padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-page)',
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                                    }}>
                                        <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{d.label}</span>
                                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: r.color }}>{d.value}</span>
                                    </div>
                                ))}
                            </div>
                            <button onClick={() => handleExport(r.id)}
                                style={{
                                    width: '100%', padding: '8px 16px', borderRadius: 'var(--radius-sm)', background: r.color,
                                    color: '#fff', border: 'none', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                    opacity: exporting === r.id ? 0.6 : 1, transition: 'all 0.15s ease'
                                }}>
                                <Download size={14} /> {exporting === r.id ? 'Exporting...' : 'Export Report'}
                            </button>
                        </div>
                    </AnimatedCard>
                ))}
            </div>

            {/* Summary Charts */}
            <div className="grid-2">
                <AnimatedCard delay={0.7}>
                    <div className="card-header"><span className="card-title">Incidents by Severity</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <PieChart>
                                    <Pie data={incidentBySeverity} cx="50%" cy="50%" outerRadius={75} innerRadius={40}
                                        dataKey="value" nameKey="name" label={({ name, value }) => `${name}: ${value}`}
                                        labelLine={{ strokeWidth: 1 }}>
                                        {incidentBySeverity.map((d, i) => (
                                            <Cell key={i} fill={d.color} />
                                        ))}
                                    </Pie>
                                    <Tooltip />
                                    <Legend />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.78}>
                    <div className="card-header"><span className="card-title">Pipeline Success Rates</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={pipelineSuccess}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                                    <YAxis domain={[0, 100]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Bar dataKey="rate" radius={[4, 4, 0, 0]} name="Success %">
                                        {pipelineSuccess.map((d, i) => (
                                            <Cell key={i} fill={d.rate >= 90 ? '#10b981' : d.rate >= 75 ? '#f59e0b' : '#ef4444'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
