import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Clock, TrendingUp, XCircle, Timer, Award, BarChart3 } from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area, BarChart, Bar
} from 'recharts';
import { devAPI } from '../../services/api';

const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

export default function DevProgressHistory() {
    const [sprintContribution, setSprintContribution] = useState([]);
    const [alignmentTrend, setAlignmentTrend] = useState([]);
    const [rejectionTrend, setRejectionTrend] = useState([]);
    const [approvalDelay, setApprovalDelay] = useState([]);
    const [behaviourSnapshot, setBehaviourSnapshot] = useState([]);

    useEffect(() => {
        devAPI.progressHistory().then(data => {
            if (!data) return;
            if (Array.isArray(data.sprint_contribution)) setSprintContribution(data.sprint_contribution);
            if (Array.isArray(data.alignment_trend)) setAlignmentTrend(data.alignment_trend);
            if (Array.isArray(data.rejection_trend)) setRejectionTrend(data.rejection_trend);
            if (Array.isArray(data.approval_delay)) setApprovalDelay(data.approval_delay);
            if (Array.isArray(data.behaviour_snapshot)) setBehaviourSnapshot(data.behaviour_snapshot);
        }).catch(() => { });
    }, []);

    const latestPoints = sprintContribution.length ? sprintContribution[sprintContribution.length - 1].points : 0;
    const latestAlignment = alignmentTrend.length ? alignmentTrend[alignmentTrend.length - 1].score : 0;
    const latestRejection = rejectionTrend.length ? rejectionTrend[rejectionTrend.length - 1].rate : 0;
    const latestDelay = approvalDelay.length ? approvalDelay[approvalDelay.length - 1].hours : 0;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<TrendingUp size={24} />} value={latestPoints} label="Sprint 12 Points" trend="+2" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<BarChart3 size={24} />} value={`${latestAlignment}%`} label="Current Alignment" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={`${latestRejection}%`} label="Rejection Rate" trend="-3" trendDir="down" color="red" delay={0.16} />
                <StatsCard icon={<Timer size={24} />} value={`${latestDelay}h`} label="Avg Approval Delay" trend="-1.2" trendDir="down" color="orange" delay={0.24} />
            </div>

            {/* Charts Grid */}
            <div className="grid-2 mb-lg">
                {/* Sprint Contribution */}
                <AnimatedCard delay={0.3}>
                    <div className="card-header">
                        <span className="card-title">Sprint Contribution</span>
                        <span className="badge badge-info">Story Points</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={sprintContribution}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Bar dataKey="points" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Points" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Alignment Score Trend */}
                <AnimatedCard delay={0.38}>
                    <div className="card-header">
                        <span className="card-title">Alignment Score Trend</span>
                        <span className="badge badge-success">↑ Improving</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={alignmentTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[50, 100]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => [`${v}%`, 'Alignment']} />
                                    <Area type="monotone" dataKey="score" stroke="#10b981" fill="#10b98120" strokeWidth={2.5} dot={{ r: 4, fill: '#10b981' }} name="Score" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Rejection Rate Trend */}
                <AnimatedCard delay={0.46}>
                    <div className="card-header">
                        <span className="card-title">Rejection Rate Trend</span>
                        <span className="badge badge-warning">Monitor</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={rejectionTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[0, 40]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => [`${v}%`, 'Rejection Rate']} />
                                    <Line type="monotone" dataKey="rate" stroke="#ef4444" strokeWidth={2.5} dot={{ r: 4, fill: '#ef4444' }} name="Rate" />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Approval Delay Trend */}
                <AnimatedCard delay={0.54}>
                    <div className="card-header">
                        <span className="card-title">Approval Delay Trend</span>
                        <span className="badge badge-success">↓ Improving</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={approvalDelay}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => [`${v}h`, 'Avg Delay']} />
                                    <Area type="monotone" dataKey="hours" stroke="#f59e0b" fill="#f59e0b20" strokeWidth={2.5} dot={{ r: 4, fill: '#f59e0b' }} name="Hours" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* Bottom Section */}
            <div className="grid-2">
                {/* Behaviour Feedback Snapshot */}
                <AnimatedCard delay={0.62}>
                    <div className="card-header">
                        <span className="card-title">Behaviour Feedback Snapshot</span>
                        <span className="badge badge-neutral">View Only</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                        {behaviourSnapshot.map((b, i) => (
                            <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', width: 120, flexShrink: 0 }}>{b.label}</span>
                                <div style={{ flex: 1, height: 8, borderRadius: 4, background: '#e5e7eb' }}>
                                    <div style={{
                                        height: '100%', borderRadius: 4, width: `${b.score}%`,
                                        background: getColor(b.score), transition: 'width 0.8s ease'
                                    }} />
                                </div>
                                <span style={{ fontWeight: 700, fontSize: '0.82rem', color: getColor(b.score), width: 36, textAlign: 'right' }}>{b.score}</span>
                                <span style={{
                                    fontSize: '0.72rem', fontWeight: 600,
                                    color: b.trend === 'up' ? '#10b981' : '#ef4444'
                                }}>{b.trend === 'up' ? '↑' : '↓'}</span>
                            </div>
                        ))}
                    </div>
                </AnimatedCard>

                {/* Promotion Readiness */}
                <AnimatedCard delay={0.7}>
                    <div className="card-header">
                        <span className="card-title">Promotion Readiness</span>
                        <span className="badge badge-neutral">View Only</span>
                    </div>
                    <div className="card-body">
                        <div style={{
                            display: 'flex', flexDirection: 'column', alignItems: 'center',
                            padding: '24px 0', gap: 16
                        }}>
                            {/* Circular Progress */}
                            <div style={{ position: 'relative', width: 120, height: 120 }}>
                                <svg width="120" height="120" viewBox="0 0 120 120">
                                    <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e7eb" strokeWidth="10" />
                                    <circle cx="60" cy="60" r="50" fill="none" stroke="#10b981" strokeWidth="10"
                                        strokeDasharray={`${2 * Math.PI * 50 * 0.78} ${2 * Math.PI * 50 * 0.22}`}
                                        strokeDashoffset={2 * Math.PI * 50 * 0.25}
                                        strokeLinecap="round"
                                        style={{ transition: 'stroke-dasharray 1s ease' }}
                                    />
                                </svg>
                                <div style={{
                                    position: 'absolute', top: '50%', left: '50%',
                                    transform: 'translate(-50%, -50%)',
                                    textAlign: 'center'
                                }}>
                                    <div style={{ fontWeight: 800, fontSize: '1.5rem', color: '#10b981' }}>78%</div>
                                    <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>Ready</div>
                                </div>
                            </div>

                            <div style={{
                                display: 'flex', alignItems: 'center', gap: 8,
                                padding: '8px 16px', background: '#ecfdf5',
                                borderRadius: 'var(--radius-sm)', border: '1px solid #a7f3d0'
                            }}>
                                <Award size={16} style={{ color: '#10b981' }} />
                                <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#065f46' }}>
                                    On Track for Promotion
                                </span>
                            </div>

                            <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', textAlign: 'center', maxWidth: 280 }}>
                                Based on alignment scores, sprint contributions, and quality metrics over the last 6 sprints.
                            </div>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
