import { useState, useRef, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { employeesAPI, usersAPI } from '../../services/api';
import { ROLE_LABELS } from '../../data/navigation';
import AnimatedCard from '../../components/AnimatedCard';
import { Mail, Building, Shield, Phone, BarChart3, TrendingUp, AlertTriangle, Award, User, MessageSquare, Zap, Clock, Eye, EyeOff, Copy, Check, Fingerprint, Camera } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

function Github({ size = 18, color = 'currentColor', style = {} }) {
    return (
        <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}>
            <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
            <path d="M9 18c-4.51 2-5-2-7-2" />
        </svg>
    );
}

const getColor = (s) => s >= 80 ? '#10b981' : s >= 60 ? '#f59e0b' : '#ef4444';

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

export default function ProfilePage() {
    const { user } = useAuth();
    const isCEO = user?.role === 'CEO';
    const showPAT = user?.role === 'DEVELOPER' || user?.role === 'DEVOPS';

    const [profileImg, setProfileImg] = useState(null);
    const [loading, setLoading] = useState(true);
    const [profileData, setProfileData] = useState(null);
    const fileInputRef = useRef(null);

    // GitHub PAT states
    const [pat, setPat] = useState('');
    const [patEditing, setPatEditing] = useState(false);
    const [patVisible, setPatVisible] = useState(false);
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (!user?.employee_id) return;

        employeesAPI.getById(user.employee_id)
            .then(data => {
                setProfileData(data);
                if (data.avatar) setProfileImg(data.avatar);
                if (data.github_pat) setPat(data.github_pat);
            })
            .catch(err => console.error('Failed to fetch profile:', err))
            .finally(() => setLoading(false));
    }, [user?.employee_id]);

    if (loading) {
        return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading profile...</div>;
    }

    // Use fetched data or defaults if missing
    const metrics = {
        alignment: profileData?.alignment || 0,
        onTime: profileData?.onTime || 0,
        rejection: profileData?.rejection || 0
    };
    const behavior = profileData?.behaviourScores || { communication: 0, ownership: 0, teamwork: 0, leadership: 0, discipline: 0, managerComment: 'No comments yet.' };
    const risk = profileData?.riskData || { overloadFreq: 0, escalationInvolvement: 0, perfDrop: 0 };
    const promo = profileData?.promotion || { eligible: false, aiRecommendation: 'None', lastReview: '—' };
    const history = profileData?.alignmentHistory || [];
    const trend = profileData?.sprintTrend || [];

    const handleImageChange = (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            const base64 = ev.target.result;
            setProfileImg(base64);
            // Persist to database
            if (user?.employee_id) {
                employeesAPI.update(user.employee_id, { avatar: base64 })
                    .catch(err => console.error('Failed to save avatar:', err));
            }
        };
        reader.readAsDataURL(file);
    };

    const handleCopy = () => {
        if (!pat) return;
        navigator.clipboard.writeText(pat);
        setCopied(true);
        setTimeout(() => setCopied(false), 1800);
    };

    const handleSavePat = () => {
        if (!user?.employee_id) return;
        usersAPI.updatePAT(user.employee_id, pat)
            .then(() => {
                setPatEditing(false);
                setPatVisible(false);
            })
            .catch(err => {
                console.error('Failed to save PAT:', err);
                alert('Failed to save GitHub PAT. Please try again.');
            });
    };

    return (
        <div style={{ maxWidth: 1000, margin: '0 auto' }}>
            {/* Header Card */}
            <AnimatedCard delay={0}>
                <div className="card-body" style={{ textAlign: 'center', padding: '48px 24px 24px' }}>
                    {/* Hidden file input */}
                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="image/*"
                        style={{ display: 'none' }}
                        onChange={handleImageChange}
                    />

                    {/* Avatar / profile image with camera button overlay */}
                    <div style={{ position: 'relative', width: 96, height: 96, margin: '0 auto 16px' }}>
                        {profileImg ? (
                            <img
                                src={profileImg}
                                alt="Profile"
                                style={{ width: 96, height: 96, borderRadius: '50%', objectFit: 'cover', border: '3px solid var(--brand-primary)' }}
                            />
                        ) : (
                            <div style={{
                                width: 96, height: 96, borderRadius: '50%', background: 'var(--brand-gradient)',
                                color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center',
                                fontSize: '1.8rem', fontWeight: 800,
                            }}>{user?.avatar}</div>
                        )}
                        {/* Camera button */}
                        <button
                            onClick={() => fileInputRef.current?.click()}
                            title="Edit profile photo"
                            style={{
                                position: 'absolute', bottom: 2, right: 2,
                                width: 28, height: 28, borderRadius: '50%',
                                background: 'var(--brand-primary)', border: '2px solid #fff',
                                display: 'flex', alignItems: 'center', justifyContent: 'center',
                                cursor: 'pointer', boxShadow: '0 2px 6px rgba(0,0,0,0.25)',
                                transition: 'transform 0.15s ease',
                            }}
                            onMouseEnter={e => e.currentTarget.style.transform = 'scale(1.12)'}
                            onMouseLeave={e => e.currentTarget.style.transform = 'scale(1)'}
                        >
                            <Camera size={13} color="#fff" />
                        </button>
                    </div>

                    <h2 style={{ fontSize: '1.5rem', fontWeight: 800 }}>{user?.name}</h2>
                    <p style={{ color: 'var(--text-secondary)', marginTop: 4 }}>{ROLE_LABELS[user?.role] || user?.role}</p>
                </div>
            </AnimatedCard>

            {/* Contact Info (always shown) + Activity (hidden for CEO) */}
            <div className={isCEO ? 'mt-lg' : 'grid-2 mt-lg'}>
                <AnimatedCard delay={0.1}>
                    <div className="card-header"><span className="card-title">Contact Info</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                        {/* Employee ID — all roles */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                            <Fingerprint size={18} color="var(--text-tertiary)" />
                            <div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Employee ID</div>
                                <div style={{ fontWeight: 700, fontFamily: 'monospace', letterSpacing: '0.5px' }}>
                                    {user?.id}
                                </div>
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Mail size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Email</div><div style={{ fontWeight: 600 }}>{user?.email}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Building size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Department</div><div style={{ fontWeight: 600 }}>{user?.department}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Shield size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Role</div><div style={{ fontWeight: 600 }}>{user?.role}</div></div></div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}><Phone size={18} color="var(--text-tertiary)" /><div><div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Phone</div><div style={{ fontWeight: 600 }}>{user?.phone || '—'}</div></div></div>

                        {/* GitHub PAT — DEVELOPER & DEVOPS only */}
                        {showPAT && (
                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
                                <Github size={18} color="var(--text-tertiary)" style={{ marginTop: 3 }} />
                                <div style={{ flex: 1 }}>
                                    <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>GitHub PAT</div>
                                    {patEditing ? (
                                        <div style={{ display: 'flex', gap: 6 }}>
                                            <input
                                                autoFocus
                                                value={pat}
                                                onChange={e => setPat(e.target.value)}
                                                placeholder="ghp_..."
                                                style={{ flex: 1, padding: '5px 10px', borderRadius: 6, border: '1px solid #3b82f6', fontFamily: 'monospace', fontSize: '0.78rem' }}
                                            />
                                            <button onClick={handleSavePat}
                                                style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                Save
                                            </button>
                                            <button onClick={() => setPatEditing(false)}
                                                style={{ padding: '4px 10px', borderRadius: 6, border: '1px solid #d1d5db', background: '#fff', color: '#374151', fontWeight: 600, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                Cancel
                                            </button>
                                        </div>
                                    ) : (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span style={{ fontFamily: 'monospace', fontWeight: 600, fontSize: '0.82rem', letterSpacing: patVisible ? 0 : '2px', color: 'var(--text-primary)' }}>
                                                {patVisible ? pat : '•'.repeat(Math.min(pat.length, 32))}
                                            </span>
                                            <button onClick={() => setPatVisible(v => !v)} title={patVisible ? 'Hide' : 'Show'}
                                                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
                                                {patVisible ? <EyeOff size={14} color="#6b7280" /> : <Eye size={14} color="#6b7280" />}
                                            </button>
                                            <button onClick={handleCopy} title="Copy" style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2 }}>
                                                {copied ? <Check size={14} color="#10b981" /> : <Copy size={14} color="#6b7280" />}
                                            </button>
                                            <button onClick={() => setPatEditing(true)}
                                                style={{ fontSize: '0.7rem', padding: '2px 8px', borderRadius: 5, border: '1px solid #e5e7eb', background: '#f9fafb', cursor: 'pointer', fontWeight: 600, color: '#374151' }}>
                                                Edit
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </AnimatedCard>

                {!isCEO && (
                    <AnimatedCard delay={0.15}>
                        <div className="card-header"><span className="card-title">Activity</span></div>
                        <div className="card-body">
                            <div className="timeline">
                                <div className="timeline-item"><div className="timeline-item-title">Logged in</div><div className="timeline-item-time">Just now</div></div>
                                <div className="timeline-item"><div className="timeline-item-title">Updated profile settings</div><div className="timeline-item-time">2 days ago</div></div>
                                <div className="timeline-item"><div className="timeline-item-title">Completed security training</div><div className="timeline-item-time">1 week ago</div></div>
                                <div className="timeline-item"><div className="timeline-item-title">Joined Samanvaya</div><div className="timeline-item-time">3 months ago</div></div>
                            </div>
                        </div>
                    </AnimatedCard>
                )}
            </div>

            {/* Everything below is hidden for CEO – CEO only sees Contact Info */}
            {!isCEO && (
                <>
                    {/* 📊 Performance Section */}
                    <AnimatedCard delay={0.2} style={{ marginTop: 20 }}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <BarChart3 size={18} style={{ color: '#3b82f6' }} /> Performance
                            </span>
                        </div>
                        <div className="card-body">
                            <StatRow icon={<TrendingUp size={16} color="#3b82f6" />} label="Current Alignment Score" value={`${metrics.alignment}%`} color={getColor(metrics.alignment)} />
                            <StatRow icon={<Clock size={16} color="#10b981" />} label="On-time Delivery %" value={`${metrics.onTime}%`} color={getColor(metrics.onTime)} />
                            <StatRow icon={<AlertTriangle size={16} color="#ef4444" />} label="Rejection Rate" value={`${metrics.rejection}%`} color={metrics.rejection > 10 ? '#ef4444' : '#10b981'} />

                            <div className="grid-2" style={{ marginTop: 20, gap: 16 }}>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Alignment Score History</div>
                                    <div style={{ height: 180 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={history}>
                                                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                                <XAxis dataKey="sprint" tick={{ fontSize: 11 }} />
                                                <YAxis domain={[60, 100]} tick={{ fontSize: 11 }} />
                                                <Tooltip formatter={(v) => `${v}%`} />
                                                <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2} dot={{ fill: '#3b82f6', r: 4 }} />
                                            </LineChart>
                                        </ResponsiveContainer>
                                    </div>
                                </div>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Sprint Contribution Trend</div>
                                    <div style={{ height: 180 }}>
                                        <ResponsiveContainer width="100%" height="100%">
                                            <LineChart data={trend}>
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
                                <User size={18} style={{ color: '#8b5cf6' }} /> Behaviour
                            </span>
                            <span className="badge" style={{ background: '#8b5cf620', color: '#8b5cf6' }}>10% Weight</span>
                        </div>
                        <div className="card-body">
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 16 }}>
                                {[
                                    { label: 'Communication', val: behavior.communication },
                                    { label: 'Ownership', val: behavior.ownership },
                                    { label: 'Teamwork', val: behavior.teamwork },
                                    { label: 'Leadership', val: behavior.leadership },
                                    { label: 'Discipline', val: behavior.discipline },
                                ].map(b => (
                                    <div key={b.label} style={{ textAlign: 'center', padding: '12px 8px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                        <div style={{ fontSize: '0.65rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }} title={b.label}>{b.label}</div>
                                        <div style={{ fontWeight: 800, fontSize: '1.1rem', color: getColor(b.val * 10) }}>{b.val}/10</div>
                                    </div>
                                ))}
                            </div>
                            <div style={{ padding: '14px 18px', background: '#faf5ff', borderRadius: 'var(--radius-sm)', border: '1px solid #e9d5ff' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6, fontWeight: 600, fontSize: '0.82rem', color: '#7c3aed' }}>
                                    <MessageSquare size={14} /> Manager Comments
                                </div>
                                <div style={{ fontSize: '0.85rem', lineHeight: 1.6, color: '#4c1d95' }}>{behavior.managerComment}</div>
                            </div>
                        </div>
                    </AnimatedCard>

                    {/* 🚨 Risk Section */}
                    <AnimatedCard delay={0.36} style={{ marginTop: 20 }}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <AlertTriangle size={18} style={{ color: '#ef4444' }} /> Risk Assessment
                            </span>
                        </div>
                        <div className="card-body">
                            <StatRow icon={<Zap size={16} color="#f59e0b" />} label="Overload Frequency (last 3 sprints)" value={`${risk.overloadFreq} times`} />
                            <StatRow icon={<AlertTriangle size={16} color="#ef4444" />} label="Escalation Involvement" value={`${risk.escalationInvolvement} escalation(s)`} />
                            <StatRow icon={<TrendingUp size={16} color={risk.perfDrop < 0 ? '#ef4444' : '#10b981'} />} label="Performance Change %" value={`${risk.perfDrop}%`} color={risk.perfDrop < 0 ? '#ef4444' : '#10b981'} />
                        </div>
                    </AnimatedCard>

                    {/* 🏆 Promotion Section */}
                    <AnimatedCard delay={0.44} style={{ marginTop: 20, marginBottom: 20 }}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Award size={18} style={{ color: '#f59e0b' }} /> Promotion
                            </span>
                        </div>
                        <div className="card-body">
                            <StatRow icon={<Shield size={16} color="#10b981" />} label="Eligibility Status" value={promo.eligible ? '✓ Eligible' : '✗ Not Eligible'} color={promo.eligible ? '#10b981' : '#ef4444'} />
                            <StatRow icon={<Zap size={16} color="#8b5cf6" />} label="AI Recommendation" value={promo.aiRecommendation} color={promo.aiRecommendation?.includes('Strongly') ? '#10b981' : '#3b82f6'} />
                            <StatRow icon={<Clock size={16} color="#6b7280" />} label="Last Review Date" value={promo.lastReview} />
                        </div>
                    </AnimatedCard>
                </>
            )}
        </div>
    );
}
