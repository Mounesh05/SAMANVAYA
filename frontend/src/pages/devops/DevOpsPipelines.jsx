import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Play, CheckCircle, XCircle, Clock, RefreshCw, Cpu } from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    BarChart, Bar, Cell
} from 'recharts';
import { devopsAPI } from '../../services/api';

const statusConfig = {
    Running: { bg: '#eff6ff', color: '#3b82f6', icon: <RefreshCw size={13} className="spin-icon" /> },
    Passed: { bg: '#ecfdf5', color: '#10b981', icon: <CheckCircle size={13} /> },
    Failed: { bg: '#fef2f2', color: '#ef4444', icon: <XCircle size={13} /> },
};

const getColor = (v) => v >= 90 ? '#10b981' : v >= 75 ? '#f59e0b' : '#ef4444';

export default function DevOpsPipelines() {
    const [pipelines, setPipelines] = useState([]);
    const [failureTrend, setFailureTrend] = useState([]);
    const [avgBuildTime, setAvgBuildTime] = useState([]);
    const [aiInsights, setAiInsights] = useState([]);
    const [filter, setFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        Promise.all([
            devopsAPI.pipelines().catch(() => []),
            devopsAPI.pipelineMetrics().catch(() => ({})),
        ]).then(([pipeData, metricData]) => {
            if (Array.isArray(pipeData)) setPipelines(pipeData);
            if (metricData) {
                if (metricData.failure_trend) setFailureTrend(metricData.failure_trend);
                if (metricData.avg_build_time) setAvgBuildTime(metricData.avg_build_time);
                if (metricData.ai_insights) setAiInsights(metricData.ai_insights);
            }
        }).catch(err => {
            console.error('Failed to fetch pipelines and metrics:', err);
        }).finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading pipelines...</div>;

    const filtered = filter === 'All' ? pipelines : pipelines.filter(p => p.status === filter);
    const totalPassed = pipelines.filter(p => p.status === 'Passed').length;
    const totalFailed = pipelines.filter(p => p.status === 'Failed').length;
    const avgTime = pipelines.length ? (pipelines.reduce((a, p) => a + (parseFloat(p.duration) || 0), 0) / pipelines.length).toFixed(1) : '0.0';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Play size={24} />} value={pipelines.length} label="Total Pipelines" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={totalPassed} label="Passed" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={totalFailed} label="Failed" color="red" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={`${avgTime}m`} label="Avg Build Time" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Pipelines</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                        {['All', 'Running', 'Passed', 'Failed'].map(s => (
                            <button key={s} onClick={() => setFilter(s)}
                                style={{
                                    padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                    background: filter === s ? 'var(--brand-primary)' : 'var(--bg-page)',
                                    color: filter === s ? '#fff' : 'var(--text-secondary)',
                                    border: filter === s ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s ease'
                                }}>{s}</button>
                        ))}
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Pipeline</th><th>Branch</th><th>Last Run</th><th>Status</th>
                                    <th>Duration</th><th>Triggered By</th><th>Success Rate</th><th>Retries</th><th>Flaky</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.length === 0 && (
                                    <tr>
                                        <td colSpan={9} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No pipelines found matching "{filter}".
                                        </td>
                                    </tr>
                                )}
                                {filtered.map(p => {
                                    const cfg = statusConfig[p.status] || statusConfig.Running;
                                    return (
                                        <tr key={p.id}>
                                            <td><span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{p.name}</span></td>
                                            <td><span style={{ fontFamily: "'Courier New', monospace", fontSize: '0.82rem', background: 'var(--bg-page)', padding: '2px 8px', borderRadius: 4 }}>{p.branch}</span></td>
                                            <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{p.lastRun}</td>
                                            <td>
                                                <span className="badge" style={{ background: cfg.bg, color: cfg.color, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                                    {cfg.icon} {p.status}
                                                </span>
                                            </td>
                                            <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                                <Clock size={12} style={{ display: 'inline', marginRight: 4 }} />{p.duration}
                                            </td>
                                            <td><span className="badge badge-neutral">{p.triggeredBy}</span></td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <div style={{ width: 50, height: 5, borderRadius: 3, background: '#e5e7eb' }}>
                                                        <div style={{ height: '100%', borderRadius: 3, width: `${p.successRate}%`, background: getColor(p.successRate) }} />
                                                    </div>
                                                    <span style={{ fontWeight: 700, fontSize: '0.78rem', color: getColor(p.successRate) }}>{p.successRate}%</span>
                                                </div>
                                            </td>
                                            <td style={{ fontWeight: 600 }}>{p.retries}</td>
                                            <td>
                                                {p.flaky ? (
                                                    <span className="badge badge-danger" style={{ fontSize: '0.68rem' }}>Flaky</span>
                                                ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>}
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            <div className="grid-2 mb-lg" style={{ marginTop: 16 }}>
                <AnimatedCard delay={0.4}>
                    <div className="card-header"><span className="card-title">Failure Trend</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={failureTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Line type="monotone" dataKey="failures" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 4, fill: '#ef4444' }} name="Failures" />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.48}>
                    <div className="card-header"><span className="card-title">Avg Build Time (min)</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={avgBuildTime}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="pipeline" tick={{ fontSize: 10 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Bar dataKey="time" radius={[4, 4, 0, 0]} name="Minutes">
                                        {avgBuildTime.map((d, i) => (
                                            <Cell key={i} fill={d.time <= 2 ? '#10b981' : d.time <= 4 ? '#3b82f6' : '#f59e0b'} />
                                        ))}
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {aiInsights.length > 0 && (
                <AnimatedCard delay={0.56}>
                    <div className="card-header">
                        <span className="card-title">AI Insights</span>
                        <span className="badge badge-info"><Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />AI</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {aiInsights.map((ai, i) => (
                            <div key={i} style={{
                                padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                                background: ai.type === 'success' ? 'var(--success-bg)' : ai.type === 'danger' ? 'var(--danger-bg)' : 'var(--warning-bg)',
                                borderLeft: `3px solid ${ai.type === 'success' ? 'var(--success)' : ai.type === 'danger' ? 'var(--danger)' : 'var(--warning)'}`,
                            }}>
                                <div style={{ fontSize: '0.85rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Cpu size={13} style={{ flexShrink: 0 }} /> {ai.text}
                                </div>
                            </div>
                        ))}
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
