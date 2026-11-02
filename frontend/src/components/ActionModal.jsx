import { useState } from 'react';
import { X, Star, MessageSquare, AlertTriangle } from 'lucide-react';

const criteria = [
    { key: 'communication', label: 'Communication' },
    { key: 'ownership', label: 'Ownership' },
    { key: 'collaboration', label: 'Collaboration' },
    { key: 'leadership', label: 'Leadership' },
    { key: 'discipline', label: 'Discipline' },
];

/**
 * ActionModal
 * type: 'approve' | 'review' | 'reject'
 * onConfirm(data)
 * onClose
 */
export default function ActionModal({ type, storyTitle, onConfirm, onClose }) {
    const [ratings, setRatings] = useState({});
    const [comment, setComment] = useState('');
    const [changes, setChanges] = useState('');
    const [reason, setReason] = useState('');

    const configs = {
        approve: { title: 'Approve Story', icon: <span style={{ fontSize: '1.4rem' }}>✅</span>, color: '#10b981', bg: '#f0fdf4', border: '#a7f3d0' },
        'qa-approve': { title: 'Pass QA', icon: <span style={{ fontSize: '1.4rem' }}>✅</span>, color: '#10b981', bg: '#f0fdf4', border: '#a7f3d0' },
        review: { title: 'Request Changes', icon: <span style={{ fontSize: '1.4rem' }}>🔄</span>, color: '#3b82f6', bg: '#eff6ff', border: '#bfdbfe' },
        reject: { title: 'Reject Story', icon: <span style={{ fontSize: '1.4rem' }}>❌</span>, color: '#ef4444', bg: '#fef2f2', border: '#fecaca' },
    };

    const { title, icon, color, bg, border } = configs[type] || configs.approve;

    /* Behaviour score calc (HR style: avg of 1-5 ratings → /5 × 10) */
    const filledKeys = Object.keys(ratings);
    const avgRating = filledKeys.length > 0
        ? (filledKeys.reduce((s, k) => s + ratings[k], 0) / filledKeys.length)
        : null;
    const behaviourScore = avgRating !== null ? ((avgRating / 5) * 10).toFixed(1) : null;

    const canSubmit = () => {
        if (type === 'approve') return filledKeys.length === criteria.length;
        if (type === 'qa-approve') return true; // note is optional
        if (type === 'review') return changes.trim().length > 0;
        if (type === 'reject') return reason.trim().length > 0;
        return false;
    };

    const handleSubmit = () => {
        if (!canSubmit()) return;
        if (type === 'approve') onConfirm({ ratings, behaviourScore: +behaviourScore, comment });
        else if (type === 'qa-approve') onConfirm({ note: comment });
        else if (type === 'review') onConfirm({ changes });
        else if (type === 'reject') onConfirm({ reason });
    };

    const updateRating = (key, val) => setRatings(prev => ({ ...prev, [key]: val }));

    return (
        <div
            onClick={e => { if (e.target === e.currentTarget) onClose(); }}
            style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 2000, display: 'flex', alignItems: 'flex-start', justifyContent: 'center', padding: '24px 16px', overflowY: 'auto' }}
        >
            <div style={{ background: '#fff', borderRadius: 14, width: type === 'approve' ? 580 : 440, maxWidth: '100%', boxShadow: '0 24px 60px rgba(0,0,0,0.2)', overflow: 'hidden', marginTop: 20 }}>

                {/* Header */}
                <div style={{ padding: '18px 22px 16px', background: bg, borderBottom: `1px solid ${border}`, display: 'flex', alignItems: 'center', gap: 10 }}>
                    {icon}
                    <div style={{ flex: 1 }}>
                        <div style={{ fontWeight: 700, fontSize: '1rem', color }}>{title}</div>
                        <div style={{ fontSize: '0.78rem', color: '#6b7280', marginTop: 2 }}>{storyTitle}</div>
                    </div>
                    <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#9ca3af' }}><X size={18} /></button>
                </div>

                {/* Body */}
                <div style={{ padding: '20px 22px' }}>

                    {/* ── APPROVE: HR-style behaviour scoring ── */}
                    {type === 'approve' && (
                        <div>
                            <div style={{ fontWeight: 700, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 14 }}>
                                <Star size={15} color="#f59e0b" /> Rate Behaviour <span style={{ color: '#9ca3af', fontWeight: 400 }}>(1–5 scale, all criteria required)</span>
                            </div>

                            {/* Criteria cards */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 12, marginBottom: 16 }}>
                                {criteria.map(c => (
                                    <div key={c.key} style={{ padding: '14px', background: 'var(--bg-secondary, #f8fafc)', borderRadius: 10, border: `1px solid ${ratings[c.key] ? '#c4b5fd' : '#e5e7eb'}`, transition: 'border-color 0.2s' }}>
                                        <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 10, color: '#374151' }}>{c.label}</div>
                                        <div style={{ display: 'flex', gap: 6 }}>
                                            {[1, 2, 3, 4, 5].map(v => (
                                                <button key={v} onClick={() => updateRating(c.key, v)}
                                                    style={{
                                                        width: 32, height: 32, borderRadius: '50%',
                                                        border: `2px solid ${(ratings[c.key] || 0) >= v ? '#3b82f6' : '#e5e7eb'}`,
                                                        background: (ratings[c.key] || 0) >= v ? '#3b82f6' : '#fff',
                                                        color: (ratings[c.key] || 0) >= v ? '#fff' : '#6b7280',
                                                        fontWeight: 700, fontSize: '0.8rem', cursor: 'pointer', transition: 'all 0.15s ease',
                                                    }}>{v}</button>
                                            ))}
                                        </div>
                                    </div>
                                ))}
                            </div>

                            {/* Auto-calculated score banner */}
                            <div style={{ padding: '14px 18px', background: 'linear-gradient(135deg, #ede9fe, #f5f3ff)', borderRadius: 10, border: '1px solid #c4b5fd', display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                                <div>
                                    <div style={{ fontSize: '0.72rem', color: '#6d28d9', textTransform: 'uppercase', letterSpacing: '0.8px', fontWeight: 600 }}>Auto-Calculated</div>
                                    <div style={{ fontWeight: 700, fontSize: '0.88rem', marginTop: 3, color: '#4c1d95' }}>
                                        Behaviour Score = Avg({avgRating !== null ? avgRating.toFixed(1) : '—'}/5) × 2 =&nbsp;
                                        <span style={{ color: '#7c3aed', fontSize: '1.15rem' }}>
                                            {behaviourScore !== null ? `${behaviourScore}/10` : '—'}
                                        </span>
                                    </div>
                                </div>
                                {behaviourScore !== null && (
                                    <div style={{ width: 52, height: 52, borderRadius: '50%', background: '#7c3aed', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '1rem' }}>
                                        {behaviourScore}
                                    </div>
                                )}
                            </div>

                            {/* Comment */}
                            <textarea
                                placeholder="Add notes about this member's behaviour on this story (optional)…"
                                value={comment}
                                onChange={e => setComment(e.target.value)}
                                rows={3}
                                style={{ width: '100%', padding: '10px 12px', border: '1px solid #e5e7eb', borderRadius: 8, fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.5 }}
                            />
                        </div>
                    )}

                    {/* ── REVIEW: Required changes ── */}
                    {type === 'review' && (
                        <div>
                            <label style={{ fontWeight: 600, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                                <MessageSquare size={15} color="#3b82f6" /> Describe the required changes
                            </label>
                            <textarea
                                value={changes}
                                onChange={e => setChanges(e.target.value)}
                                placeholder="Explain what changes are needed before this can be approved…"
                                rows={5}
                                style={{ width: '100%', padding: '10px 12px', border: `1px solid ${changes.length > 0 ? '#bfdbfe' : '#e5e7eb'}`, borderRadius: 8, fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.5, outline: 'none' }}
                            />
                            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 4 }}>{changes.length} characters</p>
                        </div>
                    )}

                    {/* ── REJECT: Reason ── */}
                    {type === 'reject' && (
                        <div>
                            <label style={{ fontWeight: 600, fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10 }}>
                                <AlertTriangle size={15} color="#ef4444" /> Reason for rejection
                            </label>
                            <textarea
                                value={reason}
                                onChange={e => setReason(e.target.value)}
                                placeholder="State the reason why this story is being rejected…"
                                rows={5}
                                style={{ width: '100%', padding: '10px 12px', border: `1px solid ${reason.length > 0 ? '#fecaca' : '#e5e7eb'}`, borderRadius: 8, fontSize: '0.85rem', resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.5, outline: 'none' }}
                            />
                            <p style={{ fontSize: '0.75rem', color: '#9ca3af', marginTop: 4 }}>{reason.length} characters</p>
                        </div>
                    )}
                </div>

                {/* Footer */}
                <div style={{ padding: '14px 22px 20px', display: 'flex', gap: 10, justifyContent: 'flex-end', borderTop: '1px solid #f3f4f6' }}>
                    <button onClick={onClose}
                        style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer' }}>
                        Cancel
                    </button>
                    <button onClick={handleSubmit} disabled={!canSubmit()}
                        style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: canSubmit() ? color : '#d1d5db', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: canSubmit() ? 'pointer' : 'default', transition: 'background 0.15s' }}>
                        Confirm {title}
                    </button>
                </div>
            </div>
        </div>
    );
}
