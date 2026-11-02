import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import ActionModal from '../../components/ActionModal';
import { Inbox, AlertTriangle, CheckCircle, Cpu } from 'lucide-react';
import { pmAPI } from '../../services/api';

const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';
const leadBadgeStyle = (val) => ({
    background: val === 'Approved' ? '#10b98120' : val === 'Rejected' ? '#ef444420' : '#f59e0b20',
    color: val === 'Approved' ? '#10b981' : val === 'Rejected' ? '#ef4444' : '#f59e0b',
});

export default function PMReviewQueue() {
    const [data, setData] = useState([]);
    const [modal, setModal] = useState(null); // { type, id, taskTitle }
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        pmAPI.reviewQueue()
            .then(d => { if (d?.length) setData(d); })
            .catch(err => console.error('Failed to fetch PM Review Queue:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading review queue...</div>;

    const avgAlignment = data.length ? Math.round(data.reduce((a, q) => a + q.alignment, 0) / data.length) : 0;


    const handleConfirm = (actionData) => {
        const { type, id } = modal;
        const statusMap = { approve: 'Approved', review: 'Revision', reject: 'Rejected' };
        const newStatus = statusMap[type];
        setData(prev => prev.map(q => q.id === id
            ? { ...q, leadApproval: newStatus, actionData }
            : q
        ));
        pmAPI.updateReviewItem(id, { action: type, leadApproval: newStatus, ...actionData }).catch(err => console.error('Failed to update review item:', err));
        setModal(null);
    };

    return (
        <div>
            {modal && (
                <ActionModal
                    type={modal.type}
                    storyTitle={modal.taskTitle}
                    onConfirm={handleConfirm}
                    onClose={() => setModal(null)}
                />
            )}

            <div className="stats-grid mb-lg">
                <StatsCard icon={<Inbox size={24} />} value={data.length} label="Pending Reviews" color="orange" delay={0} />
                <StatsCard icon={<AlertTriangle size={24} />} value={data.filter(q => q.risk === 'High').length} label="High Risk Items" color="red" delay={0.08} />
                <StatsCard icon={<CheckCircle size={24} />} value={data.filter(q => q.leadApproval === 'Approved').length} label="Lead Approved" color="green" delay={0.16} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="purple" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Review Queue</span>
                    <span className="badge badge-info">{data.length} items</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Task</th><th>Submitted By</th><th>Alignment Score</th>
                                    <th>Lead Approval</th><th>Delay (Hrs)</th><th>Risk</th><th>AI Comment</th><th>Action</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map(q => (
                                    <tr key={q.id}>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{q.task}</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{q.id}</div>
                                        </td>
                                        <td style={{ fontSize: '0.85rem' }}>{q.submittedBy}</td>
                                        <td><span style={{ fontWeight: 700, color: getColor(q.alignment) }}>{q.alignment}%</span></td>
                                        <td><span className="badge" style={leadBadgeStyle(q.leadApproval)}>{q.leadApproval}</span></td>
                                        <td>{q.delay > 0 ? <span style={{ color: '#ef4444', fontWeight: 700 }}>{q.delay}h</span> : <span style={{ color: '#10b981' }}>—</span>}</td>
                                        <td><span className="badge" style={{ background: riskColors[q.risk], color: '#fff' }}>{q.risk}</span></td>
                                        <td>
                                            <div style={{ fontSize: '0.78rem', color: '#4c1d95', background: '#f5f3ff', padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid #e9d5ff', maxWidth: 220 }}>
                                                <Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />{q.aiComment}
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 4 }}>
                                                <button title="Approve"
                                                    onClick={() => setModal({ type: 'approve', id: q.id, taskTitle: q.task })}
                                                    style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#10b98120', color: '#10b981', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                    Approve ✓
                                                </button>
                                                <button title="Request Changes"
                                                    onClick={() => setModal({ type: 'review', id: q.id, taskTitle: q.task })}
                                                    style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#3b82f620', color: '#3b82f6', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                    Changes
                                                </button>
                                                <button title="Reject"
                                                    onClick={() => setModal({ type: 'reject', id: q.id, taskTitle: q.task })}
                                                    style={{ padding: '4px 10px', borderRadius: 6, border: 'none', background: '#ef444420', color: '#ef4444', fontWeight: 700, fontSize: '0.75rem', cursor: 'pointer' }}>
                                                    Reject
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
