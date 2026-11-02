import { useState, useEffect } from 'react';
import { Play, UploadCloud, Server, Activity, AlertTriangle } from 'lucide-react';
import { dashboardAPI } from '../../services/api';
import StatsCard from '../../components/StatsCard';
import AnimatedCard from '../../components/AnimatedCard';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';

const pStat = { Running: 'badge-info', Passed: 'badge-success', Failed: 'badge-danger' };

export default function DevOpsDashboard() {
    const [pipelines, setPipelines] = useState([]);
    const [deployments, setDeployments] = useState([]);
    const [healthData, setHealthData] = useState([]);
    const [alerts, setAlerts] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        dashboardAPI.devops().then(data => {
            if (!data) return;
            if (data.pipelines) setPipelines(data.pipelines);
            if (data.deployments) setDeployments(data.deployments);
            if (data.health_data) setHealthData(data.health_data);
            if (data.alerts) setAlerts(data.alerts);
        }).catch(err => console.error('Failed to fetch DevOps dashboard:', err))
            .finally(() => setLoading(false));
    }, []);

    if (loading) return <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>Loading dashboard...</div>;

    const avgUptimeVal = healthData.length ? (healthData.reduce((acc, h) => acc + (h.uptime || 0), 0) / healthData.length).toFixed(2) : '99.9';
    const runningPipelines = pipelines.filter(p => p.status === 'Running').length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Play size={24} />} value={pipelines.length} label="Pipelines" trend={runningPipelines > 0 ? `${runningPipelines} running` : "None running"} color="blue" delay={0} />
                <StatsCard icon={<UploadCloud size={24} />} value={deployments.length} label="Recent Deployments" color="green" delay={0.08} />
                <StatsCard icon={<Server size={24} />} value={healthData.length} label="Services Monitored" color="orange" delay={0.16} />
                <StatsCard icon={<Activity size={24} />} value={`${avgUptimeVal}%`} label="Avg Uptime" trend="Healthy" trendDir="up" color="green" delay={0.24} />
            </div>
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0.3}>
                    <div className="card-header"><span className="card-title">Pipelines</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table"><thead><tr><th>Pipeline</th><th>Branch</th><th>Status</th><th>Duration</th></tr></thead>
                            <tbody>{pipelines.map(p => <tr key={p.id}><td style={{ fontWeight: 600 }}>{p.name}</td><td style={{ fontFamily: "'Courier New',monospace", fontSize: '0.82rem' }}>{p.branch}</td><td><span className={`badge ${pStat[p.status]}`}>{p.status}</span></td><td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{p.duration}</td></tr>)}</tbody></table>
                    </div>
                </AnimatedCard>
                <AnimatedCard delay={0.38}>
                    <div className="card-header"><span className="card-title">Recent Deployments</span></div>
                    <div className="card-body" style={{ padding: 0 }}>
                        <table className="table"><thead><tr><th>Service</th><th>Env</th><th>Version</th><th>Status</th></tr></thead>
                            <tbody>{deployments.map(d => <tr key={d.id}><td style={{ fontWeight: 600 }}>{d.service}</td><td><span className="badge badge-neutral">{d.env}</span></td><td style={{ fontFamily: "'Courier New',monospace" }}>{d.version}</td><td><span className={`badge ${d.status === 'Success' ? 'badge-success' : 'badge-danger'}`}>{d.status}</span></td></tr>)}</tbody></table>
                    </div>
                </AnimatedCard>
            </div>
            <div className="grid-2">
                <AnimatedCard delay={0.46}>
                    <div className="card-header"><span className="card-title">System Health</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={healthData}><CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" /><XAxis dataKey="service" tick={{ fontSize: 11 }} /><YAxis tick={{ fontSize: 12 }} /><Tooltip /><Legend /><Bar dataKey="cpu" fill="#3b82f6" radius={[4, 4, 0, 0]} name="CPU %" /><Bar dataKey="memory" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Memory %" /></BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
                <AnimatedCard delay={0.54}>
                    <div className="card-header"><span className="card-title">Logs & Alerts</span><span className="badge badge-danger">{alerts.length}</span></div>
                    <div className="card-body">
                        <div className="timeline">
                            {alerts.map(a => <div key={a.id} className="timeline-item"><div className="timeline-item-title"><span className={`badge badge-${a.level}`} style={{ marginRight: 8 }}>{a.level === 'danger' ? '✕' : a.level === 'warning' ? '⚠' : 'ℹ'}</span>{a.msg}</div><div className="timeline-item-time">{a.time}</div></div>)}
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
