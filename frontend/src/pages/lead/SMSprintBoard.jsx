import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Layers, CheckCircle, Clock, AlertTriangle, Filter, Plus, X } from 'lucide-react';
import { leadAPI } from '../../services/api';

const columns = ['To Do', 'In Progress', 'In Review', 'Done', 'Blocked'];
const colColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', Done: '#10b981', Blocked: '#ef4444' };
const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };

export default function SMSprintBoard() {
    const [stories, setStories] = useState([]);
    const [view, setView] = useState('board');
    const [memberFilter, setMemberFilter] = useState('All');
    const [riskFilter, setRiskFilter] = useState('All');
    const [members, setMembers] = useState(['All']);
    const [loading, setLoading] = useState(true);

    const alignColor = v => v >= 80 ? '#10b981' : v >= 65 ? '#f59e0b' : '#ef4444';
    const reviewBadge = { Approved: '#10b981', Pending: '#f59e0b', 'In Review': '#3b82f6', Rejected: '#ef4444' };

    useEffect(() => {
        Promise.all([
            leadAPI.sprintBoard(),
            leadAPI.myTeam()
        ]).then(([storiesData, teamData]) => {
            if (storiesData) setStories(storiesData);
            if (teamData) setMembers(['All', ...teamData.map(m => m.name)]);
        }).catch(err => console.error('Failed to fetch sprint board data:', err))
            .finally(() => setLoading(false));
    }, []);

    const [showAdd, setShowAdd] = useState(false);
    const [newStory, setNewStory] = useState({ title: '', assignee: '', type: 'Dev', points: 5, alignment: 0, risk: 'Low', reviewStatus: 'Pending', dueDate: '', status: 'To Do' });

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading sprint board...</div>;

    const filtered = stories.filter(s => {
        if (memberFilter !== 'All' && s.assignee !== memberFilter) return false;
        if (riskFilter !== 'All' && s.risk !== riskFilter) return false;
        return true;
    });

    const handleStatusChange = (id, status) => {
        setStories(prev => prev.map(s => s.id === id ? { ...s, status } : s));
        leadAPI.updateStory(id, { status }).catch(err => console.error('Failed to update story status:', err));
    };

    const handleAdd = async () => {
        if (!newStory.title || !newStory.assignee) return;
        const storyData = { ...newStory, id: `ST-${120 + stories.length}`, alignment: 0 };
        setStories(prev => [...prev, storyData]);
        setNewStory({ title: '', assignee: '', type: 'Dev', points: 5, alignment: 0, risk: 'Low', reviewStatus: 'Pending', dueDate: '', status: 'To Do' });
        setShowAdd(false);
        leadAPI.createStory(storyData).catch(err => console.error('Failed to create story:', err));
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Layers size={24} />} value={stories.length} label="Total Stories" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={stories.filter(s => s.status === 'Done').length} label="Done" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={stories.filter(s => s.status === 'Blocked').length} label="Blocked" color="red" delay={0.16} />
                <StatsCard icon={<Clock size={24} />} value={`${stories.reduce((a, s) => a + s.points, 0)} SP`} label="Total Points" color="purple" delay={0.24} />
            </div>

            {/* Filters */}
            <AnimatedCard delay={0.25}>
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Filter size={15} color="var(--text-tertiary)" />
                    <select value={memberFilter} onChange={e => setMemberFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        {members.map(m => <option key={m}>{m}</option>)}
                    </select>
                    <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Risk</option><option>Low</option><option>Medium</option><option>High</option>
                    </select>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                        <button className="btn btn-sm btn-primary" onClick={() => setShowAdd(true)} style={{ display: 'flex', alignItems: 'center', gap: 4 }}><Plus size={13} /> Add Story</button>
                        <button className={`btn btn-sm ${view === 'board' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('board')}>Board</button>
                        <button className={`btn btn-sm ${view === 'list' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('list')}>List</button>
                    </div>
                </div>
            </AnimatedCard>

            {/* Add Story Modal */}
            {showAdd && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div style={{ background: '#fff', borderRadius: 12, padding: 28, width: 480, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                            <h3 style={{ margin: 0 }}>Add Story to Sprint</h3>
                            <button onClick={() => setShowAdd(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}><X size={18} /></button>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                            <input placeholder="Story title *" value={newStory.title} onChange={e => setNewStory({ ...newStory, title: e.target.value })}
                                style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }} />
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <select value={newStory.assignee} onChange={e => setNewStory({ ...newStory, assignee: e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }}>
                                    <option value="">Assign to…</option>
                                    {members.slice(1).map(m => <option key={m}>{m}</option>)}
                                </select>
                                <select value={newStory.type} onChange={e => setNewStory({ ...newStory, type: e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }}>
                                    <option>Dev</option><option>QA</option><option>DevOps</option>
                                </select>
                                <input type="number" placeholder="Story points" value={newStory.points} onChange={e => setNewStory({ ...newStory, points: +e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }} />
                                <input type="date" value={newStory.dueDate} onChange={e => setNewStory({ ...newStory, dueDate: e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }} />
                                <select value={newStory.risk} onChange={e => setNewStory({ ...newStory, risk: e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }}>
                                    <option>Low</option><option>Medium</option><option>High</option>
                                </select>
                                <select value={newStory.status} onChange={e => setNewStory({ ...newStory, status: e.target.value })}
                                    style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: '0.85rem' }}>
                                    {columns.map(c => <option key={c}>{c}</option>)}
                                </select>
                            </div>
                            <button onClick={handleAdd} className="btn btn-primary" disabled={!newStory.title || !newStory.assignee}>Add Story</button>
                        </div>
                    </div>
                </div>
            )}

            {/* Board View */}
            {view === 'board' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginTop: 18 }}>
                    {columns.map(col => (
                        <div key={col}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 10, padding: '7px 12px', background: `${colColors[col]}15`, borderRadius: 8, borderLeft: `3px solid ${colColors[col]}` }}>
                                <span style={{ fontWeight: 700, fontSize: '0.82rem', color: colColors[col] }}>{col}</span>
                                <span className="badge" style={{ background: colColors[col], color: '#fff', fontSize: '0.65rem' }}>{filtered.filter(s => s.status === col).length}</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 9 }}>
                                {filtered.filter(s => s.status === col).map(s => (
                                    <div key={s.id} style={{ padding: 12, background: '#fff', borderRadius: 10, border: '1px solid var(--border-color)', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
                                            <span style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>{s.id} · {s.points} SP</span>
                                            <span style={{ width: 9, height: 9, borderRadius: '50%', background: riskColors[s.risk], display: 'inline-block' }} title={`${s.risk} Risk`} />
                                        </div>
                                        <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 6, lineHeight: 1.3 }}>{s.title}</div>
                                        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 6 }}>
                                            <span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>{s.type}</span>
                                            <span className="badge" style={{ background: alignColor(s.alignment) + '20', color: alignColor(s.alignment), fontSize: '0.65rem' }}>AI {s.alignment}%</span>
                                            <span className="badge" style={{ background: (reviewBadge[s.reviewStatus] || '#6b7280') + '20', color: reviewBadge[s.reviewStatus] || '#6b7280', fontSize: '0.65rem' }}>{s.reviewStatus}</span>
                                        </div>
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginBottom: 6 }}>{s.assignee}</div>
                                        {s.dueDate && <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)' }}>Due: {s.dueDate}</div>}
                                        <select value={s.status} onChange={e => handleStatusChange(s.id, e.target.value)}
                                            style={{ marginTop: 8, width: '100%', padding: '3px 6px', borderRadius: 6, border: '1px solid var(--border-color)', fontSize: '0.72rem', cursor: 'pointer' }}>
                                            {columns.map(c => <option key={c}>{c}</option>)}
                                        </select>
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* List View */}
            {view === 'list' && (
                <AnimatedCard delay={0.3} style={{ marginTop: 18 }}>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr><th>ID</th><th>Story</th><th>Assigned</th><th>Type</th><th>SP</th><th>AI Align</th><th>Risk</th><th>Review</th><th>Due</th><th>Status</th></tr>
                                </thead>
                                <tbody>
                                    {filtered.map(s => (
                                        <tr key={s.id}>
                                            <td style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '0.8rem', color: '#3b82f6' }}>{s.id}</td>
                                            <td style={{ fontWeight: 600 }}>{s.title}</td>
                                            <td style={{ fontSize: '0.82rem' }}>{s.assignee}</td>
                                            <td><span className="badge badge-neutral">{s.type}</span></td>
                                            <td style={{ fontWeight: 700 }}>{s.points}</td>
                                            <td><span style={{ fontWeight: 700, color: alignColor(s.alignment) }}>{s.alignment}%</span></td>
                                            <td><span style={{ color: riskColors[s.risk], fontWeight: 600 }}>{s.risk}</span></td>
                                            <td><span className="badge" style={{ background: (reviewBadge[s.reviewStatus] || '#6b7280') + '20', color: reviewBadge[s.reviewStatus] || '#6b7280' }}>{s.reviewStatus}</span></td>
                                            <td style={{ fontSize: '0.8rem' }}>{s.dueDate}</td>
                                            <td>
                                                <select value={s.status} onChange={e => handleStatusChange(s.id, e.target.value)}
                                                    style={{ padding: '3px 8px', borderRadius: 6, border: '1px solid var(--border-color)', fontSize: '0.75rem', color: colColors[s.status], fontWeight: 600 }}>
                                                    {columns.map(c => <option key={c}>{c}</option>)}
                                                </select>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
