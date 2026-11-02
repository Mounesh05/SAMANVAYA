import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { CheckSquare, UploadCloud, Server, Shield, Wrench, Cpu, CheckCircle, XCircle } from 'lucide-react';
import { devopsAPI } from '../../services/api';

const typeConfig = {
    'Deployment': { icon: <UploadCloud size={13} />, color: '#3b82f6' },
    'Infra Change': { icon: <Server size={13} />, color: '#8b5cf6' },
    'Monitoring Setup': { icon: <Wrench size={13} />, color: '#f59e0b' },
    'Security Patch': { icon: <Shield size={13} />, color: '#ef4444' },
};

const statusBadge = {
    'To Do': { bg: '#f3f4f6', color: '#6b7280' },
    'In Progress': { bg: '#eff6ff', color: '#3b82f6' },
    'In Review': { bg: '#fffbeb', color: '#f59e0b' },
    'Done': { bg: '#ecfdf5', color: '#10b981' },
};

const getAlignColor = (v) => v >= 85 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

export default function DevOpsTasksPage() {
    const [tasks, setTasks] = useState([]);
    const [expanded, setExpanded] = useState(null);
    const [filter, setFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    const loadTasks = async () => {
        try {
            setLoading(true);
            const data = await devopsAPI.tasks();
            if (Array.isArray(data)) {
                setTasks(data);
            }
        } catch (err) {
            console.error('Failed to load DevOps tasks', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadTasks();
    }, []);

    const types = ['All', 'Deployment', 'Infra Change', 'Monitoring Setup', 'Security Patch'];
    const filtered = filter === 'All' ? tasks : tasks.filter(t => t.type === filter);
    const doneCount = tasks.filter(t => t.status === 'Done').length;
    const alignedTasks = tasks.filter(t => (t.alignment || 0) > 0);
    const avgAlignment = alignedTasks.length
        ? Math.round(alignedTasks.reduce((a, t) => a + (t.alignment || 0), 0) / alignedTasks.length)
        : 0;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={tasks.length} label="Total Tasks" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={doneCount} label="Completed" color="green" delay={0.08} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="orange" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={tasks.filter(t => t.type === 'Security Patch').length} label="Security Patches" color="red" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">DevOps Tasks</span>
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        {types.map(t => (
                            <button
                                key={t}
                                onClick={() => setFilter(t)}
                                style={{
                                    padding: '4px 10px', borderRadius: 20, fontSize: '0.72rem', fontWeight: 600, cursor: 'pointer',
                                    background: filter === t ? 'var(--brand-primary)' : 'var(--bg-page)',
                                    color: filter === t ? '#fff' : 'var(--text-secondary)',
                                    border: filter === t ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s ease'
                                }}
                            >
                                {t}
                            </button>
                        ))}
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Story</th><th>Type</th><th>Environment</th><th>Status</th><th>Alignment</th><th></th><th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No DevOps tasks found matching "{filter}".
                                        </td>
                                    </tr>
                                )}
                                {filtered.map(t => {
                                    const tc = typeConfig[t.type] || {};
                                    const sb = statusBadge[t.status] || {};
                                    return (
                                        <tbody key={t.id || t._id}>
                                            <tr onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                                                style={{ cursor: 'pointer', transition: 'background 0.15s' }}>
                                                <td style={{ fontWeight: 700, fontSize: '0.85rem' }}>{t.story}</td>
                                                <td>
                                                    <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: tc.color, fontWeight: 600, fontSize: '0.82rem' }}>
                                                        {tc.icon} {t.type}
                                                    </span>
                                                </td>
                                                <td><span className="badge badge-neutral">{t.env}</span></td>
                                                <td><span className="badge" style={{ background: sb.bg, color: sb.color, opacity: t.status === 'In Review' ? 0.55 : 1 }}>{t.status}</span></td>
                                                <td>
                                                    {t.alignment > 0 ? (
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                            <div style={{ width: 50, height: 5, borderRadius: 3, background: '#e5e7eb' }}>
                                                                <div style={{ height: '100%', borderRadius: 3, width: `${t.alignment}%`, background: getAlignColor(t.alignment) }} />
                                                            </div>
                                                            <span style={{ fontWeight: 700, fontSize: '0.78rem', color: getAlignColor(t.alignment) }}>{t.alignment}%</span>
                                                        </div>
                                                    ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>}
                                                </td>
                                                <td style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>{expanded === t.id ? '▲' : '▼'}</td>
                                                <td>
                                                    {(t.status === 'In Progress' || t.status === 'To Do') && (
                                                        <button
                                                            onClick={async (e) => {
                                                                e.stopPropagation();
                                                                try {
                                                                    await devopsAPI.markDone(t.id, { markedBy: 'DevOps' });
                                                                    setTasks(prev => prev.map(task => task.id === t.id ? { ...task, status: 'In Review' } : task));
                                                                } catch (err) { console.error('Mark done failed:', err); }
                                                            }}
                                                            style={{
                                                                padding: '4px 10px', borderRadius: 6, border: 'none',
                                                                background: 'linear-gradient(135deg, #10b981, #059669)',
                                                                color: '#fff', fontWeight: 700, fontSize: '0.72rem',
                                                                cursor: 'pointer', whiteSpace: 'nowrap'
                                                            }}
                                                        >✓ Done</button>
                                                    )}
                                                    {t.status === 'In Review' && (
                                                        <span style={{ fontSize: '0.72rem', color: '#b45309', fontWeight: 600, opacity: 0.7 }}>⏳ Pending</span>
                                                    )}
                                                </td>
                                            </tr>
                                            {expanded === t.id && (
                                                <tr key={`${t.id}-detail`}>
                                                    <td colSpan={7} style={{ padding: 0 }}>
                                                        <div style={{ padding: '16px 20px', background: 'var(--bg-page)', borderTop: '1px solid var(--border-light)' }}>
                                                            <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 12 }}>AI Verification</div>
                                                            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 12 }}>
                                                                {[
                                                                    { label: 'CI logs aligned with task', ok: t.ciAligned },
                                                                    { label: 'Deployment triggered', ok: t.deployTriggered },
                                                                    { label: 'Correct files modified', ok: t.filesCorrect },
                                                                ].map((v, i) => (
                                                                    <div key={i} style={{
                                                                        display: 'flex', alignItems: 'center', gap: 6,
                                                                        padding: '6px 12px', borderRadius: 'var(--radius-sm)',
                                                                        background: v.ok ? '#ecfdf5' : '#fef2f2',
                                                                        fontSize: '0.82rem', fontWeight: 600,
                                                                        color: v.ok ? '#10b981' : '#ef4444'
                                                                    }}>
                                                                        {v.ok ? <CheckCircle size={14} /> : <XCircle size={14} />} {v.label}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                            {t.aiNote && (
                                                                <div style={{
                                                                    padding: '10px 14px', borderRadius: 'var(--radius-sm)',
                                                                    background: (t.alignment || 0) >= 85 ? 'var(--success-bg)' : 'var(--warning-bg)',
                                                                    borderLeft: `3px solid ${(t.alignment || 0) >= 85 ? 'var(--success)' : 'var(--warning)'}`,
                                                                    fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: 6
                                                                }}>
                                                                    <Cpu size={13} /> {t.aiNote}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
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
