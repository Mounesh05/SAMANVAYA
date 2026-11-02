import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import ActionModal from '../../components/ActionModal';
import { CheckSquare, Clock, XCircle, CheckCircle, GitPullRequest, Bug, MessageSquare } from 'lucide-react';
import { qaAPI } from '../../services/api';
import ConfirmToast from '../../components/ConfirmToast';

const statusConfig = {
    Passed: { bg: '#ecfdf5', color: '#10b981' },
    Failed: { bg: '#fef2f2', color: '#ef4444' },
    Testing: { bg: '#eff6ff', color: '#3b82f6' },
    Pending: { bg: '#f3f4f6', color: '#6b7280' },
    Rejected: { bg: '#fef2f2', color: '#ef4444' },
};

const priorityConfig = {
    Critical: { bg: '#fef2f2', color: '#dc2626' },
    High: { bg: '#fff7ed', color: '#ea580c' },
    Medium: { bg: '#fffbeb', color: '#d97706' },
    Low: { bg: '#f0fdf4', color: '#16a34a' },
};

const getAlignColor = (v) => v >= 85 ? '#10b981' : v >= 70 ? '#f59e0b' : '#ef4444';

export default function QAAssignedStories() {
    const [data, setData] = useState([]);
    const [expanded, setExpanded] = useState(null);
    const [filter, setFilter] = useState('All');

    useEffect(() => {
        qaAPI.assignedStories().then(res => {
            if (Array.isArray(res)) setData(res);
        }).catch(() => { });
    }, []);
    const [modal, setModal] = useState(null); // { type: 'review'|'reject', id, storyTitle }

    const filters = ['All', 'Testing', 'Passed', 'Failed', 'Pending'];
    const filtered = filter === 'All' ? data : data.filter(s => s.testStatus === filter);

    /* Approve: confirm then persist */
    const [confirmApprove, setConfirmApprove] = useState(null);

    const handleApprove = (id) => {
        setConfirmApprove(id);
    };

    const handleConfirmApprove = () => {
        const id = confirmApprove;
        setConfirmApprove(null);
        setData(prev => prev.map(s => s.id === id ? { ...s, testStatus: 'Passed' } : s));
        qaAPI.updateAssignedStory(id, { testStatus: 'Passed' }).catch(err => console.error('Failed to update story:', err));
    };

    /* Bug / Reject: open modal, update on confirm */
    const handleConfirm = (actionData) => {
        const { type, id } = modal;
        const newStatus = type === 'review' ? 'Failed' : 'Rejected';
        setData(prev => prev.map(s => s.id === id ? { ...s, testStatus: newStatus, actionNote: actionData.changes || actionData.reason } : s));
        qaAPI.updateAssignedStory(id, { testStatus: newStatus, actionNote: actionData.changes || actionData.reason }).catch(err => console.error('Failed to update story:', err));
        setModal(null);
    };

    return (
        <div>
            {confirmApprove && (
                <ConfirmToast
                    message="Are you sure you want to mark this story as Passed?"
                    onConfirm={handleConfirmApprove}
                    onCancel={() => setConfirmApprove(null)}
                    variant="info"
                />
            )}
            {modal && (
                <ActionModal
                    type={modal.type}
                    storyTitle={modal.storyTitle}
                    onConfirm={handleConfirm}
                    onClose={() => setModal(null)}
                />
            )}

            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={data.length} label="Assigned Stories" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={data.filter(s => s.testStatus === 'Passed').length} label="Passed" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={data.filter(s => s.testStatus === 'Failed').length} label="Failed / Bug" color="red" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={data.filter(s => s.testStatus === 'Testing' || s.testStatus === 'Pending').length} label="In Progress / Pending" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Assigned Stories</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                        {filters.map(f => (
                            <button key={f} onClick={() => setFilter(f)} style={{
                                padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                background: filter === f ? 'var(--brand-primary)' : 'var(--bg-page)',
                                color: filter === f ? '#fff' : 'var(--text-secondary)',
                                border: filter === f ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s ease'
                            }}>{f}</button>
                        ))}
                    </div>
                </div>

                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Story</th><th>Developer</th><th>Build</th><th>Alignment</th>
                                    <th>Status</th><th>Priority</th><th>Deadline</th><th>Actions</th><th></th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(s => {
                                    const sc = statusConfig[s.testStatus] || statusConfig.Pending;
                                    const pc = priorityConfig[s.priority];
                                    return (
                                        <>
                                            <tr key={s.id} onClick={() => setExpanded(expanded === s.id ? null : s.id)} style={{ cursor: 'pointer' }}>
                                                <td style={{ fontWeight: 700, fontSize: '0.85rem' }}>{s.story}</td>
                                                <td style={{ fontSize: '0.82rem' }}>{s.developer}</td>
                                                <td><span style={{ fontFamily: "'Courier New', monospace", fontSize: '0.82rem', background: 'var(--bg-page)', padding: '2px 8px', borderRadius: 4 }}>{s.buildVersion}</span></td>
                                                <td>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <div style={{ width: 40, height: 5, borderRadius: 3, background: '#e5e7eb' }}>
                                                            <div style={{ height: '100%', borderRadius: 3, width: `${s.alignment}%`, background: getAlignColor(s.alignment) }} />
                                                        </div>
                                                        <span style={{ fontWeight: 700, fontSize: '0.78rem', color: getAlignColor(s.alignment) }}>{s.alignment}%</span>
                                                    </div>
                                                </td>
                                                <td><span className="badge" style={{ background: sc.bg, color: sc.color }}>{s.testStatus}</span></td>
                                                <td><span className="badge" style={{ background: pc.bg, color: pc.color }}>{s.priority}</span></td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{s.deadline}</td>

                                                {/* Action buttons — stop row click propagation */}
                                                <td onClick={e => e.stopPropagation()}>
                                                    <div style={{ display: 'flex', gap: 6 }}>
                                                        {/* Approve — direct */}
                                                        <button
                                                            onClick={() => handleApprove(s.id)}
                                                            title="Approve"
                                                            style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#10b98120', color: '#10b981', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                            <CheckCircle size={13} /> Pass
                                                        </button>

                                                        {/* Bug — asks for description */}
                                                        <button
                                                            onClick={() => setModal({ type: 'review', id: s.id, storyTitle: s.story })}
                                                            title="Raise Bug"
                                                            style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#f59e0b20', color: '#f59e0b', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                            <Bug size={13} /> Bug
                                                        </button>

                                                        {/* Reject — asks for reason */}
                                                        <button
                                                            onClick={() => setModal({ type: 'reject', id: s.id, storyTitle: s.story })}
                                                            title="Reject"
                                                            style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#ef444420', color: '#ef4444', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                            <XCircle size={13} /> Reject
                                                        </button>
                                                    </div>
                                                </td>

                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>{expanded === s.id ? '▲' : '▼'}</td>
                                            </tr>

                                            {/* Expandable detail row */}
                                            {expanded === s.id && (
                                                <tr key={`${s.id}-detail`}>
                                                    <td colSpan={9} style={{ padding: 0 }}>
                                                        <div style={{ padding: '16px 20px', background: 'var(--bg-page)', borderTop: '1px solid var(--border-light)' }}>
                                                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 16, marginBottom: 14 }}>
                                                                <div><span style={{ fontWeight: 700, fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Linked PR</span><div style={{ fontSize: '0.85rem', fontWeight: 600, marginTop: 4 }}><GitPullRequest size={13} style={{ display: 'inline', marginRight: 4 }} />{s.linkedPR}</div></div>
                                                                <div><span style={{ fontWeight: 700, fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Build Env</span><div style={{ fontSize: '0.85rem', fontWeight: 600, marginTop: 4 }}>{s.buildEnv}</div></div>
                                                                <div><span style={{ fontWeight: 700, fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Deadline</span><div style={{ fontSize: '0.85rem', fontWeight: 600, marginTop: 4 }}>{s.deadline}</div></div>
                                                            </div>
                                                            <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 8 }}>Acceptance Criteria</div>
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                                                                {s.acceptance.map((a, i) => (
                                                                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                                                        <CheckSquare size={13} style={{ color: '#10b981', flexShrink: 0 }} /> {a}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                            {/* Show action note if set */}
                                                            {s.actionNote && (
                                                                <div style={{ marginTop: 12, padding: '10px 14px', background: s.testStatus === 'Rejected' ? '#fef2f2' : '#fffbeb', borderRadius: 8, borderLeft: `3px solid ${s.testStatus === 'Rejected' ? '#ef4444' : '#f59e0b'}`, fontSize: '0.82rem' }}>
                                                                    <strong style={{ color: s.testStatus === 'Rejected' ? '#ef4444' : '#f59e0b' }}>
                                                                        {s.testStatus === 'Rejected' ? '❌ Rejection Reason: ' : '🐛 Bug Description: '}
                                                                    </strong>{s.actionNote}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
