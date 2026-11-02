import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { 
    AlertTriangle, Shield, Clock, TrendingUp, AlertCircle, CheckCircle, 
    XCircle, ArrowRight, X, Eye, Activity, Sparkles, User, GitPullRequest, 
    Layers, Check, ExternalLink, Zap, HelpCircle
} from 'lucide-react';
import { ceoAPI } from '../../services/api';

const riskLevelColors = { Critical: '#ef4444', High: '#f59e0b', Medium: '#3b82f6', Low: '#10b981' };

export default function RiskEscalations() {
    const [activeRisks, setActiveRisks] = useState([]);
    const [timeline, setTimeline] = useState([]);
    const [patterns, setPatterns] = useState([]);
    const [selectedRisk, setSelectedRisk] = useState(null);
    const [selectedEscalation, setSelectedEscalation] = useState(null);
    const [acknowledgedRisks, setAcknowledgedRisks] = useState({});
    const [escalationResolutions, setEscalationResolutions] = useState({});

    useEffect(() => {
        ceoAPI.activeRisks().then(setActiveRisks).catch(() => { });
        ceoAPI.escalationEvents().then(setTimeline).catch(() => { });
        ceoAPI.riskPatterns().then(setPatterns).catch(() => { });
    }, []);

    const toggleAcknowledge = (storyId) => {
        setAcknowledgedRisks(prev => ({
            ...prev,
            [storyId]: !prev[storyId]
        }));
    };

    const handleUpdateResolution = (id, newStatus) => {
        setEscalationResolutions(prev => ({ ...prev, [id]: newStatus }));
        setTimeline(prev => prev.map(item => item.id === id ? { ...item, resolution: newStatus } : item));
        if (selectedEscalation && selectedEscalation.id === id) {
            setSelectedEscalation(prev => ({ ...prev, resolution: newStatus }));
        }
    };

    return (
        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<AlertTriangle size={24} />} value="4" label="Active Risks" trend="2 critical" trendDir="up" color="red" delay={0} />
                <StatsCard icon={<Shield size={24} />} value="3" label="Open Escalations" trend="1 pending" trendDir="up" color="orange" delay={0.08} />
                <StatsCard icon={<Clock size={24} />} value="4.0 hrs" label="Avg Resolution Time" trend="-1.2 hrs" trendDir="down" color="blue" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value="3" label="Patterns Detected" trend="AI analyzed" trendDir="up" color="purple" delay={0.24} />
            </div>

            {/* Active Risks Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <span className="card-title">Active Risks</span>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                            Click any risk row to inspect where it is lagging and view root-cause diagnostics
                        </div>
                    </div>
                    <span className="badge badge-neutral" style={{ fontSize: '0.78rem' }}>
                        {activeRisks.length} Tracked Stories
                    </span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Story ID</th>
                                    <th>Risk Type</th>
                                    <th>Risk Level</th>
                                    <th>Responsible</th>
                                    <th>Description & Lag Focus</th>
                                    <th style={{ textAlign: 'right' }}>Lag Analysis</th>
                                </tr>
                            </thead>
                            <tbody>
                                {activeRisks.map(r => {
                                    const isAck = acknowledgedRisks[r.storyId];
                                    return (
                                        <tr 
                                            key={r.storyId}
                                            onClick={() => setSelectedRisk(r)}
                                            style={{ 
                                                cursor: 'pointer',
                                                transition: 'background-color 0.15s ease',
                                                backgroundColor: isAck ? 'rgba(16, 185, 129, 0.04)' : undefined
                                            }}
                                            onMouseEnter={e => e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.06)'}
                                            onMouseLeave={e => e.currentTarget.style.backgroundColor = isAck ? 'rgba(16, 185, 129, 0.04)' : ''}
                                        >
                                            <td>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <span style={{ fontWeight: 800, color: '#2563eb' }}>{r.storyId}</span>
                                                    {isAck && (
                                                        <span title="Acknowledged by CEO" style={{ color: '#10b981', display: 'flex', alignItems: 'center' }}>
                                                            <CheckCircle size={14} />
                                                        </span>
                                                    )}
                                                </div>
                                                {r.title && (
                                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', maxWidth: 140, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                        {r.title}
                                                    </div>
                                                )}
                                            </td>
                                            <td><span className="badge badge-info">{r.riskType}</span></td>
                                            <td>
                                                <span 
                                                    className="badge" 
                                                    style={{ 
                                                        background: riskLevelColors[r.riskLevel], 
                                                        color: '#fff',
                                                        display: 'inline-flex',
                                                        alignItems: 'center',
                                                        gap: 5
                                                    }}
                                                >
                                                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#fff', display: 'inline-block' }} />
                                                    {r.riskLevel}
                                                </span>
                                            </td>
                                            <td style={{ fontWeight: 600 }}>{r.responsible}</td>
                                            <td>
                                                <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                                                    {r.desc}
                                                </div>
                                                {r.whereLagging && (
                                                    <div style={{ fontSize: '0.74rem', color: '#dc2626', fontWeight: 600, marginTop: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                                                        <Clock size={12} />
                                                        <span>Lagging at: {r.whereLagging}</span>
                                                    </div>
                                                )}
                                            </td>
                                            <td style={{ textAlign: 'right' }}>
                                                <button 
                                                    className="btn btn-sm btn-secondary"
                                                    style={{
                                                        display: 'inline-flex',
                                                        alignItems: 'center',
                                                        gap: 5,
                                                        fontSize: '0.78rem',
                                                        fontWeight: 600,
                                                        padding: '4px 10px',
                                                        background: '#eff6ff',
                                                        color: '#1d4ed8',
                                                        borderColor: '#bfdbfe'
                                                    }}
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        setSelectedRisk(r);
                                                    }}
                                                >
                                                    <Eye size={13} />
                                                    <span>Inspect</span>
                                                </button>
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Escalation Timeline */}
            <AnimatedCard delay={0.38} style={{ marginTop: 24 }}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <span className="card-title">Escalation Timeline</span>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-tertiary)', marginTop: 2 }}>
                            Click an incident to inspect root cause telemetry, lag duration, and response chain
                        </div>
                    </div>
                    <span className="badge badge-warning" style={{ fontSize: '0.78rem' }}>
                        Live Incident Feed
                    </span>
                </div>
                <div className="card-body">
                    <div style={{ position: 'relative', paddingLeft: 32 }}>
                        <div style={{ position: 'absolute', left: 11, top: 0, bottom: 0, width: 2, background: 'var(--border-color)' }} />
                        {timeline.map((t, i) => {
                            const resStatus = escalationResolutions[t.id] || t.resolution;
                            const isPending = resStatus === 'Pending';
                            const isResolved = resStatus === 'Resolved';
                            
                            return (
                                <div 
                                    key={t.id} 
                                    onClick={() => setSelectedEscalation({ ...t, resolution: resStatus })}
                                    style={{ 
                                        position: 'relative', 
                                        paddingBottom: i < timeline.length - 1 ? 26 : 0,
                                        cursor: 'pointer',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        transition: 'all 0.2s ease',
                                        marginBottom: i < timeline.length - 1 ? 8 : 0,
                                    }}
                                    onMouseEnter={e => {
                                        e.currentTarget.style.backgroundColor = 'rgba(59, 130, 246, 0.05)';
                                        e.currentTarget.style.boxShadow = '0 2px 8px rgba(0,0,0,0.06)';
                                    }}
                                    onMouseLeave={e => {
                                        e.currentTarget.style.backgroundColor = 'transparent';
                                        e.currentTarget.style.boxShadow = 'none';
                                    }}
                                >
                                    <div 
                                        style={{ 
                                            position: 'absolute', 
                                            left: -27, 
                                            top: 14, 
                                            width: 14, 
                                            height: 14, 
                                            borderRadius: '50%', 
                                            background: isPending ? '#ef4444' : isResolved ? '#10b981' : '#f59e0b', 
                                            border: '3px solid #fff', 
                                            boxShadow: '0 0 0 2px var(--border-color)' 
                                        }} 
                                    />
                                    
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                        <div style={{ fontSize: '0.74rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>
                                            {t.time}
                                        </div>
                                        <span style={{ fontSize: '0.74rem', color: '#2563eb', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                            <Activity size={12} /> Inspect Incident →
                                        </span>
                                    </div>

                                    <div style={{ fontWeight: 700, fontSize: '0.92rem', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 8 }}>
                                        {t.event}
                                        <span className="badge" style={{ background: riskLevelColors[t.severity], color: '#fff', fontSize: '0.68rem' }}>
                                            {t.severity}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                        {t.detail}
                                    </div>
                                    <div style={{ display: 'flex', gap: 20, fontSize: '0.78rem', color: 'var(--text-tertiary)', flexWrap: 'wrap' }}>
                                        <span>Notified: <strong style={{ color: 'var(--text-primary)' }}>{t.notified}</strong></span>
                                        <span>Status: <strong style={{ color: isPending ? '#ef4444' : isResolved ? '#10b981' : '#f59e0b' }}>{resStatus}</strong></span>
                                        {t.whereLagging && (
                                            <span style={{ color: '#dc2626' }}>
                                                Lagging at: <strong>{t.whereLagging}</strong>
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </AnimatedCard>

            {/* Risk Pattern Analysis */}
            <AnimatedCard delay={0.46} style={{ marginTop: 24 }}>
                <div className="card-header">
                    <span className="card-title">Risk Pattern Analysis</span>
                    <span className="badge badge-info">AI Detected</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gap: 16 }}>
                        {patterns.map((p, i) => (
                            <div key={i} style={{ padding: '18px 22px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', borderLeft: `4px solid ${p.color}` }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                                    <span style={{ fontWeight: 700, fontSize: '0.92rem' }}>{p.title}</span>
                                    <span className="badge" style={{ background: `${p.color}20`, color: p.color, fontWeight: 600 }}>{p.occurrences} occurrences</span>
                                </div>
                                <div style={{ display: 'flex', gap: 24, fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 10 }}>
                                    <span>Across: <strong>{p.sprints}</strong></span>
                                    <span>Impact: <strong>{p.impact}</strong></span>
                                </div>
                                <div style={{ fontSize: '0.82rem', color: 'var(--text-primary)', padding: '10px 14px', background: '#fff', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}>
                                    <strong>💡 Recommendation:</strong> {p.recommendation}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </AnimatedCard>

            {/* ─── ACTIVE RISK DETAIL & LAGGING ANALYSIS MODAL ─── */}
            {selectedRisk && (
                <div 
                    onClick={e => { if (e.target === e.currentTarget) setSelectedRisk(null); }}
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(5, 10, 24, 0.65)',
                        backdropFilter: 'blur(5px)',
                        zIndex: 2000,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '24px 16px',
                        overflowY: 'auto'
                    }}
                >
                    <div 
                        style={{
                            background: '#ffffff',
                            borderRadius: 18,
                            width: 680,
                            maxWidth: '100%',
                            boxShadow: '0 25px 60px rgba(0, 0, 0, 0.3)',
                            overflow: 'hidden',
                            border: '1px solid var(--border-color)',
                            animation: 'fadeIn 0.25s ease'
                        }}
                    >
                        {/* Modal Header */}
                        <div 
                            style={{
                                padding: '20px 24px',
                                background: 'linear-gradient(135deg, #f8fafc 0%, #edf2f7 100%)',
                                borderBottom: '1px solid #e2e8f0',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div 
                                    style={{
                                        width: 42,
                                        height: 42,
                                        borderRadius: 10,
                                        background: `${riskLevelColors[selectedRisk.riskLevel]}15`,
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: riskLevelColors[selectedRisk.riskLevel]
                                    }}
                                >
                                    <AlertTriangle size={24} />
                                </div>
                                <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <span style={{ fontWeight: 800, fontSize: '1.15rem', color: '#1e293b' }}>
                                            {selectedRisk.storyId}
                                        </span>
                                        <span className="badge" style={{ background: riskLevelColors[selectedRisk.riskLevel], color: '#fff', fontSize: '0.72rem' }}>
                                            {selectedRisk.riskLevel} Severity
                                        </span>
                                        <span className="badge badge-info" style={{ fontSize: '0.72rem' }}>
                                            {selectedRisk.riskType}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '0.85rem', color: '#64748b', marginTop: 2, fontWeight: 500 }}>
                                        {selectedRisk.title || selectedRisk.desc}
                                    </div>
                                </div>
                            </div>
                            <button 
                                onClick={() => setSelectedRisk(null)}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    color: '#94a3b8',
                                    padding: 6,
                                    borderRadius: 6
                                }}
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Modal Body */}
                        <div style={{ padding: '24px 26px', maxHeight: '72vh', overflowY: 'auto' }}>
                            {/* Where it is lagging banner */}
                            <div 
                                style={{
                                    background: 'linear-gradient(135deg, #fff1f2 0%, #ffe4e6 100%)',
                                    border: '1.5px solid #fecdd3',
                                    borderRadius: 12,
                                    padding: '16px 18px',
                                    marginBottom: 20
                                }}
                            >
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, color: '#be123c', fontWeight: 800, fontSize: '0.86rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        <Clock size={16} /> WHERE IT IS LAGGING
                                    </div>
                                    <span 
                                        style={{
                                            background: '#e11d48',
                                            color: '#fff',
                                            fontSize: '0.75rem',
                                            fontWeight: 700,
                                            padding: '2px 10px',
                                            borderRadius: 999
                                        }}
                                    >
                                        {selectedRisk.lagDuration || '+2.4 Days Behind Schedule'}
                                    </span>
                                </div>
                                <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#881337', marginBottom: 4 }}>
                                    {selectedRisk.whereLagging || 'Integration & Code Review Pipeline Gate'}
                                </div>
                                <div style={{ fontSize: '0.82rem', color: '#9f1239', lineHeight: 1.5 }}>
                                    Delivery confidence dropped to <strong>{selectedRisk.deliveryConfidence || '68% (Target: 90%)'}</strong>. Current development pace is insufficient to meet sprint cut-off without targeted intervention.
                                </div>
                            </div>

                            {/* Root Cause Analysis */}
                            <div style={{ marginBottom: 20 }}>
                                <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1e293b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Activity size={16} style={{ color: '#3b82f6' }} /> Root Cause & Technical Hold-up
                                </div>
                                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '14px 16px', fontSize: '0.84rem', color: '#334155', lineHeight: 1.6 }}>
                                    {selectedRisk.rootCause || selectedRisk.desc}
                                </div>
                            </div>

                            {/* Blockers List */}
                            <div style={{ marginBottom: 20 }}>
                                <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1e293b', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <AlertCircle size={16} style={{ color: '#ef4444' }} /> Active Blockers
                                </div>
                                <div style={{ display: 'grid', gap: 8 }}>
                                    {(selectedRisk.blockers || [
                                        'Waiting on third-party security approval for API scopes',
                                        'Staging SSL certificate mismatch on sandbox endpoint',
                                        'PR #104 review turnaround exceeds 36 hours'
                                    ]).map((blocker, bIdx) => (
                                        <div 
                                            key={bIdx}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'flex-start',
                                                gap: 10,
                                                padding: '10px 14px',
                                                background: '#fef2f2',
                                                border: '1px solid #fee2e2',
                                                borderRadius: 8,
                                                fontSize: '0.82rem',
                                                color: '#991b1b'
                                            }}
                                        >
                                            <span style={{ color: '#ef4444', fontWeight: 800, marginTop: 1 }}>•</span>
                                            <span>{blocker}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Milestone & Downstream Impact */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 20 }}>
                                <div style={{ padding: '12px 14px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10 }}>
                                    <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
                                        Sprint Milestone Impact
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1e293b' }}>
                                        {selectedRisk.sprintImpact || 'Sprint 23 Milestone at Risk'}
                                    </div>
                                </div>
                                <div style={{ padding: '12px 14px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10 }}>
                                    <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: 4 }}>
                                        Responsible Engineer
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: '0.88rem', color: '#1e293b', display: 'flex', alignItems: 'center', gap: 6 }}>
                                        <User size={15} style={{ color: '#3b82f6' }} />
                                        <span>{selectedRisk.responsible}</span>
                                        <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 400 }}>
                                            ({selectedRisk.responsibleRole || 'Developer'})
                                        </span>
                                    </div>
                                </div>
                            </div>

                            {/* Blocked Stories Chips */}
                            {selectedRisk.blockedStories && selectedRisk.blockedStories.length > 0 && (
                                <div style={{ marginBottom: 20 }}>
                                    <div style={{ fontSize: '0.76rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase', marginBottom: 6 }}>
                                        Directly Blocked Downstream Stories
                                    </div>
                                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                        {selectedRisk.blockedStories.map((bs, bsIdx) => (
                                            <span 
                                                key={bsIdx}
                                                style={{
                                                    fontSize: '0.78rem',
                                                    padding: '4px 10px',
                                                    borderRadius: 6,
                                                    background: '#fee2e2',
                                                    color: '#991b1b',
                                                    border: '1px solid #fecaca',
                                                    fontWeight: 600
                                                }}
                                            >
                                                {bs}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}

                            {/* AI Recommendation */}
                            <div 
                                style={{
                                    background: 'linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%)',
                                    border: '1px solid #bbf7d0',
                                    borderRadius: 12,
                                    padding: '16px 18px',
                                    display: 'flex',
                                    gap: 12
                                }}
                            >
                                <Sparkles size={20} style={{ color: '#16a34a', flexShrink: 0, marginTop: 2 }} />
                                <div>
                                    <div style={{ fontWeight: 800, fontSize: '0.86rem', color: '#166534', marginBottom: 4 }}>
                                        AI Executive Mitigation Plan
                                    </div>
                                    <div style={{ fontSize: '0.83rem', color: '#15803d', lineHeight: 1.55 }}>
                                        {selectedRisk.aiMitigation || 'Provision mock sandbox endpoints to unblock local QA validation and reassign code review to Tech Lead to prevent release pipeline stalls.'}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Modal Footer */}
                        <div 
                            style={{
                                padding: '16px 24px',
                                background: '#f8fafc',
                                borderTop: '1px solid #e2e8f0',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}
                        >
                            <button
                                className="btn btn-secondary"
                                style={{
                                    display: 'inline-flex',
                                    alignItems: 'center',
                                    gap: 6,
                                    fontSize: '0.84rem'
                                }}
                                onClick={() => toggleAcknowledge(selectedRisk.storyId)}
                            >
                                <Check size={16} style={{ color: acknowledgedRisks[selectedRisk.storyId] ? '#10b981' : undefined }} />
                                <span>{acknowledgedRisks[selectedRisk.storyId] ? 'Risk Acknowledged ✓' : 'Acknowledge Risk'}</span>
                            </button>
                            <div style={{ display: 'flex', gap: 10 }}>
                                <button 
                                    className="btn btn-secondary"
                                    onClick={() => {
                                        alert(`Notice dispatched to ${selectedRisk.responsible} and Tech Lead.`);
                                    }}
                                >
                                    Ping Responsible Lead
                                </button>
                                <button 
                                    className="btn btn-primary"
                                    onClick={() => setSelectedRisk(null)}
                                >
                                    Done
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ─── ESCALATION INCIDENT DIAGNOSTICS MODAL ─── */}
            {selectedEscalation && (
                <div 
                    onClick={e => { if (e.target === e.currentTarget) setSelectedEscalation(null); }}
                    style={{
                        position: 'fixed',
                        inset: 0,
                        background: 'rgba(5, 10, 24, 0.65)',
                        backdropFilter: 'blur(5px)',
                        zIndex: 2000,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '24px 16px',
                        overflowY: 'auto'
                    }}
                >
                    <div 
                        style={{
                            background: '#ffffff',
                            borderRadius: 18,
                            width: 660,
                            maxWidth: '100%',
                            boxShadow: '0 25px 60px rgba(0, 0, 0, 0.3)',
                            overflow: 'hidden',
                            border: '1px solid var(--border-color)',
                            animation: 'fadeIn 0.25s ease'
                        }}
                    >
                        {/* Header */}
                        <div 
                            style={{
                                padding: '20px 24px',
                                background: 'linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%)',
                                borderBottom: '1px solid #fed7aa',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between'
                            }}
                        >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div 
                                    style={{
                                        width: 42,
                                        height: 42,
                                        borderRadius: 10,
                                        background: '#ea580c15',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        color: '#ea580c'
                                    }}
                                >
                                    <AlertCircle size={24} />
                                </div>
                                <div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <span style={{ fontWeight: 800, fontSize: '1.12rem', color: '#1e293b' }}>
                                            {selectedEscalation.event}
                                        </span>
                                        <span className="badge" style={{ background: riskLevelColors[selectedEscalation.severity], color: '#fff', fontSize: '0.72rem' }}>
                                            {selectedEscalation.severity}
                                        </span>
                                    </div>
                                    <div style={{ fontSize: '0.8rem', color: '#7c2d12', marginTop: 2 }}>
                                        Incident ID: {selectedEscalation.id} · Triggered: {selectedEscalation.time}
                                    </div>
                                </div>
                            </div>
                            <button 
                                onClick={() => setSelectedEscalation(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9a3412', padding: 6 }}
                            >
                                <X size={20} />
                            </button>
                        </div>

                        {/* Body */}
                        <div style={{ padding: '22px 26px', maxHeight: '72vh', overflowY: 'auto' }}>
                            {/* Where it is lagging banner */}
                            <div 
                                style={{
                                    background: '#fef2f2',
                                    border: '1.5px solid #fecaca',
                                    borderRadius: 12,
                                    padding: '16px 18px',
                                    marginBottom: 18
                                }}
                            >
                                <div style={{ fontSize: '0.76rem', color: '#dc2626', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 4 }}>
                                    🚨 FAILED COMPONENT & WHERE LAGGING
                                </div>
                                <div style={{ fontWeight: 700, fontSize: '0.96rem', color: '#991b1b', marginBottom: 4 }}>
                                    {selectedEscalation.whereLagging || selectedEscalation.detail}
                                </div>
                                <div style={{ fontSize: '0.82rem', color: '#b91c1c' }}>
                                    Duration: <strong>{selectedEscalation.lagDuration || 'Active incident'}</strong> · Assigned Lead: <strong>{selectedEscalation.leadAssigned || 'Vikram Singh'}</strong>
                                </div>
                            </div>

                            {/* Root cause */}
                            <div style={{ marginBottom: 18 }}>
                                <div style={{ fontWeight: 700, fontSize: '0.86rem', color: '#1e293b', marginBottom: 6 }}>
                                    Detailed Root Cause Breakdown
                                </div>
                                <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 10, padding: '12px 16px', fontSize: '0.84rem', color: '#334155', lineHeight: 1.55 }}>
                                    {selectedEscalation.rootCause || selectedEscalation.detail}
                                </div>
                            </div>

                            {/* Impact */}
                            <div style={{ marginBottom: 18 }}>
                                <div style={{ fontWeight: 700, fontSize: '0.86rem', color: '#1e293b', marginBottom: 6 }}>
                                    System & Delivery Impact
                                </div>
                                <div style={{ background: '#fffbeb', border: '1px solid #fef3c7', borderRadius: 10, padding: '12px 16px', fontSize: '0.84rem', color: '#92400e', lineHeight: 1.55 }}>
                                    {selectedEscalation.impact || 'Release branch deploy halted; 3 downstream payment stories blocked from QA sign-off.'}
                                </div>
                            </div>

                            {/* Stakeholders & Action taken */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 18 }}>
                                <div style={{ padding: '12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                                    <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Alerted Stakeholders</div>
                                    <div style={{ fontWeight: 700, fontSize: '0.86rem', color: '#1e293b', marginTop: 3 }}>
                                        {selectedEscalation.notified}
                                    </div>
                                </div>
                                <div style={{ padding: '12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8 }}>
                                    <div style={{ fontSize: '0.74rem', color: '#64748b', fontWeight: 600, textTransform: 'uppercase' }}>Resolution Status</div>
                                    <div style={{ fontWeight: 700, fontSize: '0.86rem', color: selectedEscalation.resolution === 'Resolved' ? '#10b981' : '#ef4444', marginTop: 3 }}>
                                        {selectedEscalation.resolution}
                                    </div>
                                </div>
                            </div>

                            {/* Recommended mitigation */}
                            <div style={{ background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, padding: '14px 16px' }}>
                                <div style={{ fontWeight: 700, fontSize: '0.84rem', color: '#1e40af', marginBottom: 4 }}>
                                    Recommended Action Plan
                                </div>
                                <div style={{ fontSize: '0.82rem', color: '#1d4ed8', lineHeight: 1.5 }}>
                                    {selectedEscalation.recommendedAction || 'Authorize emergency hotfix patch version 2.4.1 to unblock CI gate.'}
                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div 
                            style={{
                                padding: '16px 24px',
                                background: '#f8fafc',
                                borderTop: '1px solid #e2e8f0',
                                display: 'flex',
                                justifyContent: 'space-between',
                                alignItems: 'center'
                            }}
                        >
                            <div style={{ display: 'flex', gap: 8 }}>
                                <button
                                    className="btn btn-sm btn-secondary"
                                    onClick={() => handleUpdateResolution(selectedEscalation.id, 'In Progress')}
                                >
                                    Mark In Progress
                                </button>
                                <button
                                    className="btn btn-sm btn-secondary"
                                    style={{ color: '#10b981', borderColor: '#a7f3d0' }}
                                    onClick={() => handleUpdateResolution(selectedEscalation.id, 'Resolved')}
                                >
                                    Mark Resolved ✓
                                </button>
                            </div>
                            <button className="btn btn-primary" onClick={() => setSelectedEscalation(null)}>
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
