import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { CheckSquare, Filter, Search } from 'lucide-react';
import { storiesAPI } from '../../services/api';

const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', 'Done': '#10b981' };
const typeColors = { Dev: '#3b82f6', QA: '#8b5cf6', DevOps: '#10b981', Research: '#f59e0b' };
const approvalColors = { 'Approved': '#10b981', 'Pending Review': '#f59e0b', 'Not Started': '#6b7280' };

export default function BacklogStories() {
    const [stories, setStories] = useState([]);
    const [filter, setFilter] = useState('All');
    const [search, setSearch] = useState('');

    useEffect(() => {
        storiesAPI.getAll()
            .then(data => { if (Array.isArray(data) && data.length) setStories(data); })
            .catch(err => { console.error('Failed to load stories:', err); });
    }, []);

    const filtered = stories.filter(s => {
        if (filter !== 'All' && s.status !== filter) return false;
        if (search && !s.title.toLowerCase().includes(search.toLowerCase()) && !s.id.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
    });

    return (

        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={stories.length} label="Total Stories" trend="Sprint Alpha" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<CheckSquare size={24} />} value={stories.filter(s => s.status === 'Done').length} label="Completed" trend={`${((stories.filter(s => s.status === 'Done').length / stories.length) * 100).toFixed(0)}%`} trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<CheckSquare size={24} />} value={stories.filter(s => s.status === 'In Progress').length} label="In Progress" color="orange" delay={0.16} />
                <StatsCard icon={<CheckSquare size={24} />} value={stories.filter(s => s.status === 'To Do').length} label="To Do" color="gray" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Backlog / Stories</span>
                    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                        <div style={{ position: 'relative' }}>
                            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
                            <input
                                type="text" placeholder="Search..." value={search}
                                onChange={e => setSearch(e.target.value)}
                                style={{ paddingLeft: 30, padding: '6px 12px 6px 30px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem', width: 160 }}
                            />
                        </div>
                        <select value={filter} onChange={e => setFilter(e.target.value)} style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                            <option value="All">All Status</option>
                            <option value="To Do">To Do</option>
                            <option value="In Progress">In Progress</option>
                            <option value="In Review">In Review</option>
                            <option value="Done">Done</option>
                        </select>
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Story</th>
                                    <th>Module</th>
                                    <th>Type</th>
                                    <th>Assignee</th>
                                    <th>Alignment</th>
                                    <th>Status</th>
                                    <th>Approval</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(s => (
                                    <tr key={s.id}>
                                        <td>
                                            <div style={{ fontWeight: 700, color: '#3b82f6', fontSize: '0.78rem' }}>{s.id}</div>
                                            <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{s.title}</div>
                                            <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 2 }}>{(s.desc || s.description || '').substring(0, 60)}...</div>
                                        </td>
                                        <td><span className="badge badge-info">{s.module || '—'}</span></td>
                                        <td><span className="badge" style={{ background: typeColors[s.type], color: '#fff' }}>{s.type}</span></td>
                                        <td style={{ fontWeight: 500 }}>{s.assignee}</td>
                                        <td>
                                            {s.alignment > 0 ? (
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <div style={{ width: 40, height: 6, background: '#f0f0f0', borderRadius: 3, overflow: 'hidden' }}>
                                                        <div style={{ height: '100%', width: `${s.alignment}%`, background: s.alignment >= 80 ? '#10b981' : s.alignment >= 60 ? '#f59e0b' : '#ef4444', borderRadius: 3 }} />
                                                    </div>
                                                    <span style={{ fontSize: '0.78rem', fontWeight: 700 }}>{s.alignment}%</span>
                                                </div>
                                            ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>}
                                        </td>
                                        <td><span className="badge" style={{ background: statusColors[s.status], color: '#fff' }}>{s.status}</span></td>
                                        <td><span className="badge" style={{ background: `${approvalColors[s.approval]}20`, color: approvalColors[s.approval], fontWeight: 600 }}>{s.approval}</span></td>
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
