import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { FileText, Download, Plus, CheckCircle } from 'lucide-react';
import { reportsAPI } from '../../services/api';

export default function ReportsPage() {
    const [reports, setReports] = useState([]);
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [exporting, setExporting] = useState(false);
    const [exportSuccess, setExportSuccess] = useState(false);

    const loadData = async () => {
        try {
            setLoading(true);
            const [repData, metricData] = await Promise.all([
                reportsAPI.getAll().catch(() => []),
                reportsAPI.getMetrics().catch(() => ({})),
            ]);
            setReports(Array.isArray(repData) ? repData : []);
            if (metricData?.chart_data?.length) {
                setChartData(metricData.chart_data);
            } else if (metricData?.trend?.length) {
                setChartData(metricData.trend);
            }
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const types = ['Engineering', 'Performance', 'Finance', 'DevOps', 'QA', 'Executive'];
            const randomType = types[Math.floor(Math.random() * types.length)];
            const dateStr = new Date().toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
            const newDoc = {
                title: `${randomType} Progress Summary`,
                type: randomType,
                date: dateStr,
                generated_at: new Date().toISOString(),
                status: 'Completed'
            };
            const res = await reportsAPI.create(newDoc);
            if (res?.data) {
                setReports(prev => [res.data, ...prev]);
            } else {
                await loadData();
            }
        } catch (err) {
            console.error('Failed to generate report', err);
        } finally {
            setGenerating(false);
        }
    };

    const handleExportAll = () => {
        setExporting(true);
        setTimeout(() => {
            const dataStr = 'data:text/json;charset=utf-8,' + encodeURIComponent(JSON.stringify(reports, null, 2));
            const dlAnchor = document.createElement('a');
            dlAnchor.setAttribute('href', dataStr);
            dlAnchor.setAttribute('download', `reports_export_${new Date().toISOString().slice(0, 10)}.json`);
            document.body.appendChild(dlAnchor);
            dlAnchor.click();
            dlAnchor.remove();
            setExporting(false);
            setExportSuccess(true);
            setTimeout(() => setExportSuccess(false), 3000);
        }, 600);
    };

    const handleDownloadReport = (r) => {
        const reportContent = JSON.stringify(r, null, 2);
        const blob = new Blob([reportContent], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `${(r.title || 'report').replace(/\s+/g, '_').toLowerCase()}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    };

    return (
        <div>
            <div className="grid-2 mb-lg">
                <AnimatedCard delay={0}>
                    <div className="card-header">
                        <span className="card-title">Report Generation Trend</span>
                    </div>
                    <div className="card-body">
                        <div className="chart-container">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={chartData}>
                                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                                    <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                                    <YAxis tick={{ fontSize: 12 }} />
                                    <Tooltip />
                                    <Bar dataKey="generated" fill="#c0392b" radius={[4, 4, 0, 0]} name="Reports" />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </div>
                </AnimatedCard>
                <AnimatedCard delay={0.1}>
                    <div className="card-header">
                        <span className="card-title">Quick Actions</span>
                    </div>
                    <div className="card-body" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                        <button
                            className="btn btn-primary w-full"
                            onClick={handleGenerate}
                            disabled={generating}
                        >
                            {generating ? <FileText size={16} className="spin" /> : <Plus size={16} />}
                            {generating ? 'Generating Report...' : 'Generate New Report'}
                        </button>
                        <button
                            className="btn btn-secondary w-full"
                            onClick={handleExportAll}
                            disabled={exporting || reports.length === 0}
                        >
                            {exportSuccess ? <CheckCircle size={16} color="var(--success)" /> : <Download size={16} />}
                            {exporting ? 'Exporting...' : exportSuccess ? 'Export Complete!' : 'Export All Reports'}
                        </button>
                        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', textAlign: 'center', marginTop: 8 }}>
                            Reports are auto-generated weekly and persisted dynamically in the platform database.
                        </p>
                    </div>
                </AnimatedCard>
            </div>
            <AnimatedCard delay={0.2}>
                <div className="card-header">
                    <span className="card-title">All Reports</span>
                    <span className="badge badge-neutral">
                        {loading ? 'Loading...' : `${reports.length} reports`}
                    </span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <table className="table">
                        <thead>
                            <tr>
                                <th>Report</th>
                                <th>Type</th>
                                <th>Date</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {reports.length === 0 && !loading && (
                                <tr>
                                    <td colSpan={4} style={{ textAlign: 'center', padding: 24, color: 'var(--text-tertiary)' }}>
                                        No reports found. Click "Generate New Report" to create one.
                                    </td>
                                </tr>
                            )}
                            {reports.map((r, i) => (
                                <tr key={r.id || r._id || i}>
                                    <td style={{ fontWeight: 600 }}>{r.title}</td>
                                    <td>
                                        <span className="badge badge-neutral">{r.type}</span>
                                    </td>
                                    <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                                        {r.date || r.generated_at?.slice(0, 10) || 'Recent'}
                                    </td>
                                    <td>
                                        <button
                                            className="btn btn-sm btn-secondary"
                                            title="Download Report"
                                            onClick={() => handleDownloadReport(r)}
                                        >
                                            <Download size={14} />
                                        </button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </AnimatedCard>
        </div>
    );
}
