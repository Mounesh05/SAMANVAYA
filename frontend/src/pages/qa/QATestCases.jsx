import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { FlaskConical, CheckCircle, Clock, XCircle, Plus, X, ChevronDown } from 'lucide-react';
import { qaAPI } from '../../services/api';


const statusCfg = {
    Passed: { bg: '#ecfdf5', color: '#10b981' },
    Failed: { bg: '#fef2f2', color: '#ef4444' },
    'In Progress': { bg: '#eff6ff', color: '#3b82f6' },
    Pending: { bg: '#f3f4f6', color: '#6b7280' },
};

const priorityCfg = {
    Critical: { color: '#dc2626' },
    High: { color: '#ea580c' },
    Medium: { color: '#d97706' },
    Low: { color: '#16a34a' },
};

const TYPES = ['Functional', 'Negative', 'Integration', 'Performance', 'Boundary', 'Regression', 'UI'];
const PRIORITIES = ['Critical', 'High', 'Medium', 'Low'];
const STATUSES = ['Pending', 'In Progress', 'Passed', 'Failed'];

const empty = { title: '', story: '', type: 'Functional', priority: 'Medium', status: 'Pending', steps: 1 };

export default function QATestCases() {
    const [cases, setCases] = useState([]);
    const [availableStories, setAvailableStories] = useState([]);
    const [filter, setFilter] = useState('All');
    const [showModal, setShowModal] = useState(false);
    const [form, setForm] = useState(empty);
    const [errors, setErrors] = useState({});

    useEffect(() => {
        qaAPI.testCases().then(data => { if (data?.length) setCases(data); }).catch(() => { });
        qaAPI.assignedStories().then(data => {
            if (Array.isArray(data) && data.length) {
                const titles = [...new Set(data.map(s => s.story || s.title).filter(Boolean))];
                setAvailableStories(titles);
            }
        }).catch(() => { });
    }, []);

    const filters = ['All', 'Passed', 'Failed', 'In Progress', 'Pending'];
    const filtered = filter === 'All' ? cases : cases.filter(c => c.status === filter);

    const update = (k, v) => setForm(f => ({ ...f, [k]: v }));

    const validate = () => {
        const e = {};
        if (!form.title.trim()) e.title = 'Title is required';
        if (!form.story) e.story = 'Linked story is required';
        return e;
    };

    const handleCreate = () => {
        const e = validate();
        if (Object.keys(e).length) { setErrors(e); return; }
        const newCase = {
            ...form,
            id: `TC-${String(cases.length + 1).padStart(3, '0')}`,
            steps: +form.steps || 1,
            updatedAt: 'Today',
        };
        setCases(prev => [newCase, ...prev]);
        qaAPI.createTestCase(newCase).catch(err => console.error('Failed to create test case:', err));
        setForm(empty);
        setErrors({});
        setShowModal(false);
    };

    return (
        <div>
            {/* Create Modal */}
            {showModal && (
                <div
                    onClick={e => { if (e.target === e.currentTarget) setShowModal(false); }}
                    style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}
                >
                    <div style={{ background: '#fff', borderRadius: 14, width: 520, maxWidth: '100%', boxShadow: '0 24px 60px rgba(0,0,0,0.2)', overflow: 'hidden' }}>
                        {/* Header */}
                        <div style={{ padding: '18px 22px', background: '#eff6ff', borderBottom: '1px solid #bfdbfe', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                <FlaskConical size={18} color="#3b82f6" />
                                <span style={{ fontWeight: 700, fontSize: '1rem', color: '#1d4ed8' }}>Create New Test Case</span>
                            </div>
                            <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} color="#9ca3af" /></button>
                        </div>

                        {/* Body */}
                        <div style={{ padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 14 }}>
                            {/* Title */}
                            <div>
                                <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Test Case Title *</label>
                                <input
                                    value={form.title}
                                    onChange={e => update('title', e.target.value)}
                                    placeholder="e.g. Verify login with valid credentials"
                                    style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${errors.title ? '#ef4444' : '#e5e7eb'}`, fontSize: '0.85rem', boxSizing: 'border-box' }}
                                />
                                {errors.title && <span style={{ fontSize: '0.73rem', color: '#ef4444' }}>{errors.title}</span>}
                            </div>

                            {/* Linked Story */}
                            <div>
                                <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Linked Story *</label>
                                <select
                                    value={form.story}
                                    onChange={e => update('story', e.target.value)}
                                    style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: `1px solid ${errors.story ? '#ef4444' : '#e5e7eb'}`, fontSize: '0.85rem', boxSizing: 'border-box' }}
                                >
                                    <option value="">Select a story…</option>
                                    {availableStories.map(s => <option key={s} value={s}>{s}</option>)}
                                </select>
                                {errors.story && <span style={{ fontSize: '0.73rem', color: '#ef4444' }}>{errors.story}</span>}
                            </div>

                            {/* Type + Priority row */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <div>
                                    <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Type</label>
                                    <select value={form.type} onChange={e => update('type', e.target.value)}
                                        style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: '0.85rem' }}>
                                        {TYPES.map(t => <option key={t}>{t}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Priority</label>
                                    <select value={form.priority} onChange={e => update('priority', e.target.value)}
                                        style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: '0.85rem' }}>
                                        {PRIORITIES.map(p => <option key={p}>{p}</option>)}
                                    </select>
                                </div>
                            </div>

                            {/* Status + Steps row */}
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <div>
                                    <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Status</label>
                                    <select value={form.status} onChange={e => update('status', e.target.value)}
                                        style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: '0.85rem' }}>
                                        {STATUSES.map(s => <option key={s}>{s}</option>)}
                                    </select>
                                </div>
                                <div>
                                    <label style={{ fontWeight: 600, fontSize: '0.82rem', display: 'block', marginBottom: 6 }}>Number of Steps</label>
                                    <input type="number" min={1} max={50} value={form.steps} onChange={e => update('steps', e.target.value)}
                                        style={{ width: '100%', padding: '9px 12px', borderRadius: 8, border: '1px solid #e5e7eb', fontSize: '0.85rem', boxSizing: 'border-box' }} />
                                </div>
                            </div>
                        </div>

                        {/* Footer */}
                        <div style={{ padding: '14px 22px 20px', display: 'flex', justifyContent: 'flex-end', gap: 10, borderTop: '1px solid #f3f4f6' }}>
                            <button onClick={() => { setShowModal(false); setErrors({}); setForm(empty); }}
                                style={{ padding: '8px 18px', borderRadius: 8, border: '1px solid #e5e7eb', background: '#fff', fontWeight: 600, fontSize: '0.85rem', cursor: 'pointer' }}>
                                Cancel
                            </button>
                            <button onClick={handleCreate}
                                style={{ padding: '8px 20px', borderRadius: 8, border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.85rem', cursor: 'pointer' }}>
                                Create Test Case
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<FlaskConical size={24} />} value={cases.length} label="Total Test Cases" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={cases.filter(c => c.status === 'Passed').length} label="Passed" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={cases.filter(c => c.status === 'Failed').length} label="Failed" color="red" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={cases.filter(c => c.status === 'Pending' || c.status === 'In Progress').length} label="Pending / In Progress" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Test Cases</span>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        {/* Filters */}
                        <div style={{ display: 'flex', gap: 6 }}>
                            {filters.map(f => (
                                <button key={f} onClick={() => setFilter(f)} style={{
                                    padding: '4px 12px', borderRadius: 20, fontSize: '0.75rem', fontWeight: 600, cursor: 'pointer',
                                    background: filter === f ? 'var(--brand-primary)' : 'var(--bg-page)',
                                    color: filter === f ? '#fff' : 'var(--text-secondary)',
                                    border: filter === f ? 'none' : '1px solid var(--border-light)', transition: 'all 0.15s'
                                }}>{f}</button>
                            ))}
                        </div>
                        {/* Create button */}
                        <button
                            onClick={() => setShowModal(true)}
                            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', borderRadius: 8, border: 'none', background: '#3b82f6', color: '#fff', fontWeight: 700, fontSize: '0.82rem', cursor: 'pointer' }}>
                            <Plus size={14} /> Create
                        </button>
                    </div>
                </div>

                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr><th>ID</th><th>Title</th><th>Linked Story</th><th>Type</th><th>Priority</th><th>Steps</th><th>Status</th><th>Updated</th></tr>
                            </thead>
                            <tbody>
                                {filtered.map(tc => {
                                    const sc = statusCfg[tc.status] || statusCfg.Pending;
                                    const pc = priorityCfg[tc.priority] || priorityCfg.Medium;
                                    return (
                                        <tr key={tc.id}>
                                            <td style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.8rem', color: '#3b82f6' }}>{tc.id}</td>
                                            <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{tc.title}</td>
                                            <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: 160 }}>{tc.story}</td>
                                            <td><span style={{ fontSize: '0.75rem', fontWeight: 600, padding: '2px 8px', borderRadius: 12, background: '#eff6ff', color: '#3b82f6' }}>{tc.type}</span></td>
                                            <td><span style={{ fontWeight: 700, fontSize: '0.82rem', color: pc.color }}>{tc.priority}</span></td>
                                            <td style={{ textAlign: 'center', fontWeight: 600 }}>{tc.steps}</td>
                                            <td><span className="badge" style={{ background: sc.bg, color: sc.color }}>{tc.status}</span></td>
                                            <td style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>{tc.updatedAt}</td>
                                        </tr>
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
