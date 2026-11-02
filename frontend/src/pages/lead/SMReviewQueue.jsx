import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import ActionModal from '../../components/ActionModal';
import { Inbox, CheckCircle, AlertTriangle, MessageSquare } from 'lucide-react';
import { leadAPI, tasksAPI } from '../../services/api';

const statusColors = { Pending: '#f59e0b', Approved: '#10b981', 'Changes Requested': '#3b82f6', 'Escalated to PM': '#8b5cf6', Rejected: '#ef4444' };
const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const alignColor = v => v >= 80 ? '#10b981' : v >= 65 ? '#f59e0b' : '#ef4444';

export default function SMReviewQueue() {
    const [reviews, setReviews] = useState([]);
    const [loading, setLoading] = useState(true);
    const [expandedNote, setExpandedNote] = useState(null);
    const [modal, setModal] = useState(null);

    useEffect(() => {
        leadAPI.reviewQueue().then(data => { if (data?.length) setReviews(data); })
            .catch(err => console.error('Failed to fetch review queue:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading review queue...</div>;


    const handleConfirm = (data) => {
        const { type, id } = modal;
        const statusMap = { approve: 'Approved', review: 'Changes Requested', reject: 'Rejected' };
        const newStatus = statusMap[type];
        setReviews(prev => prev.map(r => r.id === id ? { ...r, status: newStatus, actionData: data } : r));
        leadAPI.updateReviewItem(id, { status: newStatus, actionData: data }).catch(err => console.error('Failed to update review item:', err));

        // Also sync task-level approval
        if (type === 'approve') {
            tasksAPI.approve(id, { approvedBy: 'Lead', approvalNotes: data?.notes || '' }).catch(() => { });
        } else if (type === 'reject') {
            tasksAPI.reject(id, { rejectedBy: 'Lead', rejectionNotes: data?.notes || '' }).catch(() => { });
        }

        setModal(null);
    };

    return (
        <div>
            {modal && (
                <ActionModal
                    type={modal.type}
                    storyTitle={modal.storyTitle}
                    onConfirm={handleConfirm}
                    onClose={() => setModal(null)}
                />
            )}

            <div className="stats-grid mb-lg">
                <StatsCard icon={<Inbox size={24} />} value={reviews.filter(r => r.status === 'Pending').length} label="Pending Review" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={reviews.filter(r => r.status === 'Approved').length} label="Approved" color="green" delay={0.08} />
                <StatsCard icon={<MessageSquare size={24} />} value={reviews.filter(r => r.status === 'Changes Requested').length} label="Changes Requested" color="orange" delay={0.16} />
                <StatsCard icon={<AlertTriangle size={24} />} value={reviews.filter(r => r.status === 'Escalated to PM').length} label="Escalated to PM" color="purple" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header"><span className="card-title">Review Queue</span></div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>ID</th><th>Story</th><th>Developer</th><th>AI Align</th><th>Risk</th><th>Submitted</th><th>Status</th><th>Actions</th></tr>
                            </thead>
                            <tbody>
                                {reviews.map(r => (
                                    <>
                                        <tr key={r.id}>
                                            <td style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.8rem', color: '#3b82f6' }}>{r.id}</td>
                                            <td style={{ fontWeight: 600 }}>
                                                {r.story}
                                                <button onClick={() => setExpandedNote(expandedNote === r.id ? null : r.id)}
                                                    style={{ marginLeft: 8, background: 'none', border: 'none', cursor: 'pointer', color: '#3b82f6', fontSize: '0.72rem', fontWeight: 600 }}>
                                                    {expandedNote === r.id ? '▲ AI' : '▼ AI'}
                                                </button>
                                            </td>
                                            <td style={{ fontSize: '0.82rem' }}>{r.developer}</td>
                                            <td><span style={{ fontWeight: 700, color: alignColor(r.alignment) }}>{r.alignment}%</span></td>
                                            <td><span style={{ color: riskColors[r.risk], fontWeight: 600 }}>{r.risk}</span></td>
                                            <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>{r.submittedAt}</td>
                                            <td><span className="badge" style={{ background: (statusColors[r.status] || '#6b7280') + '20', color: statusColors[r.status] || '#6b7280' }}>{r.status}</span></td>
                                            <td>
                                                <div style={{ display: 'flex', gap: 6 }}>
                                                    <button onClick={() => setModal({ type: 'approve', id: r.id, storyTitle: r.story })}
                                                        style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#10b98120', color: '#10b981', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                        Approve ✓
                                                    </button>
                                                    <button onClick={() => setModal({ type: 'review', id: r.id, storyTitle: r.story })}
                                                        style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#3b82f620', color: '#3b82f6', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                        Changes
                                                    </button>
                                                    <button onClick={() => setModal({ type: 'reject', id: r.id, storyTitle: r.story })}
                                                        style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#ef444420', color: '#ef4444', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                        Reject
                                                    </button>
                                                </div>
                                            </td>
                                        </tr>
                                        {expandedNote === r.id && (
                                            <tr key={`${r.id}-note`}>
                                                <td colSpan={8} style={{ padding: '0 16px 14px', background: '#fafafa' }}>
                                                    <div style={{ padding: '10px 14px', background: r.alignment < 65 ? '#fef2f2' : '#f0fdf4', borderRadius: 8, borderLeft: `3px solid ${alignColor(r.alignment)}`, fontSize: '0.83rem' }}>
                                                        <span style={{ fontWeight: 700, color: alignColor(r.alignment) }}>🤖 AI Suggestion: </span>{r.aiNote}
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
