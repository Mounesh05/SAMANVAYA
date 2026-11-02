import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Target, Clock, TrendingUp, CheckCircle, AlertCircle, BarChart3, User, Calendar } from 'lucide-react';
import { storiesAPI } from '../../services/api';

const statusColumns = ['To Do', 'In Progress', 'In Review', 'Done'];
const statusColors = { 'To Do': '#6b7280', 'In Progress': '#3b82f6', 'In Review': '#f59e0b', 'Done': '#10b981' };

const sprintDetails = {
    name: 'Sprint Alpha – v2.4',
    duration: 'Feb 10 – Feb 24, 2026 (2 weeks)',
    goal: 'Complete user authentication overhaul and deploy CI/CD pipeline for staging.',
    productOwner: 'Rajesh Mehta',
    scrumMaster: 'Arjun Patel',
};

export default function SprintOverview() {
    const [activeTab, setActiveTab] = useState('board');
    const [stories, setStories] = useState([]);
    const sprintMetrics = {
        plannedSP: 120,
        completedSP: stories.filter(s => s.status === 'Done').reduce((a, s) => a + (s.points || 0), 0) || 98,
        spillover: 18.3, alignmentAvg: 87.5, approvalTimeAvg: '4.2 hrs',
    };

    useEffect(() => {
        storiesAPI.getAll().then(data => { if (data?.length) setStories(data); }).catch(() => { });
    }, []);

    const grouped = {};
    statusColumns.forEach(s => { grouped[s] = stories.filter(st => st.status === s); });
    const completionPct = ((sprintMetrics.completedSP / sprintMetrics.plannedSP) * 100).toFixed(1);

    return (
        <div>
            {/* KPI Row */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Target size={24} />} value={`${sprintMetrics.completedSP}/${sprintMetrics.plannedSP}`} label="Story Points" trend={`${completionPct}% done`} trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<TrendingUp size={24} />} value={`${sprintMetrics.alignmentAvg}%`} label="Alignment Average" trend="+2.3% vs last" trendDir="up" color="green" delay={0.08} />
                <StatsCard icon={<Clock size={24} />} value={sprintMetrics.approvalTimeAvg} label="Avg Approval Time" trend="-1.1 hrs" trendDir="down" color="orange" delay={0.16} />
                <StatsCard icon={<AlertCircle size={24} />} value={`${sprintMetrics.spillover}%`} label="Spillover Rate" trend="Target < 15%" trendDir="up" color="red" delay={0.24} />
            </div>

            {/* Sprint Details Card */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Sprint Details</span>
                    <span className="badge badge-info">Active</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 20 }}>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Sprint Name</div>
                            <div style={{ fontWeight: 700, fontSize: '1rem' }}>{sprintDetails.name}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Duration</div>
                            <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}><Calendar size={14} /> {sprintDetails.duration}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Product Owner</div>
                            <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}><User size={14} /> {sprintDetails.productOwner}</div>
                        </div>
                        <div>
                            <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Scrum Master</div>
                            <div style={{ fontWeight: 600, display: 'flex', alignItems: 'center', gap: 6 }}><User size={14} /> {sprintDetails.scrumMaster}</div>
                        </div>
                    </div>
                    <div style={{ marginTop: 20, padding: '14px 18px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', borderLeft: '4px solid #3b82f6' }}>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Sprint Goal</div>
                        <div style={{ fontWeight: 500, lineHeight: 1.5 }}>{sprintDetails.goal}</div>
                    </div>
                </div>
            </AnimatedCard>

            {/* Story Status Board */}
            <AnimatedCard delay={0.4} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title">Story Status Board</span>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <button className={`btn btn-sm ${activeTab === 'board' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setActiveTab('board')}>Board</button>
                        <button className={`btn btn-sm ${activeTab === 'list' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setActiveTab('list')}>List</button>
                    </div>
                </div>
                <div className="card-body">
                    {activeTab === 'board' ? (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
                            {statusColumns.map(col => (
                                <div key={col}>
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, paddingBottom: 8, borderBottom: `3px solid ${statusColors[col]}` }}>
                                        <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{col}</span>
                                        <span className="badge" style={{ background: statusColors[col], color: '#fff', fontSize: '0.7rem' }}>{grouped[col].length}</span>
                                    </div>
                                    {grouped[col].map(story => (
                                        <div key={story.id} style={{ padding: '12px', marginBottom: 8, background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                            <div style={{ fontSize: '0.7rem', color: statusColors[col], fontWeight: 700, marginBottom: 4 }}>{story.id}</div>
                                            <div style={{ fontWeight: 600, fontSize: '0.82rem', marginBottom: 6 }}>{story.title}</div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                                                <span>{story.assignee}</span>
                                                <span>{story.points} SP</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="table-wrapper">
                            <table className="table">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Title</th>
                                        <th>Assignee</th>
                                        <th>Points</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {stories.map(s => (
                                        <tr key={s.id}>
                                            <td style={{ fontWeight: 600, color: '#3b82f6' }}>{s.id}</td>
                                            <td style={{ fontWeight: 500 }}>{s.title}</td>
                                            <td>{s.assignee}</td>
                                            <td>{s.points}</td>
                                            <td><span className="badge" style={{ background: statusColors[s.status], color: '#fff' }}>{s.status}</span></td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </AnimatedCard>
        </div>
    );
}
