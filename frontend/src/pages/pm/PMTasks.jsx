import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { CheckSquare, Filter, AlertTriangle, Clock, Cpu, Plus, UserPlus, X, ClipboardList } from 'lucide-react';
import { getAssignableMembers } from '../../data/roleHierarchy';
import { storiesAPI, tasksAPI, employeesAPI } from '../../services/api';
const riskBadge = { Low: { bg: '#10b981', label: '🟢 Healthy' }, Medium: { bg: '#f59e0b', label: '🟡 Moderate' }, High: { bg: '#ef4444', label: '🔴 High Risk' } };
const statusCols = ['To Do', 'In Progress', 'In Review', 'Done'];
const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', 'Done': '#10b981' };
const priorityColors = { Low: '#6b7280', Medium: '#3b82f6', High: '#f59e0b', Critical: '#ef4444' };
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';
const selectStyle = { padding: '4px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.75rem', background: '#fff', cursor: 'pointer' };

export default function PMTasks() {
    const [storiesData, setStoriesData] = useState([]);
    const [myTasks, setMyTasks] = useState([]);
    const [view, setView] = useState('board');
    const [sprintFilter, setSprintFilter] = useState('All');
    const [riskFilter, setRiskFilter] = useState('All');
    const [memberFilter, setMemberFilter] = useState('All');
    const [statusFilter, setStatusFilter] = useState('All');
    const [showAssignModal, setShowAssignModal] = useState(false);
    const [newStory, setNewStory] = useState({ title: '', assignee: '', type: 'Dev', est: '', status: 'To Do' });

    const [loading, setLoading] = useState(true);
    const [dbTeamMembers, setDbTeamMembers] = useState([]);

    useEffect(() => {
        const fetchAll = async () => {
            try {
                const [emps, stories, tasks] = await Promise.all([
                    employeesAPI.getAll(),
                    storiesAPI.getAll(),
                    tasksAPI.getAll()
                ]);

                if (emps) {
                    const assignable = getAssignableMembers('PM', emps).map(e => e.name);
                    setDbTeamMembers(assignable);
                }
                if (stories?.length) setStoriesData(stories);

                // Filter tasks assigned to PM role
                const pmTasks = tasks?.filter(t => t.assignedToRole === 'PM') || [];
                if (pmTasks.length) setMyTasks(pmTasks);
            } catch (err) {
                console.error('Failed to fetch PM Tasks data:', err);
            } finally {
                setLoading(false);
            }
        };
        fetchAll();
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading tasks...</div>;

    const avgAlignment = storiesData.length ? Math.round(storiesData.reduce((a, s) => a + s.alignment, 0) / storiesData.length) : 0;

    const members = ['All', ...new Set(storiesData.map(s => s.assignee))];
    const filtered = storiesData.filter(s => {
        if (riskFilter !== 'All' && s.risk !== riskFilter) return false;
        if (memberFilter !== 'All' && s.assignee !== memberFilter) return false;
        if (statusFilter !== 'All' && s.status !== statusFilter) return false;
        return true;
    });

    const handleReassign = (id, newAssignee) => {
        setStoriesData(prev => prev.map(s => s.id === id ? { ...s, assignee: newAssignee } : s));
        storiesAPI.update(id, { assignee: newAssignee }).catch(err => console.error('Reassign failed:', err));
    };

    const handleAddStory = () => {
        if (!newStory.title || !newStory.assignee) return;
        const nextId = `ST-${111 + storiesData.length}`;
        const storyData = {
            id: nextId, title: newStory.title, assignee: newStory.assignee, type: newStory.type,
            alignment: 0, risk: 'Low', approval: 'Pending', delay: 0, est: newStory.est || '—', actual: '—', status: newStory.status
        };
        setStoriesData(prev => [...prev, storyData]);
        storiesAPI.create(storyData).catch(err => console.error('Failed to create story:', err));
        setNewStory({ title: '', assignee: '', type: 'Dev', est: '', status: 'To Do' });
        setShowAssignModal(false);
    };

    const handleMyTaskStatusChange = (id, newStatus) => {
        setMyTasks(prev => prev.map(t => t.id === id ? { ...t, status: newStatus } : t));
        tasksAPI.update(id, { status: newStatus }).catch(err => console.error('Task status update failed:', err));
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={storiesData.length} label="Total Stories" color="blue" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={storiesData.filter(s => s.status === 'Done').length} label="Completed" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={storiesData.filter(s => s.risk === 'High').length} label="High Risk" color="red" delay={0.16} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="purple" delay={0.24} />
            </div>

            {/* Filters + Assign Button */}
            <AnimatedCard delay={0.25}>
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Filter size={16} color="var(--text-tertiary)" />
                    <select value={sprintFilter} onChange={e => setSprintFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Sprints</option><option value="Alpha">Sprint Alpha</option><option value="Beta">Sprint Beta</option>
                    </select>
                    <select value={riskFilter} onChange={e => setRiskFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Risk</option><option value="Low">Low</option><option value="Medium">Medium</option><option value="High">High</option>
                    </select>
                    <select value={memberFilter} onChange={e => setMemberFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        {members.map(m => <option key={m} value={m}>{m}</option>)}
                    </select>
                    <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Status</option>{statusCols.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                        <button className="btn btn-sm btn-primary" onClick={() => setShowAssignModal(true)} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <Plus size={14} /> Assign Story
                        </button>
                        <button className={`btn btn-sm ${view === 'board' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('board')}>Board</button>
                        <button className={`btn btn-sm ${view === 'list' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('list')}>List</button>
                    </div>
                </div>
            </AnimatedCard>

            {/* Assign Story Modal */}
            {showAssignModal && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
                    <div style={{ background: '#fff', borderRadius: 'var(--radius-lg)', padding: 28, width: 480, maxWidth: '90vw', boxShadow: '0 20px 60px rgba(0,0,0,0.2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                            <h3 style={{ margin: 0, fontSize: '1.1rem', display: 'flex', alignItems: 'center', gap: 8 }}><UserPlus size={20} style={{ color: '#3b82f6' }} /> Assign New Story / Task</h3>
                            <button onClick={() => setShowAssignModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 4 }}><X size={18} /></button>
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                            <div>
                                <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>Story / Task Title *</label>
                                <input type="text" value={newStory.title} onChange={e => setNewStory({ ...newStory, title: e.target.value })} placeholder="e.g. Implement Payment Gateway"
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem', boxSizing: 'border-box' }} />
                            </div>
                            <div>
                                <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>Assign To *</label>
                                <select value={newStory.assignee} onChange={e => setNewStory({ ...newStory, assignee: e.target.value })}
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
                                    <option value="">Select Member</option>
                                    {dbTeamMembers.map(m => <option key={m} value={m}>{m}</option>)}
                                </select>
                            </div>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                                <div>
                                    <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>Type</label>
                                    <select value={newStory.type} onChange={e => setNewStory({ ...newStory, type: e.target.value })}
                                        style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
                                        <option value="Dev">Dev</option><option value="QA">QA</option><option value="DevOps">DevOps</option><option value="Design">Design</option>
                                    </select>
                                </div>
                                <div>
                                    <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>Estimate</label>
                                    <input type="text" value={newStory.est} onChange={e => setNewStory({ ...newStory, est: e.target.value })} placeholder="e.g. 6h"
                                        style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem', boxSizing: 'border-box' }} />
                                </div>
                                <div>
                                    <label style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: 4, display: 'block' }}>Status</label>
                                    <select value={newStory.status} onChange={e => setNewStory({ ...newStory, status: e.target.value })}
                                        style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.85rem' }}>
                                        {statusCols.map(s => <option key={s} value={s}>{s}</option>)}
                                    </select>
                                </div>
                            </div>
                            <button onClick={handleAddStory} className="btn btn-primary" style={{ marginTop: 8, padding: '10px 20px', width: '100%' }}
                                disabled={!newStory.title || !newStory.assignee}>
                                <Plus size={16} style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
                                Assign Story
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Board View */}
            {view === 'board' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginTop: 20 }}>
                    {statusCols.map(col => (
                        <div key={col}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '8px 12px', background: `${statusColors[col]}15`, borderRadius: 'var(--radius-sm)', borderLeft: `3px solid ${statusColors[col]}` }}>
                                <span style={{ fontWeight: 700, fontSize: '0.85rem', color: statusColors[col] }}>{col}</span>
                                <span className="badge" style={{ background: statusColors[col], color: '#fff', fontSize: '0.7rem' }}>{filtered.filter(s => s.status === col).length}</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {filtered.filter(s => s.status === col).map(s => (
                                    <div key={s.id} style={{ padding: '14px', background: '#fff', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                                            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>{s.id}</span>
                                            <span style={{ fontSize: '0.68rem', fontWeight: 600, color: riskBadge[s.risk].bg }}>{riskBadge[s.risk].label}</span>
                                        </div>
                                        <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 8 }}>{s.title}</div>
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                                            <span className="badge badge-neutral" style={{ fontSize: '0.68rem' }}>{s.type}</span>
                                            <span className="badge" style={{ background: getColor(s.alignment) + '20', color: getColor(s.alignment), fontSize: '0.68rem' }}>AI: {s.alignment}%</span>
                                        </div>
                                        {/* Assign To dropdown */}
                                        <div style={{ marginBottom: 8 }}>
                                            <label style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', fontWeight: 600, display: 'block', marginBottom: 2 }}>Assigned To</label>
                                            <select value={s.assignee} onChange={e => handleReassign(s.id, e.target.value)} style={selectStyle}>
                                                {dbTeamMembers.map(m => <option key={m} value={m}>{m}</option>)}
                                            </select>
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                            <span>{s.est} → {s.actual}</span>
                                        </div>
                                        {s.delay > 0 && (
                                            <div style={{ marginTop: 6, fontSize: '0.72rem', color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <Clock size={12} /> Delayed by {s.delay}h
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* List View */}
            {view === 'list' && (
                <AnimatedCard delay={0.32} style={{ marginTop: 20 }}>
                    <div className="card-body" style={{ padding: 0 }}>
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>ID</th><th>Story Title</th><th>Assigned To</th><th>Type</th>
                                        <th>AI Alignment</th><th>Risk</th><th>Approval</th><th>Delay</th><th>Est vs Actual</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {filtered.map(s => (
                                        <tr key={s.id}>
                                            <td style={{ fontWeight: 600, fontSize: '0.8rem', color: 'var(--text-tertiary)' }}>{s.id}</td>
                                            <td style={{ fontWeight: 600 }}>{s.title}</td>
                                            <td>
                                                <select value={s.assignee} onChange={e => handleReassign(s.id, e.target.value)} style={selectStyle}>
                                                    {dbTeamMembers.map(m => <option key={m} value={m}>{m}</option>)}
                                                </select>
                                            </td>
                                            <td><span className="badge badge-neutral">{s.type}</span></td>
                                            <td><span style={{ fontWeight: 700, color: getColor(s.alignment) }}>{s.alignment}%</span></td>
                                            <td><span style={{ fontSize: '0.78rem', fontWeight: 600, color: riskBadge[s.risk].bg }}>{riskBadge[s.risk].label}</span></td>
                                            <td><span className="badge" style={{ background: s.approval === 'Approved' ? '#10b98120' : s.approval === 'Rejected' ? '#ef444420' : '#f59e0b20', color: s.approval === 'Approved' ? '#10b981' : s.approval === 'Rejected' ? '#ef4444' : '#f59e0b' }}>{s.approval}</span></td>
                                            <td>{s.delay > 0 ? <span style={{ color: '#ef4444', fontWeight: 600 }}>{s.delay}h</span> : <span style={{ color: '#10b981' }}>—</span>}</td>
                                            <td style={{ fontSize: '0.8rem' }}>{s.est} → {s.actual}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}

            {/* ─── Tasks Assigned to Me ─── */}
            <AnimatedCard delay={0.4} style={{ marginTop: 24 }}>
                <div className="card-header">
                    <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <ClipboardList size={18} /> Tasks Assigned to Me
                    </span>
                    <span className="badge badge-info">{myTasks.length} tasks</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>ID</th><th>Task</th><th>From</th><th>Priority</th><th>Status</th><th>Due</th><th>Est vs Actual</th>
                                </tr>
                            </thead>
                            <tbody>
                                {myTasks.map(t => (
                                    <tr key={t.id}>
                                        <td style={{ fontFamily: "'Courier New',monospace", fontWeight: 700, fontSize: '0.82rem', color: '#3b82f6' }}>{t.id}</td>
                                        <td style={{ fontWeight: 600 }}>{t.title}</td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{t.from}</td>
                                        <td><span className="badge" style={{ background: `${priorityColors[t.priority]}20`, color: priorityColors[t.priority], fontWeight: 600 }}>{t.priority}</span></td>
                                        <td>
                                            <select value={t.status} onChange={e => handleMyTaskStatusChange(t.id, e.target.value)}
                                                style={{ ...selectStyle, fontWeight: 600, color: statusColors[t.status], background: `${statusColors[t.status]}10` }}>
                                                {statusCols.map(st => <option key={st} value={st}>{st}</option>)}
                                            </select>
                                        </td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{t.due}</td>
                                        <td style={{ fontSize: '0.8rem' }}>{t.est} → {t.actual}</td>
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
