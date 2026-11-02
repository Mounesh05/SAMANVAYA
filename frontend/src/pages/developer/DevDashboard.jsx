import { useState, useEffect } from 'react';
import { CheckSquare, GitBranch, GitPullRequest, Cpu } from 'lucide-react';
import { dashboardAPI } from '../../services/api';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

export default function DevDashboard() {
    const [myTasks, setMyTasks] = useState([]);
    const [activeBranches, setActiveBranches] = useState([]);
    const [pullRequests, setPullRequests] = useState([]);
    const [aiFeedback, setAiFeedback] = useState([]);
    const [progressData, setProgressData] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        dashboardAPI.developer().then(data => {
            if (!data) return;
            if (data.my_tasks?.length) setMyTasks(data.my_tasks);
            if (data.active_branches?.length) setActiveBranches(data.active_branches);
            if (data.pull_requests?.length) setPullRequests(data.pull_requests);
            if (data.ai_feedback?.length) setAiFeedback(data.ai_feedback);
            if (data.progress_history?.length) setProgressData(data.progress_history);
        }).catch(() => {
        }).finally(() => {
            setLoading(false);
        });
    }, []);

    const displayProgress = progressData.length ? progressData : [
        { day: 'Mon', tasks: 2 }, { day: 'Tue', tasks: 3 }, { day: 'Wed', tasks: 1 },
        { day: 'Thu', tasks: 4 }, { day: 'Fri', tasks: 3 }, { day: 'Sat', tasks: 0 }, { day: 'Sun', tasks: 1 },
    ];

    const sBadge = { 'In Progress': 'badge-info', 'To Do': 'badge-neutral', 'In Review': 'badge-warning', 'Done': 'badge-success' };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<CheckSquare size={24} />} value={myTasks.filter(t => t.status !== 'Done').length.toString()} label="Active Tasks" color="blue" delay={0} />
                <StatsCard icon={<GitBranch size={24} />} value={activeBranches.length.toString()} label="Active Branches" color="green" delay={0.08} />
                <StatsCard icon={<GitPullRequest size={24} />} value={pullRequests.length.toString()} label="Pull Requests" color="orange" delay={0.16} />
                <StatsCard icon={<Cpu size={24} />} value="92" label="AI Quality Score" trend="+4" trendDir="up" color="green" delay={0.24} />
            </div>
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header"><span className="card-title">My Tasks</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table"><thead><tr><th>Task</th><th>Status</th><th>Due</th></tr></thead>
                            <tbody>{myTasks.map(t => <tr key={t.id}><td><div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{t.title}</div><div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{t.project}</div></td><td><span className={`badge ${sBadge[t.status]}`}>{t.status}</span></td><td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{t.due}</td></tr>)}</tbody></table>
                    </div>
                </AnimatedCard>
                <AnimatedCard delay={0.38}>
                    <div className="card-header"><span className="card-title">Active Branches</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table"><thead><tr><th>Branch</th><th>Commits</th><th>Status</th></tr></thead>
                            <tbody>{activeBranches.map(b => <tr key={b.id}><td style={{ fontFamily: "'Courier New',monospace", fontWeight: 600, fontSize: '0.85rem' }}>{b.name}</td><td>{b.commits}</td><td><span className={`badge ${b.status === 'Ahead' ? 'badge-success' : b.status === 'Behind' ? 'badge-warning' : 'badge-info'}`}>{b.status}</span></td></tr>)}</tbody></table>
                    </div>
                    <div className="card-header" style={{ borderTop: '1px solid var(--border-light)' }}><span className="card-title">Pull Requests</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table"><tbody>{pullRequests.map(pr => <tr key={pr.id}><td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{pr.title}</td><td><span className={`badge ${pr.status === 'Approved' ? 'badge-success' : pr.status === 'Open' ? 'badge-info' : 'badge-warning'}`}>{pr.status}</span></td><td style={{ fontSize: '0.8rem' }}>💬 {pr.comments}</td></tr>)}</tbody></table>
                    </div>
                </AnimatedCard>
            </div>
            <div className="grid-2">
                <AnimatedCard delay={0.46}>
                    <div className="card-header"><span className="card-title">AI Feedback</span><span className="badge badge-info">AI</span></div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        {aiFeedback.map(fb => <div key={fb.id} style={{ padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: fb.type === 'success' ? 'var(--success-bg)' : fb.type === 'danger' ? 'var(--danger-bg)' : 'var(--warning-bg)', borderLeft: `3px solid ${fb.type === 'success' ? 'var(--success)' : fb.type === 'danger' ? 'var(--danger)' : 'var(--warning)'}` }}><div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: 4 }}>{fb.title}</div><div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{fb.desc}</div></div>)}
                    </div>
                </AnimatedCard>
                <AnimatedCard delay={0.54}>
                    <div className="card-header"><span className="card-title">Progress This Week</span></div>
                    <div className="card-body"><div className="chart-container"><ResponsiveContainer width="100%" height="100%"><LineChart data={displayProgress}><CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" /><XAxis dataKey="day" tick={{ fontSize: 12 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Line type="monotone" dataKey="tasks" stroke="#c0392b" strokeWidth={2.5} dot={{ r: 5, fill: '#c0392b' }} name="Tasks Done" /></LineChart></ResponsiveContainer></div></div>
                </AnimatedCard>
            </div>
        </div>
    );
}
