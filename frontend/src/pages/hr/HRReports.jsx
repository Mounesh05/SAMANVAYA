import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import { FileText, Download, BarChart3, Award, Star, AlertTriangle, UserPlus, Loader2, Sparkles } from 'lucide-react';
import { hrAPI, reportsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

const ICON_MAP = {
    'BarChart3': <BarChart3 size={24} />,
    'Award': <Award size={24} />,
    'Star': <Star size={24} />,
    'AlertTriangle': <AlertTriangle size={24} />,
    'UserPlus': <UserPlus size={24} />
};

export default function HRReports() {
    const { user, currentCompany } = useAuth();
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [exportingId, setExportingId] = useState(null);
    const [toastMessage, setToastMessage] = useState(null);

    useEffect(() => {
        hrAPI.hrReports()
            .then(data => {
                if (Array.isArray(data)) setReports(data);
            })
            .catch(err => console.error('Failed to fetch reports:', err))
            .finally(() => setLoading(false));
    }, []);

    const handleExportPdf = async (r) => {
        setExportingId(r.id);
        try {
            await reportsAPI.exportPdf(r, 'HR', currentCompany?.id || currentCompany?.company_id || 'ORG-001');
            setToastMessage(`AI ReAct analysis complete! Downloaded "${r.title}".`);
        } catch (err) {
            console.error('Failed to export PDF:', err);
            alert('Failed to generate AI report PDF. Please check server logs.');
        } finally {
            setExportingId(null);
        }
    };

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>
                <Loader2 size={32} className="spin" style={{ marginBottom: 12 }} />
                <div>Loading HR reports...</div>
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
                        <span className="card-title">People Operations & HR Intelligence Reports</span>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                            Instant ReAct LLM synthesis linking workforce telemetry with automated PDF executive briefings.
                        </div>
                    </div>
                    <span className="badge badge-info">{reports.length} Reports</span>
                </div>
                <div className="card-body">
                    <div style={{ display: 'grid', gap: 16 }}>
                        {reports.map((r, i) => {
                            const isExporting = exportingId === r.id;
                            return (
                                <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '20px 24px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-color)' }}>
                                    <div style={{ width: 52, height: 52, borderRadius: 'var(--radius-md)', background: `${r.color}15`, color: r.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                                        {ICON_MAP[r.icon] || <FileText size={24} />}
                                    </div>
                                    <div style={{ flex: 1 }}>
                                        <div style={{ fontWeight: 700, fontSize: '0.95rem', marginBottom: 4 }}>{r.title}</div>
                                        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>{r.desc}</div>
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 6, display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <span>Last generated: {r.lastGenerated}</span>
                                            <span>•</span>
                                            <span style={{ color: '#10b981', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                                                <Sparkles size={11} /> AI ReAct Synthesis
                                            </span>
                                        </div>
                                    </div>
                                    <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                                        <button
                                            className="btn btn-sm btn-primary"
                                            style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 140, justifyContent: 'center' }}
                                            onClick={() => handleExportPdf(r)}
                                            disabled={isExporting}
                                        >
                                            {isExporting ? (
                                                <>
                                                    <Loader2 size={13} className="spin" /> Analyzing with AI...
                                                </>
                                            ) : (
                                                <>
                                                    <Download size={14} /> PDF (AI)
                                                </>
                                            )}
                                        </button>
                                        <button
                                            className="btn btn-sm btn-secondary"
                                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                            onClick={() => alert(`Exporting ${r.title} as CSV...`)}
                                        >
                                            <Download size={14} /> CSV
                                        </button>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
