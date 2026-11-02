import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import { FileText, Download, BarChart3, Shield, Activity, Users, MessageSquare, Loader2, Sparkles } from 'lucide-react';
import { reportsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

const ICON_MAP = {
    'BarChart3': <BarChart3 size={24} />,
    'Users': <Users size={24} />,
    'Shield': <Shield size={24} />,
    'Activity': <Activity size={24} />,
    'MessageSquare': <MessageSquare size={24} />
};

export default function CEOReports() {
    const { user, currentCompany } = useAuth();
    const [reportsData, setReportsData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [exportingId, setExportingId] = useState(null);
    const [toastMessage, setToastMessage] = useState(null);

    useEffect(() => {
        reportsAPI.getAll('CEO')
            .then(data => {
                if (Array.isArray(data)) setReportsData(data);
            })
            .catch(err => console.error('Failed to fetch CEO reports:', err))
            .finally(() => setLoading(false));
    }, []);

    const handleExportPdf = async (r) => {
        setExportingId(r.id);
        try {
            await reportsAPI.exportPdf(r, 'CEO', currentCompany?.id || currentCompany?.company_id || 'ORG-001');
            setToastMessage(`AI ReAct analysis complete! Downloaded "${r.title}".`);
        } catch (err) {
            console.error('PDF export failed:', err);
            alert('Failed to generate AI report PDF. Please check server logs.');
        } finally {
            setExportingId(null);
        }
    };

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>
                <Loader2 size={32} className="spin" style={{ marginBottom: 12 }} />
                <div>Loading executive reports...</div>
            </div>
        );
    }

    return (
        <div>
            {toastMessage && (
                <ConfirmToast
                    message={toastMessage}
                    onConfirm={() => setToastMessage(null)}
                    onCancel={() => setToastMessage(null)}
                    variant="info"
                />
            )}

            <AnimatedCard delay={0.1}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <span className="card-title">Available Executive Reports</span>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                            Real-time AI ReAct agent synthesizes live MongoDB metrics with Ollama LLM and compiles PDF downloads.
                        </div>
                    </div>
                    <span className="badge badge-info">{reportsData.length} Reports</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gap: 16 }}>
                        {reportsData.map((r, i) => {
                            const isExporting = exportingId === r.id;
                            return (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '20px 24px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)', transition: 'all 0.2s ease' }}>
                                    <div style={{ width: 52, height: 52, borderRadius: 'var(--radius-md)', background: `${r.color}15`, color: r.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        {ICON_MAP[r.icon] || <FileText size={24} />}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 4 }}>{r.title}</div>
                                        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{r.desc}</div>
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span>Last generated: {r.lastGenerated}</span>
                                            <span>•</span>
                                            <span style={{ color: '#3b82f6', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                                                <Sparkles size={11} /> AI ReAct Enabled
                                            </span>
                                        </div>
                                    </div>
                                    <button
                                        className="btn btn-sm btn-primary"
                                        style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0, minWidth: 150, justifyContent: 'center' }}
                                        onClick={() => handleExportPdf(r)}
                                        disabled={isExporting}
                                    >
                                        {isExporting ? (
                                            <>
                                                <Loader2 size={14} className="spin" /> Analyzing with AI...
                                            </>
                                        ) : (
                                            <>
                                                <Download size={14} /> Export PDF (AI)
                                            </>
                                        )}
                                    </button>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
