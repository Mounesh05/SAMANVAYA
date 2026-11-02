import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { CheckSquare, AlertTriangle, Clock, Cpu, X, GitBranch, MessageSquare } from 'lucide-react';
import { devAPI } from '../../services/api';

const priorityBadge = { High: 'badge-danger', Medium: 'badge-warning', Low: 'badge-success' };
const statusBadge = { 'In Progress': 'badge-info', 'To Do': 'badge-neutral', 'In Review': 'badge-warning', Done: 'badge-success', 'Changes Requested': 'badge-danger' };
const statusOpacity = { 'In Review': 0.55 };
const riskBadge = { Low: { bg: '#ecfdf5', color: '#10b981', label: '🟢 Low' }, Medium: { bg: '#fffbeb', color: '#f59e0b', label: '🟡 Medium' }, High: { bg: '#fef2f2', color: '#ef4444', label: '🔴 High' } };
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

export default function DevMyTasks() {
    const [tasks, setTasks] = useState([]);
    const [selected, setSelected] = useState(null);
    const [filter, setFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        devAPI.myTasks().then(data => { if (data?.length) setTasks(data); })
            .catch(err => console.error('Failed to fetch tasks:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading tasks...</div>;

    const filtered = filter === 'All' ? tasks : tasks.filter(t => t.status === filter);
    const avgAlignment = tasks.length ? Math.round(tasks.reduce((a, t) => a + t.alignment, 0) / tasks.length) : 0;

    const totalPoints = tasks.reduce((a, t) => a + t.points, 0);

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={tasks.length} label="Total Tasks" color="blue" delay={0} />
                <StatsCard icon={<AlertTriangle size={24} />} value={tasks.filter(t => t.risk === 'High').length} label="High Risk" color="red" delay={0.08} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="green" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={totalPoints} label="Total Story Points" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">My Tasks</span>
                    <div style={{ display: 'flex', gap: 6 }}>
                        {['All', 'To Do', 'In Progress', 'In Review', 'Changes Requested', 'Done'].map(s => (
                            <button key={s} onClick={() => setFilter(s)}
                                style={{
                                    padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                    background: filter === s ? 'var(--brand-primary)' : 'var(--bg-page)',
                                    color: filter === s ? '#fff' : 'var(--text-secondary)',
                                    border: filter === s ? 'none' : '1px solid var(--border-light)',
                                    transition: 'all 0.15s ease'
                                }}>{s}</button>
                        ))}
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Story</th><th>Sprint</th><th>Priority</th><th>Status</th>
                                    <th>Alignment</th><th>Due Date</th><th>Risk</th><th>Module</th><th>Points</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(t => (
                                    <tr key={t.id} onClick={() => setSelected(t)} style={{ cursor: 'pointer' }}>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.story}</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{t.id}</div>
                                        </td>
                                        <td style={{ fontSize: '0.82rem' }}>{t.sprint}</td>
                                        <td><span className={`badge ${priorityBadge[t.priority]}`}>{t.priority}</span></td>
                                        <td><span className={`badge ${statusBadge[t.status]}`} style={{ opacity: statusOpacity[t.status] || 1 }}>{t.status}</span></td>
                                        <td><span style={{ fontWeight: 700, color: getColor(t.alignment) }}>{t.alignment}%</span></td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{t.due}</td>
                                        <td>
                                            <span className="badge" style={{ background: (riskBadge[t.risk] || riskBadge.Low).bg, color: (riskBadge[t.risk] || riskBadge.Low).color }}>
                                                {(riskBadge[t.risk] || riskBadge.Low).label}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.82rem' }}>{t.module}</td>
                                        <td>
                                            <span style={{
                                                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                                width: 28, height: 28, borderRadius: '50%',
                                                background: 'var(--info-bg)', color: 'var(--info)',
                                                fontWeight: 700, fontSize: '0.8rem'
                                            }}>{t.points}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Detail Modal */}
            {selected && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    animation: 'fadeIn 0.2s ease'
                }} onClick={() => setSelected(null)}>
                    <div onClick={e => e.stopPropagation()} style={{
                        background: '#fff', borderRadius: 'var(--radius-lg)', width: '90%', maxWidth: 720,
                        maxHeight: '85vh', overflow: 'auto', boxShadow: 'var(--shadow-xl)',
                        animation: 'fadeInUp 0.3s ease'
                    }}>
                        {/* Modal Header */}
                        <div style={{
                            padding: '20px 24px', borderBottom: '1px solid var(--border-light)',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <div>
                                <div style={{ fontWeight: 800, fontSize: '1.1rem' }}>{selected.story}</div>
                                <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: 2 }}>{selected.id} · {selected.sprint} · {selected.points} pts</div>
                            </div>
                            <button onClick={() => setSelected(null)} style={{ cursor: 'pointer', background: 'var(--bg-page)', border: 'none', borderRadius: '50%', width: 32, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                <X size={16} />
                            </button>
                        </div>

                        {/* Mark as Done button */}
                        {(selected.status === 'In Progress' || selected.status === 'To Do' || selected.status === 'Changes Requested') && (
                            <div style={{ padding: '0 24px' }}>
                                <button
                                    onClick={async () => {
                                        try {
                                            const res = await devAPI.markDone(selected.id, { markedBy: 'Developer' });
                                            setTasks(prev => prev.map(t => t.id === selected.id ? { ...t, status: 'In Review', reviewedBy: 'AI Agent', reviewNotes: res?.review?.notes?.join(' | ') || '' } : t));
                                            setSelected(prev => ({ ...prev, status: 'In Review' }));
                                        } catch (err) {
                                            console.error('Mark done failed:', err);
                                        }
                                    }}
                                    style={{
                                        width: '100%', padding: '12px 20px', borderRadius: 'var(--radius-md)',
                                        border: 'none', background: 'linear-gradient(135deg, #10b981, #059669)',
                                        color: '#fff', fontWeight: 700, fontSize: '0.9rem', cursor: 'pointer',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                                        boxShadow: '0 4px 14px rgba(16,185,129,0.3)', transition: 'all 0.2s ease'
                                    }}
                                >
                                    ✓ Mark as Done — Submit for Review
                                </button>
                            </div>
                        )}
                        {selected.status === 'In Review' && (
                            <div style={{ padding: '0 24px' }}>
                                <div style={{
                                    padding: '12px 16px', borderRadius: 'var(--radius-md)',
                                    background: '#f59e0b15', border: '1px solid #f59e0b30',
                                    color: '#b45309', fontSize: '0.85rem', fontWeight: 600,
                                    display: 'flex', alignItems: 'center', gap: 8, opacity: 0.7
                                }}>
                                    ⏳ In Review — Awaiting Lead / PM approval
                                </div>
                            </div>
                        )}

                        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
                            {/* Description */}
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 6, color: 'var(--text-secondary)' }}>Description</div>
                                <div style={{ fontSize: '0.88rem', lineHeight: 1.7, color: 'var(--text-primary)' }}>{selected.description}</div>
                            </div>

                            {/* Acceptance Criteria */}
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 6, color: 'var(--text-secondary)' }}>Acceptance Criteria</div>
                                <ul style={{ paddingLeft: 18, display: 'flex', flexDirection: 'column', gap: 6 }}>
                                    {selected.acceptance.map((a, i) => (
                                        <li key={i} style={{ fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                                            <span style={{ color: 'var(--success)', marginRight: 6 }}>✓</span>{a}
                                        </li>
                                    ))}
                                </ul>
                            </div>

                            {/* Repo & Branch */}
                            <div style={{ display: 'flex', gap: 16 }}>
                                <div style={{ flex: 1, padding: '12px 16px', background: 'var(--bg-page)', borderRadius: 'var(--radius-sm)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>Linked Repo</div>
                                    <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{selected.repo}</div>
                                </div>
                                <div style={{ flex: 1, padding: '12px 16px', background: 'var(--bg-page)', borderRadius: 'var(--radius-sm)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginBottom: 4 }}>Branch</div>
                                    <div style={{ fontWeight: 600, fontSize: '0.88rem', fontFamily: "'Courier New', monospace", display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <GitBranch size={14} />{selected.branch}
                                    </div>
                                </div>
                            </div>

                            {/* AI Alignment Breakdown */}
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 10, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <Cpu size={14} /> AI Alignment Breakdown
                                </div>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                                    {[
                                        { label: 'Keyword Match', value: selected.aiBreakdown.keyword },
                                        { label: 'File Path Relevance', value: selected.aiBreakdown.filePath },
                                        { label: 'Semantic Similarity', value: selected.aiBreakdown.semantic },
                                        { label: 'Scope Drift', value: selected.aiBreakdown.scopeDrift, invert: true },
                                    ].map((m, i) => (
                                        <div key={i} style={{ padding: '10px 14px', background: '#f9fafb', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-light)' }}>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginBottom: 6 }}>{m.label}</div>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <div style={{ flex: 1, height: 6, borderRadius: 3, background: '#e5e7eb' }}>
                                                    <div style={{
                                                        height: '100%', borderRadius: 3,
                                                        width: `${m.value}%`,
                                                        background: m.invert
                                                            ? (m.value <= 10 ? '#10b981' : m.value <= 20 ? '#f59e0b' : '#ef4444')
                                                            : getColor(m.value),
                                                        transition: 'width 0.6s ease'
                                                    }} />
                                                </div>
                                                <span style={{
                                                    fontWeight: 700, fontSize: '0.82rem',
                                                    color: m.invert
                                                        ? (m.value <= 10 ? '#10b981' : m.value <= 20 ? '#f59e0b' : '#ef4444')
                                                        : getColor(m.value)
                                                }}>{m.value}%</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>

                            {/* Review Comments */}
                            <div>
                                <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 10, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                    <MessageSquare size={14} /> Review Comments ({selected.comments.length})
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                    {selected.comments.map((c, i) => (
                                        <div key={i} style={{
                                            padding: '10px 14px',
                                            background: c.author === 'AI Review' ? '#f5f3ff' : '#f9fafb',
                                            border: `1px solid ${c.author === 'AI Review' ? '#e9d5ff' : 'var(--border-light)'}`,
                                            borderRadius: 'var(--radius-sm)'
                                        }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                                <span style={{ fontWeight: 700, fontSize: '0.8rem', color: c.author === 'AI Review' ? '#7c3aed' : 'var(--text-primary)' }}>
                                                    {c.author === 'AI Review' && <Cpu size={11} style={{ display: 'inline', marginRight: 4 }} />}
                                                    {c.author}
                                                </span>
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{c.time}</span>
                                            </div>
                                            <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{c.text}</div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
