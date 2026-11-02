import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { GitPullRequest, CheckCircle, XCircle, AlertTriangle, Cpu, MessageSquare, Play, X } from 'lucide-react';
import { devAPI } from '../../services/api';

const reviewColors = {
    Approved: { bg: '#ecfdf5', color: '#10b981' },
    'In Review': { bg: '#eff6ff', color: '#3b82f6' },
    Open: { bg: '#fffbeb', color: '#f59e0b' },
    'Changes Requested': { bg: '#fef2f2', color: '#ef4444' },
};
const getColor = (v) => v >= 80 ? '#10b981' : v >= 60 ? '#f59e0b' : '#ef4444';

export default function DevPullRequests() {
    const [pullRequests, setPullRequests] = useState([]);
    const [selected, setSelected] = useState(null);

    useEffect(() => {
        devAPI.pullRequests().then(data => { if (Array.isArray(data)) setPullRequests(data); }).catch(() => { });
    }, []);

    const passCount = pullRequests.filter(p => p.ci === 'Pass').length;
    const failCount = pullRequests.filter(p => p.ci === 'Fail').length;
    const avgAlignment = pullRequests.length ? Math.round(pullRequests.reduce((a, p) => a + p.alignment, 0) / pullRequests.length) : 0;

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<GitPullRequest size={24} />} value={pullRequests.length} label="Total PRs" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={passCount} label="CI Passing" color="green" delay={0.08} />
                <StatsCard icon={<XCircle size={24} />} value={failCount} label="CI Failing" color="red" delay={0.16} />
                <StatsCard icon={<Cpu size={24} />} value={`${avgAlignment}%`} label="Avg Alignment" color="orange" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Pull Requests</span>
                    <span className="badge badge-info">{pullRequests.length} PRs</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>PR ID</th><th>Story</th><th>Alignment</th>
                                    <th>Review Status</th><th>CI Status</th><th>Changes</th>
                                    <th>Comments</th><th>AI Risk</th>
                                </tr>
                            </thead>
                            <tbody>
                                {pullRequests.map(pr => (
                                    <tr key={pr.id} onClick={() => setSelected(pr)} style={{ cursor: 'pointer' }}>
                                        <td>
                                            <span style={{ fontWeight: 700, fontSize: '0.85rem', color: 'var(--brand-primary)' }}>{pr.id}</span>
                                        </td>
                                        <td>
                                            <div style={{ fontWeight: 600, fontSize: '0.82rem' }}>{(pr.story || pr.title || '').split(' – ')[1] || pr.story || pr.title}</div>
                                            <div style={{ fontSize: '0.7rem', color: 'var(--text-tertiary)' }}>{(pr.story || pr.title || '').split(' – ')[0]}</div>
                                        </td>
                                        <td>
                                            <span style={{ fontWeight: 700, color: getColor(pr.alignment) }}>{pr.alignment}%</span>
                                        </td>
                                        <td>
                                            <span className="badge" style={{
                                                background: (reviewColors[pr.reviewStatus] || reviewColors.Open).bg,
                                                color: (reviewColors[pr.reviewStatus] || reviewColors.Open).color
                                            }}>{pr.reviewStatus}</span>
                                        </td>
                                        <td>
                                            {pr.ci === 'Pass' ? (
                                                <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#10b981', fontWeight: 600, fontSize: '0.82rem' }}>
                                                    <CheckCircle size={14} /> Pass
                                                </span>
                                            ) : (
                                                <span style={{ display: 'flex', alignItems: 'center', gap: 4, color: '#ef4444', fontWeight: 600, fontSize: '0.82rem' }}>
                                                    <XCircle size={14} /> Fail
                                                </span>
                                            )}
                                        </td>
                                        <td>
                                            <span style={{ fontSize: '0.78rem' }}>
                                                <span style={{ color: '#10b981', fontWeight: 600 }}>+{pr.additions}</span>{' '}
                                                <span style={{ color: '#ef4444', fontWeight: 600 }}>-{pr.deletions}</span>
                                            </span>
                                        </td>
                                        <td>
                                            <span style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: '0.82rem' }}>
                                                <MessageSquare size={13} /> {pr.comments.length}
                                            </span>
                                        </td>
                                        <td style={{ maxWidth: 200 }}>
                                            {pr.aiRisk ? (
                                                <div style={{
                                                    fontSize: '0.75rem', color: '#4c1d95', background: '#f5f3ff',
                                                    padding: '6px 10px', borderRadius: 'var(--radius-sm)',
                                                    border: '1px solid #e9d5ff'
                                                }}>
                                                    <Cpu size={10} style={{ display: 'inline', marginRight: 4 }} />
                                                    {pr.aiRisk}
                                                </div>
                                            ) : (
                                                <span style={{ color: 'var(--text-tertiary)', fontSize: '0.78rem' }}>—</span>
                                            )}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* PR Detail Modal */}
            {selected && (
                <div style={{
                    position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
                    background: 'rgba(0,0,0,0.5)', zIndex: 1000,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    animation: 'fadeIn 0.2s ease'
                }} onClick={() => setSelected(null)}>
                    <div onClick={e => e.stopPropagation()} style={{
                        background: '#fff', borderRadius: 'var(--radius-lg)', width: '90%', maxWidth: 600,
                        maxHeight: '80vh', overflow: 'auto', boxShadow: 'var(--shadow-xl)',
                        animation: 'fadeInUp 0.3s ease'
                    }}>
                        <div style={{
                            padding: '20px 24px', borderBottom: '1px solid var(--border-light)',
                            display: 'flex', justifyContent: 'space-between', alignItems: 'center'
                        }}>
                            <div>
                                <div style={{ fontWeight: 800, fontSize: '1.1rem', color: 'var(--brand-primary)' }}>{selected.id}</div>
                                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 2 }}>{selected.story}</div>
                            </div>
                            <button onClick={() => setSelected(null)} style={{
                                cursor: 'pointer', background: 'var(--bg-page)', border: 'none',
                                borderRadius: '50%', width: 32, height: 32,
                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                            }}><X size={16} /></button>
                        </div>
                        <div style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 16 }}>
                            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                                <div style={{ padding: '10px 16px', background: 'var(--bg-page)', borderRadius: 'var(--radius-sm)', flex: 1 }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Alignment</div>
                                    <div style={{ fontWeight: 800, fontSize: '1.2rem', color: getColor(selected.alignment) }}>{selected.alignment}%</div>
                                </div>
                                <div style={{ padding: '10px 16px', background: 'var(--bg-page)', borderRadius: 'var(--radius-sm)', flex: 1 }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>CI</div>
                                    <div style={{ fontWeight: 700, fontSize: '1rem', color: selected.ci === 'Pass' ? '#10b981' : '#ef4444' }}>
                                        {selected.ci === 'Pass' ? '✅ Pass' : '❌ Fail'}
                                    </div>
                                </div>
                                <div style={{ padding: '10px 16px', background: 'var(--bg-page)', borderRadius: 'var(--radius-sm)', flex: 1 }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>Files</div>
                                    <div style={{ fontWeight: 700, fontSize: '1rem' }}>{selected.files} files</div>
                                </div>
                            </div>
                            {selected.aiRisk && (
                                <div style={{
                                    padding: '12px 16px', background: '#f5f3ff', borderRadius: 'var(--radius-sm)',
                                    border: '1px solid #e9d5ff', borderLeft: '3px solid #7c3aed'
                                }}>
                                    <div style={{ fontWeight: 700, fontSize: '0.82rem', color: '#7c3aed', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 4 }}>
                                        <Cpu size={13} /> AI Risk Note
                                    </div>
                                    <div style={{ fontSize: '0.82rem', color: '#4c1d95' }}>{selected.aiRisk}</div>
                                </div>
                            )}
                            {selected.comments.length > 0 && (
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 8, color: 'var(--text-secondary)' }}>
                                        Review Comments ({selected.comments.length})
                                    </div>
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                                        {selected.comments.map((c, i) => (
                                            <div key={i} style={{
                                                padding: '10px 14px',
                                                background: c.author === 'AI Review' ? '#f5f3ff' : '#f9fafb',
                                                border: `1px solid ${c.author === 'AI Review' ? '#e9d5ff' : 'var(--border-light)'}`,
                                                borderRadius: 'var(--radius-sm)'
                                            }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                                                    <span style={{ fontWeight: 700, fontSize: '0.8rem', color: c.author === 'AI Review' ? '#7c3aed' : 'var(--text-primary)' }}>
                                                        {c.author}
                                                    </span>
                                                    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{c.time}</span>
                                                </div>
                                                <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{c.text}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
