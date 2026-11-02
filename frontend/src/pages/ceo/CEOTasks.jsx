import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { ClipboardList, Send, CheckCircle, Clock, AlertCircle, Plus, X } from 'lucide-react';
import { ROLE_CAN_ASSIGN_TO, ROLE_DISPLAY_NAMES } from '../../data/roleHierarchy';
import { tasksAPI } from '../../services/api';


const priorityColors = { Low: '#6b7280', Medium: '#3b82f6', High: '#f59e0b', Critical: '#ef4444' };
const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', Done: '#10b981' };

export default function CEOTasks() {
    const [tasks, setTasks] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [newTask, setNewTask] = useState({ title: '', description: '', assignRole: '', priority: 'Medium' });
    const [filter, setFilter] = useState('All');

    useEffect(() => {
        tasksAPI.getAll({ role: 'CEO' }).then(t => { if (t?.length) setTasks(t); }).catch(() => { });
    }, []);

    const assignableRoles = ROLE_CAN_ASSIGN_TO['CEO'] || [];
    const filteredTasks = filter === 'All' ? tasks : tasks.filter(t => t.status === filter);

    const handleCreateTask = (e) => {
        e.preventDefault();
        const roleName = ROLE_DISPLAY_NAMES[newTask.assignRole] || newTask.assignRole;
        const task = {
            id: `CEO-T${String(tasks.length + 1).padStart(2, '0')}`,
            title: newTask.title,
            description: newTask.description,
            assignedTo: `${roleName}`,
            priority: newTask.priority,
            status: 'To Do',
            due: 'TBD',
        };
        setTasks(prev => [task, ...prev]);
        tasksAPI.create(task).catch(err => console.error('Failed to create task:', err));
        setNewTask({ title: '', description: '', assignRole: '', priority: 'Medium' });
        setShowForm(false);
    };

    const handleStatusChange = (id, newStatus) => {
        setTasks(prev => prev.map(t => t.id === id ? { ...t, status: newStatus } : t));
        tasksAPI.update(id, { status: newStatus }).catch(err => console.error('Failed to update task status:', err));
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<ClipboardList size={24} />} value={tasks.length} label="Total Tasks" color="blue" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={tasks.filter(t => t.status === 'To Do').length} label="To Do" color="orange" delay={0.08} />
                <StatsCard icon={<AlertCircle size={24} />} value={tasks.filter(t => t.status === 'In Progress').length} label="In Progress" color="purple" delay={0.16} />
                <StatsCard icon={<CheckCircle size={24} />} value={tasks.filter(t => t.status === 'Done').length} label="Completed" color="green" delay={0.24} />
            </div>

            {/* Toolbar */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">CEO Task Delegation</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <select value={filter} onChange={e => setFilter(e.target.value)}
                            style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                            <option value="All">All Status</option>
                            <option value="To Do">To Do</option>
                            <option value="In Progress">In Progress</option>
                            <option value="Done">Done</option>
                        </select>
                        <button className="btn btn-primary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => setShowForm(!showForm)}>
                            {showForm ? <X size={14} /> : <Plus size={14} />} {showForm ? 'Close' : 'New Task'}
                        </button>
                    </div>
                </div>

                {/* New Task Form */}
                {showForm && (
                    <div className="card-body" style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <form onSubmit={handleCreateTask} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                                <label className="form-label">Task Title *</label>
                                <input className="form-input" placeholder="Enter task title…" value={newTask.title} onChange={e => setNewTask({ ...newTask, title: e.target.value })} required />
                            </div>
                            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                                <label className="form-label">Description *</label>
                                <textarea className="form-input" rows={3} placeholder="Enter task description…" value={newTask.description}
                                    onChange={e => setNewTask({ ...newTask, description: e.target.value })} style={{ resize: 'vertical', minHeight: 60 }} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Assign To *</label>
                                <select className="form-select" value={newTask.assignRole} onChange={e => setNewTask({ ...newTask, assignRole: e.target.value })} required>
                                    <option value="">Select role…</option>
                                    {assignableRoles.map(r => (
                                        <option key={r} value={r}>{ROLE_DISPLAY_NAMES[r]}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Priority</label>
                                <select className="form-select" value={newTask.priority} onChange={e => setNewTask({ ...newTask, priority: e.target.value })}>
                                    <option>Low</option><option>Medium</option><option>High</option><option>Critical</option>
                                </select>
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <button className="btn btn-primary" type="submit"><Send size={16} /> Assign Task</button>
                            </div>
                        </form>
                    </div>
                )}

                {/* Task Table */}
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Task</th>
                                    <th>Description</th>
                                    <th>Assigned To</th>
                                    <th>Priority</th>
                                    <th>Status</th>
                                    <th>Due</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredTasks.map(t => (
                                    <tr key={t.id}>
                                        <td style={{ fontFamily: 'monospace', fontSize: '0.82rem', fontWeight: 600, color: '#3b82f6' }}>{t.id}</td>
                                        <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.title}</td>
                                        <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', maxWidth: 220 }}>{t.description || '—'}</td>
                                        <td><span className="badge badge-info">{t.assignedTo}</span></td>
                                        <td><span className="badge" style={{ background: `${priorityColors[t.priority]}20`, color: priorityColors[t.priority], fontWeight: 600 }}>{t.priority}</span></td>
                                        <td>
                                            <select value={t.status} onChange={e => handleStatusChange(t.id, e.target.value)}
                                                style={{
                                                    padding: '4px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.78rem',
                                                    fontWeight: 600, color: statusColors[t.status], background: `${statusColors[t.status]}10`
                                                }}>
                                                <option value="To Do">To Do</option>
                                                <option value="In Progress">In Progress</option>
                                                <option value="Done">Done</option>
                                            </select>
                                        </td>
                                        <td style={{ fontSize: '0.8rem' }}>{t.due}</td>
                                    </tr>
                                ))}
                                {filteredTasks.length === 0 && (
                                    <tr><td colSpan={7} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>No tasks found.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
