import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Activity, Shield, Zap, Server, BarChart3, AlertTriangle, Brain, TrendingDown } from 'lucide-react';
import { ceoAPI } from '../../services/api';

const getRiskColor = (score) => {
    if (score >= 70) return '#ef4444';
    if (score >= 50) return '#f59e0b';
    if (score >= 30) return '#3b82f6';
    return '#10b981';
};

export default function ExecutionHealth() {
    const [healthFactors, setHealthFactors] = useState([]);
    const [storyRisks, setStoryRisks] = useState([]);
    const [devRiskContribution, setDevRiskContribution] = useState([
        { name: 'Vikram Singh', riskScore: 45, storiesAtRisk: 2, avgDelay: '1.2 days' },
        { name: 'Sneha Iyer', riskScore: 12, storiesAtRisk: 0, avgDelay: '0.4 days' },
    ]);

    useEffect(() => {
        ceoAPI.healthFactors().then(setHealthFactors).catch(() => { });
        ceoAPI.storyRisks().then(setStoryRisks).catch(() => { });
        ceoAPI.devRiskContribution().then(setDevRiskContribution).catch(() => { });
    }, []);

    const overallHealth = healthFactors.length
        ? healthFactors.reduce((sum, f) => sum + (f.score * f.weight / 100), 0).toFixed(1)
        : '—';

    return (
        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Activity size={24} />} value={`${overallHealth}%`} label="Overall Health" trend="+2.1% this sprint" trendDir="up" color="green" delay={0} />
                <StatsCard icon={<Shield size={24} />} value="87%" label="Alignment Accuracy" trend="+3.5%" trendDir="up" color="blue" delay={0.08} />
                <StatsCard icon={<Zap size={24} />} value="4.2 hrs" label="Approval Speed" trend="-1.1 hrs" trendDir="down" color="orange" delay={0.16} />
                <StatsCard icon={<Server size={24} />} value="95%" label="CI Stability" trend="All green" trendDir="up" color="purple" delay={0.24} />
            </div>

            {/* Health Score Breakdown */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Health Score Breakdown</span>
                    <span className="badge badge-success">Score: {overallHealth}%</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gap: 16 }}>
                        {healthFactors.map(f => (
                            <div key={f.name}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6, fontSize: '0.85rem' }}>
                                    <span style={{ fontWeight: 600 }}>{f.name}</span>
                                    <span style={{ color: 'var(--text-secondary)' }}>
                                        <strong style={{ color: f.color }}>{f.score}%</strong> · Weight: {f.weight}%
                                    </span>
                                </div>
                                <div style={{ height: 10, background: 'var(--bg-secondary)', borderRadius: 5, overflow: 'hidden' }}>
                                    <div style={{ height: '100%', width: `${f.score}%`, background: f.color, borderRadius: 5, transition: 'width 0.8s ease' }} />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </AnimatedCard>

            <div className="grid-2 mb-lg" style={{ marginTop: 20 }}>
                {/* Risk Heatmap */}
                <AnimatedCard delay={0.4}>
                    <div className="card-header">
                        <span className="card-title">Story Risk Heatmap</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Story</th>
                                        <th>Developer</th>
                                        <th>Risk Score</th>
                                        <th>Reason</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {storyRisks.map(s => (
                                        <tr key={s.id}>
                                            <td>
                                                <span style={{ fontWeight: 700, color: '#3b82f6', marginRight: 6 }}>{s.id}</span>
                                                <span style={{ fontSize: '0.82rem' }}>{s.title}</span>
                                            </td>
                                            <td>{s.developer}</td>
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                    <div style={{ width: 60, height: 8, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                                                        <div style={{ height: '100%', width: `${s.risk}%`, background: getRiskColor(s.risk), borderRadius: 4 }} />
                                                    </div>
                                                    <span style={{ fontWeight: 700, color: getRiskColor(s.risk), fontSize: '0.82rem' }}>{s.risk}</span>
                                                </div>
                                            </td>
                                            <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{s.reason}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Developer Risk Contribution */}
                <AnimatedCard delay={0.48}>
                    <div className="card-header">
                        <span className="card-title">Developer Risk Contribution</span>
                    </div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>Developer</th>
                                        <th>Risk Score</th>
                                        <th>Stories at Risk</th>
                                        <th>Avg Delay</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {devRiskContribution.map(d => (
                                        <tr key={d.name}>
                                            <td style={{ fontWeight: 600 }}>{d.name}</td>
                                            <td>
                                                <span style={{ fontWeight: 700, color: getRiskColor(d.riskScore) }}>{d.riskScore}</span>
                                            </td>
                                            <td>{d.storiesAtRisk}</td>
                                            <td>{d.avgDelay}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* Predictive Signal */}
            <AnimatedCard delay={0.56}>
                <div className="card-header">
                    <span className="card-title"><Brain size={18} style={{ marginRight: 6, verticalAlign: 'middle' }} /> AI Predictive Signal</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
                        <div style={{ flex: 1, minWidth: 280, padding: '20px 24px', background: 'linear-gradient(135deg, #fef3c7, #fde68a)', borderRadius: 'var(--radius-md)', border: '1px solid #fbbf24' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#92400e', fontWeight: 700, fontSize: '0.85rem' }}>
                                <AlertTriangle size={16} /> Warning
                            </div>
                            <div style={{ color: '#78350f', fontWeight: 500, lineHeight: 1.6 }}>
                                "If current delay in <strong>US-104 (SSO config)</strong> and <strong>US-109 (CI/CD pipeline)</strong> continues, sprint health may drop <strong>8%</strong> by end of sprint."
                            </div>
                        </div>
                        <div style={{ flex: 1, minWidth: 280, padding: '20px 24px', background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', borderRadius: 'var(--radius-md)', border: '1px solid #60a5fa' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10, color: '#1e40af', fontWeight: 700, fontSize: '0.85rem' }}>
                                <TrendingDown size={16} /> Recommendation
                            </div>
                            <div style={{ color: '#1e3a5f', fontWeight: 500, lineHeight: 1.6 }}>
                                "Consider reassigning infrastructure tasks from Ananya R. or escalating the DevOps provisioning ticket to unblock the pipeline."
                            </div>
                        </div>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
