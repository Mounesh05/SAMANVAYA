import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Award, CheckCircle, Clock, PauseCircle, Send, ThumbsUp, Filter } from 'lucide-react';
import { employeesAPI, hrAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';


const verdictColors = { 'Strongly Recommend': '#10b981', 'Recommend': '#3b82f6', 'Not Recommended': '#ef4444' };
const decisionColors = { 'Promoted': '#10b981', 'Pending': '#f59e0b', 'Hold': '#ef4444', '—': '#94a3b8' };
const actionLabels = { 'Promoted': 'Promotion Approved', 'Pending': 'Sent to Review', 'Hold': 'Hold' };

export default function HRPromotions() {
    const { user } = useAuth();
    const navigate = useNavigate();
    const [data, setData] = useState([]);
    const [auditLog, setAuditLog] = useState([]);

    useEffect(() => {
        employeesAPI.getAll().then(emps => {
            setData(emps.map(e => ({
                id: e.id, name: e.name, role: e.role, perfScore: e.perfScore, behaviour: e.behaviour, risk: e.risk,
                aiVerdict: e.promotion?.aiVerdict || '—', managerReview: e.promotion?.managerReview || '—', finalDecision: e.promotion?.finalDecision || '—',
            })));
        }).catch(() => { });

        // Fetch audit log from DB
        hrAPI.auditLog().then(logs => {
            if (Array.isArray(logs) && logs.length) setAuditLog(logs);
        }).catch(() => { });
    }, []);

    const [roleFilter, setRoleFilter] = useState('All');
    const uniqueRoles = ['All', ...new Set(data.map(c => c.role))];
    const filteredData = roleFilter === 'All' ? data : data.filter(c => c.role === roleFilter);

    const handleAction = async (id, action) => {
        const candidate = data.find(c => c.id === id);
        if (!candidate) return;

        // Update local state
        setData(prev => prev.map(c => c.id === id ? { ...c, finalDecision: action } : c));

        // Create audit log entry
        const now = new Date();
        const timeStr = now.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
            ' ' + now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });

        const logEntry = {
            id: `audit-${Date.now()}`,
            action: actionLabels[action] || action,
            name: candidate.name,
            by: user?.name ? `${user.name} (${user.role || 'HR'})` : 'Alexander Sterling (CEO)',
            time: timeStr,
        };

        // Add to local state immediately (prepend for latest-first)
        setAuditLog(prev => [logEntry, ...prev]);

        // Persist to backend
        try {
            await hrAPI.createAuditLog(logEntry);
        } catch (err) {
            console.error('Failed to save audit log:', err);
        }
    };

    return (
        <div>
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Award size={24} />} value={data.filter(c => c.aiVerdict.includes('Recommend')).length} label="AI Recommended" color="green" delay={0} />
                <StatsCard icon={<ThumbsUp size={24} />} value={data.filter(c => c.finalDecision === 'Promoted').length} label="Promoted" color="blue" delay={0.08} />
                <StatsCard icon={<Clock size={24} />} value={data.filter(c => c.finalDecision === 'Pending' || c.finalDecision === '—').length} label="Pending" color="orange" delay={0.16} />
                <StatsCard icon={<PauseCircle size={24} />} value={data.filter(c => c.finalDecision === 'Hold').length} label="On Hold" color="red" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Promotion Recommendations</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Filter size={16} color="var(--text-tertiary)" />
                        <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
                            style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                            {uniqueRoles.map(r => <option key={r} value={r}>{r === 'All' ? 'All Roles' : r}</option>)}
                        </select>
                    </div>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Role</th>
                                    <th>Perf Score</th>
                                    <th>Behaviour (10%)</th>
                                    <th>Risk</th>
                                    <th>AI Verdict</th>
                                    <th>Manager Review</th>
                                    <th>Decision</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredData.map(c => (
                                    <tr key={c.id}>
                                        <td>
                                            <span style={{ fontWeight: 600, color: '#3b82f6', cursor: 'pointer', textDecoration: 'underline' }}
                                                onClick={() => navigate(`/employees/${c.id}`)}>
                                                {c.name}
                                            </span>
                                        </td>
                                        <td><span className="badge badge-neutral">{c.role}</span></td>
                                        <td><span style={{ fontWeight: 700, color: c.perfScore >= 80 ? '#10b981' : '#f59e0b' }}>{c.perfScore}%</span></td>
                                        <td><span style={{ fontWeight: 700 }}>{c.behaviour}/10</span></td>
                                        <td><span className="badge" style={{ background: c.risk === 'Low' ? '#10b981' : c.risk === 'Medium' ? '#f59e0b' : '#ef4444', color: '#fff' }}>{c.risk}</span></td>
                                        <td><span style={{ fontWeight: 600, color: verdictColors[c.aiVerdict] }}>{c.aiVerdict}</span></td>
                                        <td><span className="badge" style={{ background: c.managerReview === 'Approved' ? '#10b98120' : c.managerReview === 'Hold' ? '#ef444420' : '#f59e0b20', color: c.managerReview === 'Approved' ? '#10b981' : c.managerReview === 'Hold' ? '#ef4444' : '#f59e0b' }}>{c.managerReview}</span></td>
                                        <td><span className="badge" style={{ background: decisionColors[c.finalDecision], color: '#fff' }}>{c.finalDecision}</span></td>
                                        <td>
                                            <div style={{ display: 'flex', gap: 4 }}>
                                                <button className="btn btn-sm btn-secondary" title="Send to Review" onClick={() => handleAction(c.id, 'Pending')} style={{ padding: '3px 6px' }}><Send size={12} /></button>
                                                <button className="btn btn-sm btn-secondary" title="Approve" onClick={() => handleAction(c.id, 'Promoted')} style={{ padding: '3px 6px', color: '#10b981' }}><CheckCircle size={12} /></button>
                                                <button className="btn btn-sm btn-secondary" title="Hold" onClick={() => handleAction(c.id, 'Hold')} style={{ padding: '3px 6px', color: '#ef4444' }}><PauseCircle size={12} /></button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Audit Log */}
            <AnimatedCard delay={0.4} style={{ marginTop: 20 }}>
                <div className="card-header">
                    <span className="card-title">Promotion Audit Log</span>
                    <span className="badge badge-neutral">{auditLog.length} entries</span>
                </div>
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead><tr><th>Action</th><th>Employee</th><th>By</th><th>When</th></tr></thead>
                            <tbody>
                                {auditLog.map((log, i) => (
                                    <tr key={log.id || i}>
                                        <td><span className="badge" style={{ background: log.action === 'Promotion Approved' ? '#10b98120' : log.action === 'Hold' ? '#ef444420' : '#3b82f620', color: log.action === 'Promotion Approved' ? '#10b981' : log.action === 'Hold' ? '#ef4444' : '#3b82f6' }}>{log.action}</span></td>
                                        <td style={{ fontWeight: 600 }}>{log.name}</td>
                                        <td>{log.by}</td>
                                        <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{log.time}</td>
                                    </tr>
                                ))}
                                {auditLog.length === 0 && (
                                    <tr><td colSpan={4} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>No audit entries yet. Take promotion actions above to see them here.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
