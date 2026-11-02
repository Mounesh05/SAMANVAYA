import { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { ClipboardList, Send, CheckCircle, Clock, AlertCircle, Plus, X, Filter, Cpu } from 'lucide-react';
import { ROLE_CAN_ASSIGN_TO, ROLE_DISPLAY_NAMES } from '../../data/roleHierarchy';

import { employeesAPI, tasksAPI } from '../../services/api';
import ConfirmToast from '../../components/ConfirmToast';

/*
 * Hierarchical task delegation (enforced by roleHierarchy.js):
 *   CEO  →  HR, PM, LEAD, DEVELOPER, DEVOPS, QA
 *   HR   →  PM, LEAD, DEVELOPER, DEVOPS, QA
 *   PM   →  LEAD, DEVELOPER, DEVOPS, QA
 *   LEAD →  DEVELOPER, DEVOPS, QA
 *   DEVELOPER, DEVOPS, QA → cannot assign
 */


const statusCols = ['To Do', 'In Progress', 'In Review', 'Done'];
const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', Done: '#10b981' };
const priorityColors = { Low: '#6b7280', Medium: '#3b82f6', High: '#f59e0b', Critical: '#ef4444' };
const selectStyle = { padding: '4px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.75rem', background: '#fff', cursor: 'pointer' };

export default function TaskManagement() {
    const { user } = useAuth();
    const role = user?.role;
    const canAssign = (ROLE_CAN_ASSIGN_TO[role] || []).length > 0;
    const canReceive = role !== 'CEO';

    const defaultTab = canReceive ? 'assigned' : 'assigning';
    const [tab, setTab] = useState(defaultTab);
    const [view, setView] = useState('board');

    /* All employees fetched from the database */
    const [dbEmployees, setDbEmployees] = useState([]);

    /* Task lists */
    const [assignedTasks, setAssignedTasks] = useState([]);
    const [assigningTasks, setAssigningTasks] = useState([]);
    const [loading, setLoading] = useState(true);

    /* Load employees from database (for member dropdown) */
    useEffect(() => {
        employeesAPI.getAll()
            .then(data => setDbEmployees(Array.isArray(data) ? data : []))
            .catch(() => { });
    }, []);

    /* Load tasks from database — always update state, even when empty */
    const loadTasks = () => {
        const userName = user?.name || '';
        setLoading(true);
        tasksAPI.getAll()
            .then(dbTasks => {
                const all = Array.isArray(dbTasks) ? dbTasks : [];
                // Tasks assigned TO this specific user (matched by name inside the 'to' label)
                const toMe = all.filter(t =>
                    (t.assignedToName && t.assignedToName === userName) ||
                    (t.to && t.to.includes(userName))
                );
                // Tasks assigned BY this specific user (matched by name, not just role)
                const byMe = all.filter(t => t.assignedBy === userName);
                setAssignedTasks(toMe);
                setAssigningTasks(byMe);
            })
            .catch(() => { })
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        if (user?.name) loadTasks();
    }, [user?.name]);

    /* Filters */
    const [statusFilter, setStatusFilter] = useState('All');
    const [priorityFilter, setPriorityFilter] = useState('All');

    /* New-task form state */
    const [showForm, setShowForm] = useState(false);
    const [newTitle, setNewTitle] = useState('');
    const [newDescription, setNewDescription] = useState('');
    const [newPriority, setNewPriority] = useState('Medium');
    const [newAssignTo, setNewAssignTo] = useState('');
    const [newAssignName, setNewAssignName] = useState('');

    /* Members of the currently selected assignee role — from the database */
    const membersForRole = newAssignTo
        ? dbEmployees.filter(e => {
            const displayName = ROLE_DISPLAY_NAMES[newAssignTo];
            // Match against both the role key (e.g. 'DEVELOPER') and display name (e.g. 'Developer')
            return e.role === newAssignTo || e.role === displayName;
        })
        : [];

    const handleNewTask = async (e) => {
        e.preventDefault();
        const displayName = ROLE_DISPLAY_NAMES[newAssignTo] || newAssignTo;
        const label = newAssignName ? `${newAssignName} (${displayName})` : displayName;
        const task = {
            id: `T-${Date.now().toString().slice(-4)}`,
            title: newTitle,
            description: newDescription,
            to: label,
            from: `${user?.name || 'Unknown'} (${ROLE_DISPLAY_NAMES[role] || role})`,
            assignedBy: user?.name || '',
            assignedByRole: role,
            assignedToRole: newAssignTo,
            assignedToName: newAssignName || '',
            type: 'Task',
            priority: newPriority,
            status: 'To Do',
            due: 'TBD',
            est: '—',
            actual: '—',
            delay: 0,
        };
        try {
            await tasksAPI.create(task);
            loadTasks(); // re-fetch to keep board in sync with DB
        } catch (err) {
            console.error('Failed to create task:', err);
        }
        setNewTitle(''); setNewDescription(''); setNewPriority('Medium'); setNewAssignTo(''); setNewAssignName(''); setShowForm(false);
    };

    const handleStatusChange = (id, newStatus, list) => {
        if (list === 'assigned') {
            setAssignedTasks(prev => prev.map(t => t.id === id ? { ...t, status: newStatus } : t));
        } else {
            setAssigningTasks(prev => prev.map(t => t.id === id ? { ...t, status: newStatus } : t));
        }
        tasksAPI.update(id, { status: newStatus }).catch(err => console.error('Failed to update task status:', err));
    };

    const filteredAssigned = assignedTasks.filter(t => {
        if (statusFilter !== 'All' && t.status !== statusFilter) return false;
        if (priorityFilter !== 'All' && t.priority !== priorityFilter) return false;
        return true;
    });

    const filteredAssigning = assigningTasks.filter(t => {
        if (statusFilter !== 'All' && t.status !== statusFilter) return false;
        if (priorityFilter !== 'All' && t.priority !== priorityFilter) return false;
        return true;
    });

    const currentTasks = tab === 'assigned' ? filteredAssigned : filteredAssigning;

    if (loading) return (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: 60, color: 'var(--text-tertiary)', fontSize: '0.9rem', gap: 12 }}>
            <span style={{ width: 20, height: 20, borderRadius: '50%', border: '2px solid var(--border-color)', borderTopColor: '#3b82f6', animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />
            Loading tasks…
        </div>
    );

    return (
        <div>
            {/* Stats */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<ClipboardList size={24} />} value={assignedTasks.length + assigningTasks.length} label="Total Tasks" color="blue" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={(tab === 'assigned' ? assignedTasks : assigningTasks).filter(t => t.status === 'Done').length} label="Completed" color="green" delay={0.08} />
                <StatsCard icon={<AlertCircle size={24} />} value={(tab === 'assigned' ? assignedTasks : assigningTasks).filter(t => t.priority === 'High' || t.priority === 'Critical').length} label="High Priority" color="red" delay={0.16} />
                <StatsCard icon={<Cpu size={24} />} value={(tab === 'assigned' ? assignedTasks : assigningTasks).filter(t => t.status === 'In Progress').length} label="In Progress" color="purple" delay={0.24} />
            </div>

            {/* Tabs */}
            <div className="task-tabs mb-lg">
                {canReceive && (
                    <button className={`task-tab ${tab === 'assigned' ? 'active' : ''}`} onClick={() => setTab('assigned')}>
                        <ClipboardList size={16} /> Assigned to Me
                        <span className="task-tab-count">{assignedTasks.length}</span>
                    </button>
                )}
                {canAssign && (
                    <button className={`task-tab ${tab === 'assigning' ? 'active' : ''}`} onClick={() => setTab('assigning')}>
                        <Send size={16} /> Tasks I Assigned
                        <span className="task-tab-count">{assigningTasks.length}</span>
                    </button>
                )}
            </div>

            {/* Filters + View Toggle */}
            <AnimatedCard delay={0.25}>
                <div className="card-body" style={{ display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Filter size={16} color="var(--text-tertiary)" />
                    <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Status</option>
                        {statusCols.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                    <select value={priorityFilter} onChange={e => setPriorityFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                        <option value="All">All Priority</option>
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Critical">Critical</option>
                    </select>
                    <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
                        {canAssign && tab === 'assigning' && (
                            <button className="btn btn-sm btn-primary" onClick={() => setShowForm(!showForm)} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                                {showForm ? <X size={14} /> : <Plus size={14} />} {showForm ? 'Close' : 'Assign Task'}
                            </button>
                        )}
                        <button className={`btn btn-sm ${view === 'board' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('board')}>Board</button>
                        <button className={`btn btn-sm ${view === 'list' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setView('list')}>List</button>
                    </div>
                </div>
            </AnimatedCard>

            {/* New Task Form */}
            {showForm && canAssign && tab === 'assigning' && (
                <AnimatedCard delay={0} className="mb-lg" style={{ marginTop: 16 }}>
                    <div className="card-header"><span className="card-title">Create & Assign New Task</span></div>
                    <div className="card-body">
                        <form onSubmit={handleNewTask} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                                <label className="form-label">Task Title *</label>
                                <input className="form-input" placeholder="Describe the task…" value={newTitle} onChange={e => setNewTitle(e.target.value)} required />
                            </div>
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                                <label className="form-label">Task Description</label>
                                <textarea className="form-input" rows={3} placeholder="Enter detailed task description…" value={newDescription} onChange={e => setNewDescription(e.target.value)}
                                    style={{ resize: 'vertical', minHeight: 60 }} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Priority</label>
                                <select className="form-select" value={newPriority} onChange={e => setNewPriority(e.target.value)}>
                                    <option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Assign To Role *</label>
                                <select className="form-select" value={newAssignTo} onChange={e => { setNewAssignTo(e.target.value); setNewAssignName(''); }} required>
                                    <option value="">Select role…</option>
                                    {(ROLE_CAN_ASSIGN_TO[role] || []).map(r => (
                                        <option key={r} value={r}>{ROLE_DISPLAY_NAMES[r]}</option>
                                    ))}
                                </select>
                            </div>
                            {newAssignTo && (
                                <div className="form-group">
                                    <label className="form-label">Assign To Member{membersForRole.length > 0 ? ' *' : ''}</label>
                                    {membersForRole.length > 0 ? (
                                        <select className="form-select" value={newAssignName} onChange={e => setNewAssignName(e.target.value)} required>
                                            <option value="">Select member…</option>
                                            {membersForRole.map(m => (
                                                <option key={m.employee_id || m.id} value={m.name}>{m.name}</option>
                                            ))}
                                        </select>
                                    ) : (
                                        <p style={{ fontSize: '0.82rem', color: 'var(--text-tertiary)', margin: '4px 0 0' }}>No members found for this role.</p>
                                    )}
                                </div>
                            )}
                            <div style={{ gridColumn: '1 / -1' }}>
                                <button className="btn btn-primary" type="submit"><Send size={16} /> Assign Task</button>
                            </div>
                        </form>
                    </div>
                </AnimatedCard>
            )}

            {/* Board View */}
            {view === 'board' && (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16, marginTop: 20 }}>
                    {statusCols.map(col => (
                        <div key={col}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, padding: '8px 12px', background: `${statusColors[col]}15`, borderRadius: 'var(--radius-sm)', borderLeft: `3px solid ${statusColors[col]}` }}>
                                <span style={{ fontWeight: 700, fontSize: '0.85rem', color: statusColors[col] }}>{col}</span>
                                <span className="badge" style={{ background: statusColors[col], color: '#fff', fontSize: '0.7rem' }}>{currentTasks.filter(s => s.status === col).length}</span>
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                                {currentTasks.filter(s => s.status === col).map(s => (
                                    <div key={s.id} style={{ padding: '14px', background: '#fff', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', boxShadow: '0 1px 3px rgba(0,0,0,0.06)' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                                            <span style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)', fontWeight: 600 }}>{s.id}</span>
                                            <span className="badge" style={{ background: `${priorityColors[s.priority]}20`, color: priorityColors[s.priority], fontSize: '0.65rem', fontWeight: 600 }}>{s.priority}</span>
                                        </div>
                                        <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 6 }}>{s.title}</div>
                                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 8 }}>
                                            {s.type && <span className="badge badge-neutral" style={{ fontSize: '0.68rem' }}>{s.type}</span>}
                                        </div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                            {tab === 'assigned' ? `From: ${s.from}` : `To: ${s.to}`}
                                        </div>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                            <span>Due: {s.due}</span>
                                            <select value={s.status} onChange={e => handleStatusChange(s.id, e.target.value, tab)} style={selectStyle}>
                                                {statusCols.map(st => <option key={st} value={st}>{st}</option>)}
                                            </select>
                                        </div>
                                        {s.delay > 0 && (
                                            <div style={{ marginTop: 6, fontSize: '0.72rem', color: '#ef4444', fontWeight: 600, display: 'flex', alignItems: 'center', gap: 4 }}>
                                                <Clock size={12} /> Delayed by {s.delay}h
                                            </div>
                                        )}
                                    </div>
                                ))}
                                {currentTasks.filter(s => s.status === col).length === 0 && (
                                    <div style={{ padding: 16, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: '0.8rem', border: '1px dashed var(--border-color)', borderRadius: 'var(--radius-sm)' }}>No tasks</div>
                                )}
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
                                        <th>ID</th><th>Task</th><th>{tab === 'assigned' ? 'From' : 'Assigned To'}</th><th>Type</th>
                                        <th>Priority</th><th>Status</th><th>Due</th><th>Est vs Actual</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {currentTasks.map(s => (
                                        <tr key={s.id}>
                                            <td style={{ fontFamily: "'Courier New',monospace", fontWeight: 700, fontSize: '0.82rem', color: '#3b82f6' }}>{s.id}</td>
                                            <td style={{ fontWeight: 600 }}>{s.title}</td>
                                            <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{tab === 'assigned' ? s.from : s.to}</td>
                                            <td><span className="badge badge-neutral">{s.type || '—'}</span></td>
                                            <td><span className="badge" style={{ background: `${priorityColors[s.priority]}20`, color: priorityColors[s.priority], fontWeight: 600 }}>{s.priority}</span></td>
                                            <td>
                                                <select value={s.status} onChange={e => handleStatusChange(s.id, e.target.value, tab)} style={{ ...selectStyle, fontWeight: 600, color: statusColors[s.status], background: `${statusColors[s.status]}10` }}>
                                                    {statusCols.map(st => <option key={st} value={st}>{st}</option>)}
                                                </select>
                                            </td>
                                            <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{s.due}</td>
                                            <td style={{ fontSize: '0.8rem' }}>{s.est} → {s.actual}</td>
                                        </tr>
                                    ))}
                                    {currentTasks.length === 0 && (
                                        <tr><td colSpan={8} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>No tasks found.</td></tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
