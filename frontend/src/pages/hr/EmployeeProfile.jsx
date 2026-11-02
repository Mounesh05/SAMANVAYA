import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import { employeesAPI, teamsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import {
    Mail, Building, Shield, Phone, BarChart3, TrendingUp, AlertTriangle,
    Award, User, MessageSquare, Zap, Clock, ArrowLeft, CheckCircle, PauseCircle, Send, Loader2,
    ArrowRightLeft, Users, ShieldCheck, X, Check
} from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const getColor = (s) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444';
const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const statusColors = { Active: '#10b981', 'On Leave': '#3b82f6', Probation: '#f59e0b' };
const verdictColors = { 'Strongly Recommend': '#10b981', 'Recommend': '#3b82f6', 'Not Recommended': '#ef4444' };
const decisionColors = { Promoted: '#10b981', Pending: '#f59e0b', Hold: '#ef4444', '—': '#94a3b8' };

function StatRow({ icon, label, value, color }) {
    return (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {icon}
                <span style={{ fontSize: '0.85rem' }}>{label}</span>
            </div>
            <span style={{ fontWeight: 700, fontSize: '0.95rem', color: color || 'var(--text-primary)' }}>{value}</span>
        </div>
    );
}

export default function EmployeeProfile() {
    const { id } = useParams();
    const navigate = useNavigate();
    const { user } = useAuth();
    const [emp, setEmp] = useState(null);
    const [loading, setLoading] = useState(true);
    const [teams, setTeams] = useState([]);
    const [saving, setSaving] = useState(false);
    
    // Transfer Modal
    const [showTransferModal, setShowTransferModal] = useState(false);
    const [targetTeam, setTargetTeam] = useState('');
    const [targetDept, setTargetDept] = useState('');
    const [transferReason, setTransferReason] = useState('');
    const [transferring, setTransferring] = useState(false);

    const loadEmployee = () => {
        setLoading(true);
        employeesAPI.getById(id)
            .then(data => {
                if (data) {
                    setEmp(data);
                    setTargetTeam(data.team_id || 'team-01');
                    setTargetDept(data.dept || 'Engineering');
                } else {
                    setEmp(null);
                }
            })
            .catch(() => setEmp(null))
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        loadEmployee();
        teamsAPI.getAll().then(tms => setTeams(Array.isArray(tms) ? tms : [])).catch(() => {});
    }, [id]);

    const handleExecuteTransfer = async (e) => {
        e.preventDefault();
        if (!emp) return;
        setTransferring(true);
        const selectedTeamObj = teams.find(t => t.team_id === targetTeam) || { name: targetTeam };
        const performer = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Claire Underwood (HR)';

        try {
            await employeesAPI.transferTeam(emp.employee_id || id, {
                team_id: targetTeam,
                team_name: selectedTeamObj.name,
                dept: targetDept,
                transferred_by: performer,
                reason: transferReason || 'Organizational team restructuring',
                name: emp.name
            });
            setShowTransferModal(false);
            loadEmployee();
        } catch (err) {
            console.error('Failed to transfer employee team:', err);
            alert('Failed to transfer employee team.');
        } finally {
            setTransferring(false);
        }
    };

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 80, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                <Loader2 size={36} className="spin" color="#3b82f6" style={{ marginBottom: 16 }} />
                <div style={{ color: 'var(--text-secondary)', fontWeight: 600 }}>Loading employee profile...</div>
            </div>
        );
    }

    if (!emp) {
        return (
            <div style={{ textAlign: 'center', padding: 60 }}>
                <h2>Employee Not Found</h2>
                <p style={{ color: 'var(--text-secondary)', marginTop: 8 }}>The requested employee ({id}) could not be located.</p>
                <button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => navigate('/employees')}>
                    ← Back to Employees
                </button>
            </div>
        );
    }

    const perfScore = typeof emp.perfScore === 'number' ? emp.perfScore : 85;
    const behaviourScore = typeof emp.behaviour === 'number' ? emp.behaviour : 8.5;
    const status = emp.status || 'Active';
    const risk = emp.risk || (perfScore < 70 ? 'High' : perfScore < 80 ? 'Medium' : 'Low');
    const alignment = emp.alignment ?? Math.round(perfScore * 0.98);
    const onTime = emp.onTime ?? Math.round(Math.min(99, perfScore * 1.04));
    const rejection = emp.rejection ?? (perfScore < 75 ? 12 : perfScore < 85 ? 6 : 3);
    const sprintContrib = emp.sprintContrib || '18 SP';

    // Safe behaviour scores
    const defaultVal = Math.min(10, Math.max(1, Math.round(behaviourScore)));
    const behaviourScores = (emp.behaviourScores && typeof emp.behaviourScores === 'object' && Object.keys(emp.behaviourScores).length > 0)
        ? emp.behaviourScores
        : {
            communication: defaultVal,
            ownership: defaultVal,
            teamwork: defaultVal,
            leadership: Math.max(4, defaultVal - 1),
            discipline: defaultVal,
        };

    const bEntries = Object.entries(behaviourScores);
    const avgBehaviour = bEntries.length > 0
        ? (bEntries.reduce((sum, [, val]) => sum + (Number(val) || 0), 0) / bEntries.length).toFixed(1)
        : behaviourScore.toFixed(1);

    // Safe risk data
    const riskData = (emp.riskData && typeof emp.riskData === 'object') ? emp.riskData : {
        overloadFreq: risk === 'High' ? 4 : risk === 'Medium' ? 2 : 1,
        escalationInvolvement: risk === 'High' ? 3 : risk === 'Medium' ? 1 : 0,
        perfDrop: risk === 'High' ? -6.8 : risk === 'Medium' ? -2.4 : 2.1,
    };

    // Safe promotion data
    const isEligible = perfScore >= 80 && risk !== 'High';
    const promotion = (emp.promotion && typeof emp.promotion === 'object') ? emp.promotion : {
        eligible: isEligible,
        aiVerdict: perfScore >= 88 ? 'Strongly Recommend' : perfScore >= 78 ? 'Recommend' : 'Not Recommended',
        managerReview: perfScore >= 85 ? 'Approved' : perfScore >= 75 ? 'Pending' : 'Hold',
        finalDecision: perfScore >= 88 ? 'Promoted' : perfScore >= 78 ? 'Pending' : 'Hold',
        lastReview: 'Sprint 24 Cycle Review',
        reviewedBy: 'Engineering Lead'
    };

    // Safe alignment history & sprint trend fallback
    const alignmentHistory = (Array.isArray(emp.alignmentHistory) && emp.alignmentHistory.length > 0)
        ? emp.alignmentHistory
        : [
            { sprint: 'S1', score: Math.min(100, Math.max(50, Math.round(perfScore - 7))) },
            { sprint: 'S2', score: Math.min(100, Math.max(50, Math.round(perfScore - 4))) },
            { sprint: 'S3', score: Math.min(100, Math.max(50, Math.round(perfScore - 2))) },
            { sprint: 'S4', score: Math.min(100, Math.max(50, Math.round(perfScore - 1))) },
            { sprint: 'S5', score: Math.min(100, Math.max(50, Math.round(perfScore + 1))) },
            { sprint: 'S6', score: Math.min(100, Math.max(50, Math.round(perfScore))) },
        ];

    const baseSp = parseInt(sprintContrib) || 18;
    const sprintTrend = (Array.isArray(emp.sprintTrend) && emp.sprintTrend.length > 0)
        ? emp.sprintTrend
        : [
            { sprint: 'S1', sp: Math.max(8, baseSp - 4) },
            { sprint: 'S2', sp: Math.max(10, baseSp - 2) },
            { sprint: 'S3', sp: Math.max(12, baseSp - 1) },
            { sprint: 'S4', sp: baseSp },
            { sprint: 'S5', sp: Math.max(10, baseSp - 1) },
            { sprint: 'S6', sp: baseSp },
        ];

    const managerComment = emp.managerComment || (
        perfScore >= 85
            ? 'Consistently delivers high-quality code and thorough reviews. Proactive collaborator across team milestones.'
            : perfScore >= 75
            ? 'Solid contributor with steady delivery. Focus is on continuing cross-functional coordination and velocity.'
            : 'Working actively with tech leads on structured velocity improvement and sprint milestone commitments.'
    );

    const handlePromotionAction = async (action) => {
        if (!emp) return;
        setSaving(true);
        const updatedPromotion = { ...promotion, finalDecision: action };
        try {
            await employeesAPI.update(emp.employee_id || id, { promotion: updatedPromotion });
        } catch (err) {
            console.error('Failed to update promotion:', err);
        } finally {
            setEmp(prev => ({ ...prev, promotion: updatedPromotion }));
            setSaving(false);
        }
    };

    const avatarText = emp.avatar || (emp.name ? emp.name.slice(0, 2).toUpperCase() : 'EM');

    return (
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
            {/* Back Button */}
            <button onClick={() => navigate('/employees')}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: '#fff', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem', marginBottom: 16, transition: 'all 0.15s ease' }}>
                <ArrowLeft size={16} /> Back to Employees
            </button>

            {/* Header Card */}
            <AnimatedCard delay={0}>
                <div className="card-body" style={{ display: 'flex', alignItems: 'center', gap: 24, padding: 30 }}>
                    <div style={{
                        width: 80, height: 80, borderRadius: '50%', background: 'var(--brand-gradient)',
                        color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '1.6rem', fontWeight: 800, flexShrink: 0
                    }}>{avatarText}</div>
                    <div style={{ flex: 1 }}>
                        <h2 style={{ fontSize: '1.4rem', fontWeight: 800, marginBottom: 4 }}>{emp.name}</h2>
                        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                            {emp.role} · {emp.dept} · Team: <strong>{emp.team_name || 'Core Engineering Squad'}</strong>
                        </p>
                        <div style={{ display: 'flex', gap: 8, marginTop: 10, flexWrap: 'wrap' }}>
                            <span className="badge" style={{ background: `${statusColors[status] || '#10b981'}20`, color: statusColors[status] || '#10b981', fontWeight: 600 }}>{status}</span>
                            <span className="badge" style={{ background: `${riskColors[risk] || '#10b981'}20`, color: riskColors[risk] || '#10b981', fontWeight: 600 }}>{risk} Risk</span>
                            <span className="badge badge-info">{sprintContrib}</span>
                            {emp.transferred_by && (
                                <span className="badge" style={{ background: '#10b98115', color: '#10b981', display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                    <ShieldCheck size={12} /> Reassigned by {emp.transferred_by}
                                </span>
                            )}
                        </div>
                    </div>
                    <div style={{ textAlign: 'right', display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 8 }}>
                        <div style={{ fontSize: '2rem', fontWeight: 800, color: getColor(perfScore) }}>{perfScore}%</div>
                        <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Overall Performance</div>
                        <button
                            className="btn btn-primary btn-sm"
                            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 4 }}
                            onClick={() => setShowTransferModal(true)}
                        >
                            <ArrowRightLeft size={13} /> Transfer Team
                        </button>
                    </div>
                </div>
            </AnimatedCard>

            {/* Contact Info */}
            <div className="grid-2 mt-lg">
                <AnimatedCard delay={0.08}>
                    <div className="card-header"><span className="card-title">Contact & Team Info</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Mail size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Email</div><div style={{ fontWeight: 600 }}>{emp.email}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Users size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Assigned Squad / Team</div><div style={{ fontWeight: 600 }}>{emp.team_name || 'Core Engineering Squad'}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Building size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Department</div><div style={{ fontWeight: 600 }}>{emp.dept}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Shield size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)' }}>Projects</div><div style={{ fontWeight: 600 }}>{Array.isArray(emp.projects) && emp.projects.length > 0 ? emp.projects.join(', ') : 'Samanvaya AI Platform'}</div></div></div>
                    </div>
                </AnimatedCard>

                {/* Quick Stats */}
                <AnimatedCard delay={0.14}>
                    <div className="card-header"><span className="card-title">Quick Stats</span></div>
                    <div className="card-body">
                        <StatRow icon={<TrendingUp size={16} color="#3b82f6" />} label="Alignment Score" value={`${alignment}%`} color={getColor(alignment)} />
                        <StatRow icon={<Clock size={16} color="#10b981" />} label="On-time Delivery" value={`${onTime}%`} color={getColor(onTime)} />
                        <StatRow icon={<AlertTriangle size={16} color="#ef4444" />} label="Rejection Rate" value={`${rejection}%`} color={rejection > 10 ? '#ef4444' : '#10b981'} />
                        <StatRow icon={<User size={16} color="#8b5cf6" />} label="Behaviour Score" value={`${behaviourScore}/10`} color={getColor(behaviourScore * 10)} />
                    </div>
                </AnimatedCard>
            </div>

            {/* Transfer Modal in Profile */}
            {showTransferModal && (
                <div style={{
                    position: 'fixed',
                    top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(15, 23, 42, 0.72)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    zIndex: 1000, backdropFilter: 'blur(4px)'
                }}>
                    <div style={{
                        background: '#ffffff',
                        border: '1px solid var(--border-color)',
                        borderRadius: 'var(--radius-md)',
                        width: '100%', maxWidth: 480, padding: 24,
                        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <ArrowRightLeft size={18} color="#3b82f6" />
                                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Transfer Team for {emp.name}</h3>
                            </div>
                            <button onClick={() => setShowTransferModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)' }}>
                                <X size={18} />
                            </button>
                        </div>

                        <form onSubmit={handleExecuteTransfer} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Reassign to Team *</label>
                                <select
                                    className="form-select"
                                    value={targetTeam}
                                    onChange={e => setTargetTeam(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                                >
                                    {teams.map(t => (
                                        <option key={t.team_id} value={t.team_id}>
                                            {t.name} ({t.dept || 'Engineering'})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Department *</label>
                                <select
                                    className="form-select"
                                    value={targetDept}
                                    onChange={e => setTargetDept(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)' }}
                                >
                                    <option value="Engineering">Engineering</option>
                                    <option value="Quality Assurance">Quality Assurance</option>
                                    <option value="Infrastructure & SRE">Infrastructure & SRE</option>
                                    <option value="Product">Product</option>
                                    <option value="Human Resources">Human Resources</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Reassignment Reason *</label>
                                <textarea
                                    className="form-input"
                                    rows={3}
                                    placeholder="Explain the team transfer rationale..."
                                    value={transferReason}
                                    onChange={e => setTransferReason(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}
                                />
                            </div>

                            <div style={{ background: '#3b82f610', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid #3b82f630' }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Transparent Audit Attribution:</div>
                                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#3b82f6', marginTop: 2 }}>
                                    Performed by: {user?.name ? `${user.name} (${user.role || 'HR'})` : 'Claire Underwood (HR)'}
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
                                <button type="button" className="btn btn-secondary" onClick={() => setShowTransferModal(false)}>Cancel</button>
                                <button type="submit" className="btn btn-primary" disabled={transferring} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Check size={14} /> {transferring ? 'Transferring...' : 'Confirm Transfer'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}


            {/* 📊 Performance Section */}
            <AnimatedCard delay={0.2} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <BarChart3 size={18} style={{ color: '#3b82f6' }} /> Performance Trends
                    </span>
                </div>
                <div className="card-body">
                    <div className="grid-2" style={{ gap: 20 }}>
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Alignment Score History</div>
                            <div style={{ height: 200 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={alignmentHistory}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                        <YAxis domain={[50, 100]} tick={{ fontSize: 11 }} />
                                        <Tooltip formatter={(v) => `${v}%`} />
                                        <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 4 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Sprint Contribution Trend</div>
                            <div style={{ height: 200 }}>
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={sprintTrend}>
                                        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                        <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} />
                                        <Tooltip formatter={(v) => `${v} SP`} />
                                        <Line type="monotone" dataKey="sp" stroke="#10b981" strokeWidth={2} dot={{ fill: '#10b981', r: 4 }} />
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>
                </div>
            </AnimatedCard>

            {/* 👤 Behaviour Section */}
            <AnimatedCard delay={0.28} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <User size={18} style={{ color: '#8b5cf6' }} /> Behaviour Assessment
                    </span>
                    <span className="badge" style={{ background: '#8b5cf620', color: '#8b5cf6' }}>Avg: {avgBehaviour}/10 · 10% Weight</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: 12, marginBottom: 16 }}>
                        {Object.entries(behaviourScores).map(([key, val]) => (
                            <div key={key} style={{ textAlign: 'center', padding: 16, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 8 }}>{key}</div>
                                <div style={{ fontWeight: 800, fontSize: '1.4rem', color: getColor(Number(val) * 10) }}>{val}</div>
                                <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginTop: 2 }}>/ 10</div>
                            </div>
                        ))}
                    </div>
                    <div style={{ padding: '14px 18px', background: '#faf5ff', borderRadius: 'var(--radius-sm)', border: '1px solid #e9d5ff' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontWeight: 600, fontSize: '0.82rem', color: '#7c3aed' }}>
                            <MessageSquare size={14} /> Manager Comments
                        </div>
                        <div style={{ fontSize: '0.85rem', lineHeight: 1.6, color: '#4c1d95' }}>{managerComment}</div>
                    </div>
                </div>
            </AnimatedCard>

            {/* 🚨 Risk Section */}
            <AnimatedCard delay={0.36} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <AlertTriangle size={18} style={{ color: '#ef4444' }} /> Risk Assessment
                    </span>
                    <span className="badge" style={{ background: `${riskColors[risk] || '#ef4444'}20`, color: riskColors[risk] || '#ef4444' }}>{risk} Risk</span>
                </div>
                <div className="card-body">
                    <StatRow icon={<Zap size={16} color="#f59e0b" />} label="Overload Frequency (last 3 sprints)" value={`${riskData.overloadFreq ?? 0} time(s)`} color={(riskData.overloadFreq ?? 0) > 3 ? '#ef4444' : '#10b981'} />
                    <StatRow icon={<AlertTriangle size={16} color="#ef4444" />} label="Escalation Involvement" value={`${riskData.escalationInvolvement ?? 0} escalation(s)`} color={(riskData.escalationInvolvement ?? 0) > 2 ? '#ef4444' : '#10b981'} />
                    <StatRow icon={<TrendingUp size={16} color={(riskData.perfDrop ?? 0) < 0 ? '#ef4444' : '#10b981'} />} label="Performance Change %" value={`${(riskData.perfDrop ?? 0) > 0 ? '+' : ''}${riskData.perfDrop ?? 0}%`} color={(riskData.perfDrop ?? 0) < 0 ? '#ef4444' : '#10b981'} />
                </div>
            </AnimatedCard>

            {/* 🏆 Promotion Section — from Promotion Recommendations */}
            <AnimatedCard delay={0.44} style={{ marginTop: 20, marginBottom: 20 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Award size={18} style={{ color: '#f59e0b' }} /> Promotion Status
                    </span>
                    <span className="badge" style={{ background: promotion.eligible ? '#10b98120' : '#ef444420', color: promotion.eligible ? '#10b981' : '#ef4444' }}>
                        {promotion.eligible ? '✓ Eligible' : '✗ Not Eligible'}
                    </span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 16, marginBottom: 20 }}>
                        <div style={{ padding: '16px 20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 6 }}>AI Verdict</div>
                            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: verdictColors[promotion.aiVerdict] || '#3b82f6' }}>{promotion.aiVerdict || 'Pending Evaluation'}</div>
                        </div>
                        <div style={{ padding: '16px 20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 6 }}>Manager Review</div>
                            <div style={{ fontWeight: 700, fontSize: '0.95rem', color: promotion.managerReview === 'Approved' ? '#10b981' : promotion.managerReview === 'Hold' ? '#ef4444' : '#f59e0b' }}>{promotion.managerReview || 'Pending'}</div>
                        </div>
                        <div style={{ padding: '16px 20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 6 }}>Decision</div>
                            <span className="badge" style={{ background: decisionColors[promotion.finalDecision] || '#94a3b8', color: '#fff', fontSize: '0.85rem', padding: '4px 14px' }}>{promotion.finalDecision || '—'}</span>
                        </div>
                    </div>

                    <StatRow icon={<Clock size={16} color="#6b7280" />} label="Last Review Date" value={promotion.lastReview || '—'} />
                    <StatRow icon={<User size={16} color="#3b82f6" />} label="Reviewed By" value={promotion.reviewedBy || '—'} />

                    {/* Action Buttons */}
                    {promotion.finalDecision !== 'Promoted' && (
                        <div style={{ marginTop: 16, display: 'flex', gap: 10 }}>
                            <button className="btn btn-sm btn-primary"
                                style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                disabled={saving}
                                onClick={() => handlePromotionAction('Pending')}>
                                {saving ? <Loader2 size={14} className="spin" /> : <Send size={14} />}
                                Send to Review
                            </button>
                            <button className="btn btn-sm"
                                style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#10b981', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', padding: '6px 14px', cursor: 'pointer', fontWeight: 600, opacity: saving ? 0.7 : 1 }}
                                disabled={saving}
                                onClick={() => handlePromotionAction('Promoted')}>
                                {saving ? <Loader2 size={14} className="spin" /> : <CheckCircle size={14} />}
                                Approve Promotion
                            </button>
                            <button className="btn btn-sm"
                                style={{ display: 'flex', alignItems: 'center', gap: 6, background: '#ef4444', color: '#fff', border: 'none', borderRadius: 'var(--radius-sm)', padding: '6px 14px', cursor: 'pointer', fontWeight: 600, opacity: saving ? 0.7 : 1 }}
                                disabled={saving}
                                onClick={() => handlePromotionAction('Hold')}>
                                {saving ? <Loader2 size={14} className="spin" /> : <PauseCircle size={14} />}
                                Hold
                            </button>
                        </div>
                    )}
                </div>
            </AnimatedCard>
        </div>
    );
}
