import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
const BEHAVIOUR_KEYS = ['communication', 'ownership', 'teamwork', 'leadership', 'discipline'];

import { TrendingUp, Award, Star, Users, ThumbsUp, MessageCircle, Heart, Zap, Loader2 } from 'lucide-react';
import { ceoAPI, dashboardAPI } from '../../services/api';

const behaviourCriteria = [
    { key: 'communication', label: 'Communication', icon: <MessageCircle size={16} />, desc: 'Clarity, frequency, and effectiveness' },
    { key: 'ownership', label: 'Ownership', icon: <ThumbsUp size={16} />, desc: 'Takes responsibility and follows through' },
    { key: 'teamwork', label: 'Teamwork', icon: <Heart size={16} />, desc: 'Collaboration and support for peers' },
    { key: 'leadership', label: 'Leadership', icon: <Award size={16} />, desc: 'Guides others and shows initiative' },
    { key: 'discipline', label: 'Discipline', icon: <Zap size={16} />, desc: 'Consistency, reliability and standards' },
];

const getScoreColor = (score) => {
    if (score >= 85) return '#10b981';
    if (score >= 70) return '#f59e0b';
    return '#ef4444';
};

export default function PerformanceInsights() {
    const { user } = useAuth();
    const [members, setMembers] = useState([]);
    const [ratings, setRatings] = useState({});
    const [selectedMember, setSelectedMember] = useState('');
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [saveError, setSaveError] = useState(null);
    const [statusLog, setStatusLog] = useState('');
    const [notes, setNotes] = useState('');

    const loadMembers = () => {
        return ceoAPI.performanceMembers().then(data => {
            setMembers(data);
            return data;
        }).catch(() => { });
    };

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [membersData, statsData, feedbackList] = await Promise.all([
                    ceoAPI.performanceMembers(),
                    dashboardAPI.ceo(), // Reuse CEO dashboard stats for KPIs or add specialist endpoint if needed
                    ceoAPI.behaviourFeedback()
                ]);

                setMembers(membersData || []);
                if (membersData?.length) setSelectedMember(membersData[0].name);
                setStats(statsData);

                const initial = {};
                (feedbackList || []).forEach(f => {
                    initial[f.name] = {
                        communication: f.communication ?? 5,
                        ownership: f.ownership ?? 5,
                        teamwork: f.teamwork ?? 5,
                        leadership: f.leadership ?? 5,
                        discipline: f.discipline ?? 5,
                    };
                });
                setRatings(initial);
            } catch (err) {
                console.error('Failed to fetch performance insights data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    const updateRating = (criteria, value) => {
        setRatings(prev => ({
            ...prev,
            [selectedMember]: { ...(prev[selectedMember] || {}), [criteria]: value }
        }));
        setSaveError(null);
    };

    const handleSaveBehaviourScores = () => {
        const r = ratings[selectedMember] || {};
        const payload = {
            name: selectedMember,
            communication: r.communication ?? 5,
            ownership: r.ownership ?? 5,
            teamwork: r.teamwork ?? 5,
            leadership: r.leadership ?? 5,
            discipline: r.discipline ?? 5,
            notes: notes,
            assignedBy: user?.name || 'CEO',
        };
        setSaving(true);
        setSaveError(null);
        ceoAPI.saveBehaviourScores(payload)
            .then(res => {
                return loadMembers().then(updatedMembers => ({ res, updatedMembers }));
            })
            .then(({ res, updatedMembers }) => {
                setSaving(false);
                setSaved(true);
                setNotes('');
                setStatusLog(`Success: Behaviour scores for ${selectedMember} saved. Overall Index updated to ${res.overall}%`);
                setTimeout(() => setSaved(false), 5000);
            })
            .catch(err => {
                setSaving(false);
                setSaveError(err?.message || 'Failed to save behaviour scores');
                setStatusLog(`Error: ${err?.message || 'Save failed'}`);
            });
    };
    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading performance insights...</div>;
    }

    return (
        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<TrendingUp size={24} />} value="84.8%" label="Avg Performance" trend="+3.2%" trendDir="up" color="green" delay={0} />
                <StatsCard icon={<Award size={24} />} value={members.filter(m => m.promotion).length.toString()} label="Promotion Eligible" trend={`of ${members.length} members`} trendDir="up" color="blue" delay={0.08} />
                <StatsCard icon={<Star size={24} />} value={(members.reduce((a, b) => a + (b.behaviour || 0), 0) / (members.length || 1)).toFixed(1)} label="Avg Behaviour Score" trend="+0.4" trendDir="up" color="purple" delay={0.16} />
                <StatsCard icon={<Users size={24} />} value={(members.reduce((a, b) => a + (b.rejection || 0), 0) / (members.length || 1)).toFixed(1) + '%'} label="Avg Rejection Rate" trend="-2.1%" trendDir="down" color="orange" delay={0.24} />
            </div>

            {/* Member Performance Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Member Performance Table</span>
                    <span className="badge badge-info">10% Behaviour Weight</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Member</th>
                                    <th>Alignment Avg</th>
                                    <th>On-time %</th>
                                    <th>Rejection %</th>
                                    <th>Behaviour</th>
                                    <th>Overall Index</th>
                                    <th>Promotion</th>
                                </tr>
                            </thead>
                            <tbody>
                                {members.map(m => (
                                    <tr key={m.name}>
                                        <td>
                                            <div style={{ fontWeight: 600 }}>{m.name}</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{m.role}</div>
                                        </td>
                                        <td><span style={{ fontWeight: 700, color: getScoreColor(m.alignment) }}>{m.alignment}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: getScoreColor(m.onTime) }}>{m.onTime}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: m.rejection > 10 ? '#ef4444' : '#10b981' }}>{m.rejection}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: getScoreColor(m.behaviour * 10) }}>{m.behaviour}/10</span></td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ width: 50, height: 8, background: '#f0f0f0', borderRadius: 4, overflow: 'hidden' }}>
                                                    <div style={{ height: '100%', width: `${m.overall}%`, background: getScoreColor(m.overall), borderRadius: 4 }} />
                                                </div>
                                                <span style={{ fontWeight: 700, color: getScoreColor(m.overall) }}>{m.overall}%</span>
                                            </div>
                                        </td>
                                        <td>
                                            {m.promotion
                                                ? <span className="badge badge-success">✓ Eligible</span>
                                                : <span className="badge badge-danger">✗ Not Yet</span>
                                            }
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Behaviour Input Section */}
            <AnimatedCard delay={0.4} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title">Behaviour Input (10% Weight)</span>
                    <select
                        value={selectedMember}
                        onChange={e => setSelectedMember(e.target.value)}
                        style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem', background: '#fff' }}
                    >
                        {members.map(m => <option key={m.name} value={m.name}>{m.name}</option>)}
                    </select>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12 }}>
                        {behaviourCriteria.map(c => {
                            const val = ratings[selectedMember]?.[c.key] || 5;
                            return (
                                <div key={c.key} style={{
                                    padding: '12px 14px',
                                    background: 'var(--bg-secondary)',
                                    borderRadius: 'var(--radius-md)',
                                    border: '1px solid var(--border-color)',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    justifyContent: 'space-between',
                                    minHeight: '140px'
                                }}>
                                    <div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, fontWeight: 700, fontSize: '0.82rem' }}>
                                            {c.icon} {c.label}
                                        </div>
                                        <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', marginBottom: 12, height: '32px', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                                            {c.desc}
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <input
                                            type="range" min="1" max="10" value={val}
                                            onChange={e => updateRating(c.key, Number(e.target.value))}
                                            style={{ flex: 1, accentColor: '#3b82f6' }}
                                        />
                                        <span style={{ fontWeight: 800, fontSize: '0.95rem', color: getScoreColor(val * 10), minWidth: 32, textAlign: 'center' }}>{val}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div style={{ marginTop: 24 }}>
                        <div style={{ fontSize: '0.82rem', fontWeight: 700, marginBottom: 8, color: 'var(--text-secondary)' }}>Assessment Description / Notes</div>
                        <textarea
                            placeholder="Add specific observations about this member's behaviour this sprint..."
                            value={notes}
                            onChange={e => setNotes(e.target.value)}
                            style={{
                                width: '100%',
                                padding: '12px 16px',
                                borderRadius: 'var(--radius-sm)',
                                border: '1px solid var(--border-color)',
                                fontSize: '0.85rem',
                                minHeight: '100px',
                                background: '#fff',
                                resize: 'vertical'
                            }}
                        />
                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                            Logged in as: <strong>{user?.name || 'System'}</strong> (Assigned By)
                        </div>
                    </div>

                    <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 12 }}>
                        {saveError && <span style={{ color: '#ef4444', fontSize: '0.85rem' }}>{saveError}</span>}
                        <button
                            className={`btn ${saved ? 'btn-success' : 'btn-primary'} btn-sm`}
                            onClick={handleSaveBehaviourScores}
                            disabled={saving || saved}
                        >
                            {saving ? 'Saving…' : saved ? 'Saved!' : 'Save Behaviour Scores'}
                        </button>
                    </div>
                    {statusLog && (
                        <div style={{
                            marginTop: 16,
                            padding: '10px 14px',
                            background: statusLog.startsWith('Error') ? '#fef2f2' : '#f0fdf4',
                            borderRadius: 'var(--radius-sm)',
                            border: `1px solid ${statusLog.startsWith('Error') ? '#fee2e2' : '#dcfce7'}`,
                            fontSize: '0.82rem',
                            color: statusLog.startsWith('Error') ? '#b91c1c' : '#15803d',
                            fontWeight: 500
                        }}>
                            {statusLog}
                        </div>
                    )}
                </div>
            </AnimatedCard>
        </div>
    );
}
