import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { FileText, Download, BarChart2, Bug, FlaskConical, Shield, CheckCircle } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, Legend } from 'recharts';
import { qaAPI } from '../../services/api';

const ICON_MAP = {
    Sprint: <BarChart2 size={16} />,
    Bugs: <Bug size={16} />,
    Release: <Shield size={16} />,
    Regression: <FlaskConical size={16} />,
};

export default function QAReports() {
    const [reports, setReports] = useState([]);
    const [bugTrend, setBugTrend] = useState([]);
    const [qualityTrend, setQualityTrend] = useState([]);
    const [exporting, setExporting] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        qaAPI.reports().then(data => {
            if (!data) return;
            let reportList = [];
            if (Array.isArray(data)) {
                reportList = data;
            } else if (data.reports) {
                reportList = data.reports;
                if (data.bug_trend) setBugTrend(data.bug_trend);
                if (data.quality_trend) setQualityTrend(data.quality_trend);
            }
            if (reportList.length) {
                setReports(reportList.map(r => ({
                    ...r,
                    icon: ICON_MAP[r.category] || <FileText size={16} />
                })));
            }
        }).catch(err => {
            console.error('Failed to load QA reports', err);
        }).finally(() => {
            setLoading(false);
        });
    }, []);

    const handleExport = (report) => {
        const id = report.id || report._id;
        setExporting(id);
        setTimeout(() => {
            const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(report, null, 2));
            const dlAnchor = document.createElement('a');
            dlAnchor.setAttribute('href', dataStr);
            dlAnchor.setAttribute('download', `${(report.name || 'qa-report').replace(/\s+/g, '_').toLowerCase()}.json`);
            document.body.appendChild(dlAnchor);
            dlAnchor.click();
            dlAnchor.remove();
            setExporting(null);
        }, 800);
    };

    const latestSprint = qualityTrend[qualityTrend.length - 1]?.sprint || 'Sprint 12';
    const latestQuality = qualityTrend[qualityTrend.length - 1]?.score ? `${qualityTrend[qualityTrend.length - 1].score}%` : '85%';

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<FileText size={24} />} value={reports.length} label="Available Reports" color="blue" delay={0} />
                <StatsCard icon={<Download size={24} />} value="JSON/CSV" label="Export Formats" color="green" delay={0.08} />
                <StatsCard icon={<BarChart2 size={24} />} value={latestSprint} label="Current Period" color="orange" delay={0.16} />
                <StatsCard icon={<Shield size={24} />} value={latestQuality} label="Quality Score" color="green" delay={0.24} />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(380px, 1fr))', gap: 16, marginBottom: 16 }}>
                {reports.map((r, idx) => (
                    <AnimatedCard key={r.id || idx} delay={0.3 + idx * 0.08}>
                        <div className="card-header" style={{ borderBottom: `2px solid ${r.color || '#3b82f6'}20` }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <div style={{
                                    width: 32, height: 32, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    background: `${r.color || '#3b82f6'}15`, color: r.color || '#3b82f6'
                                }}>{r.icon}</div>
                                <div>
                                    <span className="card-title" style={{ fontSize: '0.9rem' }}>{r.name}</span>
                                    <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{r.category}</div>
                                </div>
                            </div>
                            <span className="badge badge-neutral" style={{ fontSize: '0.68rem' }}>{r.lastGenerated || 'Recent'}</span>
                        </div>
                        <div className="card-body">
                            <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 12, lineHeight: 1.5 }}>{r.description}</p>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 14 }}>
                                {(r.data || []).map((d, i) => (
                                    <div key={i} style={{
                                        padding: '8px 10px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-page)',
                                        display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                                    }}>
                                        <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{d.label}</span>
                                        <span style={{ fontSize: '0.82rem', fontWeight: 700, color: r.color || '#3b82f6' }}>{d.value}</span>
                                    </div>
                                ))}
                            </div>
                            <button
                                onClick={() => handleExport(r)}
                                disabled={exporting === (r.id || r._id)}
                                style={{
                                    width: '100%', padding: '8px 16px', borderRadius: 'var(--radius-sm)',
                                    background: r.color || '#3b82f6',
                                    color: '#fff', border: 'none', fontWeight: 600, fontSize: '0.82rem', cursor: 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                                    opacity: exporting === (r.id || r._id) ? 0.6 : 1, transition: 'all 0.15s ease'
                                }}
                            >
                                <Download size={14} /> {exporting === (r.id || r._id) ? 'Exporting...' : 'Export Report'}
                            </button>
                        </div>
                    </AnimatedCard>
                ))}
            </div>

            <div className="grid-2">
                <AnimatedCard delay={0.65}>
                    <div className="card-header"><span className="card-title">Bug Trend</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={bugTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip /><Legend />
                                    <Bar dataKey="found" fill="#ef4444" radius={[4, 4, 0, 0]} name="Found" />
                                    <Bar dataKey="resolved" fill="#10b981" radius={[4, 4, 0, 0]} name="Resolved" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>

                <AnimatedCard delay={0.73}>
                    <div className="card-header"><span className="card-title">Quality Trend</span></div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={qualityTrend}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="sprint" tick={{ fontSize: 12 }} />
                                    <YAxis domain={[60, 100]} tick={{ fontSize: 12 }} />
                                    <Tooltip formatter={(v) => `${v}%`} />
                                    <Line type="monotone" dataKey="score" stroke="#3b82f6" strokeWidth={2.5} dot={{ r: 5, fill: '#3b82f6' }} name="Quality %" />
                                </LineChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
            </div>
        </div>
    );
}
