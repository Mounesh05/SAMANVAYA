import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Activity, Server, AlertTriangle, CheckCircle } from 'lucide-react';
import {
    LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
    AreaChart, Area
} from 'recharts';
import { devopsAPI } from '../../services/api';

const depStatusColor = { healthy: '#10b981', degraded: '#f59e0b', unhealthy: '#ef4444' };
const getUtilColor = (v) => v >= 80 ? '#ef4444' : v >= 60 ? '#f59e0b' : '#10b981';

export default function DevOpsSystemHealth() {
    const [services, setServices] = useState([]);
    const [uptimeHistory, setUptimeHistory] = useState([]);
    const [slaBreaches, setSlaBreaches] = useState([]);
    const [dependencies, setDependencies] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        devopsAPI.systemHealth().then(data => {
            if (!data) return;
            if (Array.isArray(data)) {
                setServices(data);
            } else {
                if (data.services) setServices(data.services);
                if (data.uptime_history) setUptimeHistory(data.uptime_history);
                if (data.sla_breaches) setSlaBreaches(data.sla_breaches);
                if (data.dependencies) setDependencies(data.dependencies);
            }
        }).catch(err => {
            console.error('Failed to load system health', err);
        }).finally(() => {
            setLoading(false);
        });
    }, []);

    const avgUptime = services.length
        ? (services.reduce((a, s) => a + (Number(s.uptime) || 0), 0) / services.length).toFixed(2)
        : '100.00';
    const criticalServices = services.filter(s => (s.cpu || 0) > 70 || (s.memory || 0) > 80).length;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Activity size={24} />} value={`${avgUptime}%`} label="Avg Uptime" trend="Healthy" trendDir="up" color="green" delay={0} />
                <StatsCard icon={<Server size={24} />} value={services.length} label="Services Monitored" color="blue" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={criticalServices} label="Critical CPU/Mem" color="red" delay={0.16} />
                <StatsCard icon={<CheckCircle size={24} />} value={slaBreaches.length} label="SLA Breaches" color="orange" delay={0.24} />
            </div>

            {/* Resource Usage Table */}
            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Service Resource Usage</span>
                    <span className="badge badge-neutral">{services.length} services</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Service</th><th>CPU %</th><th>Memory %</th><th>Disk I/O %</th>
                                    <th>DB Latency (ms)</th><th>API Response (ms)</th><th>Uptime %</th>
                                </tr>
                            </thead>
                            <tbody>
                                {services.length === 0 && !loading && (
                                    <tr>
                                        <td colSpan={7} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                            No monitored services registered yet.
                                        </td>
                                    </tr>
                                )}
                                {services.map((s, i) => (
                                    <tr key={s.id || s.name || i}>
                                        <td style={{ fontWeight: 700, fontSize: '0.85rem' }}>{s.name}</td>
                                        {['cpu', 'memory', 'diskIO'].map(k => (
                                            <td key={k}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                    <div style={{ width: 50, height: 5, borderRadius: 3, background: '#e5e7eb' }}>
                                                        <div style={{ height: '100%', borderRadius: 3, width: `${s[k] || 0}%`, background: getUtilColor(s[k] || 0), transition: 'width 0.5s' }} />
                                                    </div>
                                                    <span style={{ fontWeight: 700, fontSize: '0.78rem', color: getUtilColor(s[k] || 0) }}>{s[k] || 0}%</span>
                                                </div>
                                            </td>
                                        ))}
                                        <td style={{ fontWeight: 600, fontSize: '0.82rem', color: (s.dbLatency || 0) > 30 ? '#ef4444' : (s.dbLatency || 0) > 15 ? '#f59e0b' : '#10b981' }}>
                                            {s.dbLatency != null ? `${s.dbLatency}ms` : '—'}
                                        </td>
                                        <td>
                                            {s.apiResponse != null ? (
                                                <span style={{ fontWeight: 600, fontSize: '0.82rem', color: s.apiResponse > 200 ? '#ef4444' : s.apiResponse > 100 ? '#f59e0b' : '#10b981' }}>
                                                    {s.apiResponse}ms
                                                </span>
                                            ) : <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>N/A</span>}
                                        </td>
                                        <td>
                                            <span style={{
                                                fontWeight: 700, fontSize: '0.82rem',
                                                color: (s.uptime || 0) >= 99.95 ? '#10b981' : (s.uptime || 0) >= 99.5 ? '#f59e0b' : '#ef4444'
                                            }}>{s.uptime != null ? `${s.uptime}%` : '100%'}</span>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            <div className="grid-2 mb-lg" style={{ marginTop: 16 }}>
                {/* Uptime History */}
                <AnimatedCard delay={0.4}>
                    <div className="card-header"><span className="card-title">Historical Uptime</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <AreaChart data={uptimeHistory}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[99.5, 100]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Area type="monotone" dataKey="uptime" stroke="#10b981" fill="#10b98120" strokeWidth={2.5} name="Uptime %" />
                                </AreaChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                {/* Service Dependency Map */}
                <AnimatedCard delay={0.48}>
                    <div className="card-header"><span className="card-title">Service Dependency Map</span></div>
                    <div className="card-body">
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                            {dependencies.length === 0 && (
                                <div style={{ textAlign: 'center', padding: 16, color: 'var(--text-tertiary)', fontSize: '0.82rem' }}>
                                    No service dependencies recorded.
                                </div>
                            )}
                            {dependencies.map((d, i) => (
                                <div key={i} style={{
                                    display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                                    borderRadius: 'var(--radius-sm)', background: 'var(--bg-page)', fontSize: '0.82rem'
                                }}>
                                    <span style={{ fontWeight: 700, minWidth: 100 }}>{d.from}</span>
                                    <span style={{ color: depStatusColor[d.status] || '#10b981', fontWeight: 600 }}>→</span>
                                    <span style={{ fontWeight: 600 }}>{d.to}</span>
                                    <span style={{ marginLeft: 'auto' }}>
                                        <span className="badge" style={{
                                            background: d.status === 'healthy' ? '#ecfdf5' : d.status === 'degraded' ? '#fffbeb' : '#fef2f2',
                                            color: depStatusColor[d.status] || '#10b981', fontWeight: 600
                                        }}>
                                            {d.status === 'healthy' ? '🟢' : d.status === 'degraded' ? '🟡' : '🔴'} {d.status}
                                        </span>
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </AnimatedCard>
            </div>

            {/* SLA Breaches */}
            {slaBreaches.length > 0 && (
                <AnimatedCard delay={0.56}>
                    <div className="card-header">
                        <span className="card-title">SLA Breach Alerts</span>
                        <span className="badge badge-danger">{slaBreaches.length}</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        {slaBreaches.map((b, i) => (
                            <div key={i} style={{
                                padding: '12px 16px', borderRadius: 'var(--radius-sm)',
                                background: b.severity === 'High' ? '#fef2f2' : '#fffbeb',
                                borderLeft: `3px solid ${b.severity === 'High' ? '#ef4444' : '#f59e0b'}`,
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <div>
                                        <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{b.service}</span>
                                        <span style={{ fontSize: '0.82rem', marginLeft: 8, color: 'var(--text-secondary)' }}>— {b.breach}</span>
                                    </div>
                                    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{b.time}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </AnimatedCard>
            )}
        </div>
    );
}
