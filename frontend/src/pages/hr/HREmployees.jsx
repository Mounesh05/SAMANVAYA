import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { Users, Search, UserCheck, AlertTriangle, TrendingUp, ArrowRightLeft, X, Check, Building2, ShieldCheck } from 'lucide-react';
import { employeesAPI, teamsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

const riskColors = { Low: '#10b981', Medium: '#f59e0b', High: '#ef4444' };
const statusColors = { Active: '#10b981', 'On Leave': '#3b82f6', Probation: '#f59e0b' };
const getScoreColor = (s) => s >= 80 ? '#10b981' : s >= 65 ? '#f59e0b' : '#ef4444';

export default function HREmployees() {
    const navigate = useNavigate();
    const { user, currentCompany } = useAuth();
    const [search, setSearch] = useState('');
    const [deptFilter, setDeptFilter] = useState('All');
    const [employees, setEmployees] = useState([]);
    const [teams, setTeams] = useState([]);
    const [loading, setLoading] = useState(true);

    // Transfer Modal State
    const [transferModal, setTransferModal] = useState(null); // holds selected employee
    const [targetTeam, setTargetTeam] = useState('');
    const [targetDept, setTargetDept] = useState('');
    const [transferReason, setTransferReason] = useState('');
    const [transferring, setTransferring] = useState(false);
    const [toastMessage, setToastMessage] = useState(null);

    const loadData = async () => {
        setLoading(true);
        try {
            const [emps, tms] = await Promise.all([
                employeesAPI.getAll(),
                teamsAPI.getAll()
            ]);
            setEmployees(Array.isArray(emps) ? emps : []);
            setTeams(Array.isArray(tms) ? tms : []);
        } catch (err) {
            console.error('Failed to load employee/team data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    const depts = ['All', ...new Set(employees.map(e => e.dept).filter(Boolean))];
    const filtered = employees.filter(e => {
        if (deptFilter !== 'All' && e.dept !== deptFilter) return false;
        if (search && !e.name.toLowerCase().includes(search.toLowerCase()) && !e.role.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
    });

    const openTransferModal = (emp, e) => {
        e.stopPropagation();
        setTransferModal(emp);
        setTargetTeam(emp.team_id || (teams[0] ? teams[0].team_id : ''));
        setTargetDept(emp.dept || 'Engineering');
        setTransferReason('');
    };

    const handleExecuteTransfer = async (e) => {
        e.preventDefault();
        if (!transferModal) return;
        setTransferring(true);
        
        const selectedTeamObj = teams.find(t => t.team_id === targetTeam) || { name: targetTeam };
        const performer = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';

        try {
            await employeesAPI.transferTeam(transferModal.employee_id || transferModal.id, {
                team_id: targetTeam,
                team_name: selectedTeamObj.name,
                dept: targetDept,
                transferred_by: performer,
                reason: transferReason || 'Organizational realignment',
                name: transferModal.name
            });
            
            setToastMessage(`Successfully transferred ${transferModal.name} to ${selectedTeamObj.name}`);
            setTransferModal(null);
            // Refresh employee data
            await loadData();
        } catch (err) {
            console.error('Failed to transfer employee:', err);
            alert('Failed to transfer employee team. Please try again.');
        } finally {
            setTransferring(false);
        }
    };

    return (
        <div>
            {toastMessage && (
                <ConfirmToast
                    message={toastMessage}
                    onConfirm={() => setToastMessage(null)}
                    onCancel={() => setToastMessage(null)}
                />
            )}

            {/* Top Metric Cards */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={employees.length} label="Total Employees" trend="+2 this month" trendDir="up" color="blue" delay={0} />
                <StatsCard icon={<UserCheck size={24} />} value={employees.filter(e => e.status === 'Active').length} label="Active" color="green" delay={0.08} />
                <StatsCard icon={<AlertTriangle size={24} />} value={employees.filter(e => e.risk === 'High').length} label="High Risk" color="red" delay={0.16} />
                <StatsCard icon={<TrendingUp size={24} />} value="82.3%" label="Avg Performance" trend="+1.8%" trendDir="up" color="purple" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <span className="card-title">Employee Directory</span>
                        {currentCompany && (
                            <span className="badge" style={{ background: '#3b82f620', color: '#3b82f6', fontWeight: 600 }}>
                                {currentCompany.name}
                            </span>
                        )}
                    </div>
                    <div style={{ display: 'flex', gap: 8 }}>
                        <div style={{ position: 'relative' }}>
                            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
                            <input
                                type="text"
                                placeholder="Search employee..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                style={{ paddingLeft: 30, padding: '6px 12px 6px 30px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem', width: 170 }}
                            />
                        </div>
                        <select
                            value={deptFilter}
                            onChange={e => setDeptFilter(e.target.value)}
                            style={{ padding: '6px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}
                        >
                            {depts.map(d => <option key={d} value={d}>{d}</option>)}
                        </select>
                    </div>
                </div>

                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Employee</th>
                                    <th>Department</th>
                                    <th>Assigned Team</th>
                                    <th>Project(s)</th>
                                    <th>Perf Score</th>
                                    <th>Behaviour</th>
                                    <th>Risk</th>
                                    <th>Status</th>
                                    <th>Actions / Transparency</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filtered.map(e => (
                                    <tr key={e.employee_id || e.id} onClick={() => navigate(`/employees/${e.employee_id || e.id}`)} style={{ cursor: 'pointer' }}>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                <div style={{ width: 34, height: 34, borderRadius: '50%', background: '#3b82f6', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, fontSize: '0.72rem', flexShrink: 0 }}>
                                                    {e.avatar || e.name.slice(0, 2).toUpperCase()}
                                                </div>
                                                <div>
                                                    <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>{e.name}</div>
                                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>{e.role} ({e.employee_id || e.id})</div>
                                                </div>
                                            </div>
                                        </td>
                                        <td>{e.dept}</td>
                                        <td>
                                            <span className="badge badge-info" style={{ fontWeight: 600, fontSize: '0.78rem' }}>
                                                {e.team_name || (teams.find(t => t.team_id === e.team_id)?.name) || 'Core Engineering Squad'}
                                            </span>
                                        </td>
                                        <td style={{ fontSize: '0.8rem', maxWidth: 180 }}>
                                            {Array.isArray(e.projects) && e.projects.length > 0 ? e.projects.join(', ') : 'Samanvaya AI Platform'}
                                        </td>
                                        <td><span style={{ fontWeight: 700, color: getScoreColor(e.perfScore || 85) }}>{e.perfScore || 85}%</span></td>
                                        <td><span style={{ fontWeight: 700, color: getScoreColor((e.behaviour || 8.5) * 10) }}>{e.behaviour || 8.5}/10</span></td>
                                        <td><span className="badge" style={{ background: riskColors[e.risk || 'Low'], color: '#fff' }}>{e.risk || 'Low'}</span></td>
                                        <td>
                                            <span className="badge" style={{ background: `${statusColors[e.status || 'Active']}20`, color: statusColors[e.status || 'Active'], fontWeight: 600 }}>
                                                {e.status || 'Active'}
                                            </span>
                                        </td>
                                        <td onClick={evt => evt.stopPropagation()}>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                                <button
                                                    className="btn btn-sm btn-primary"
                                                    style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '4px 10px', fontSize: '0.75rem', width: 'fit-content' }}
                                                    onClick={(evt) => openTransferModal(e, evt)}
                                                    title="Reassign employee to another team"
                                                >
                                                    <ArrowRightLeft size={12} /> Transfer Team
                                                </button>
                                                {e.transferred_by && (
                                                    <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 3 }}>
                                                        <ShieldCheck size={11} color="#10b981" /> Reassigned by {e.transferred_by}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {filtered.length === 0 && (
                                    <tr>
                                        <td colSpan={9} style={{ textAlign: 'center', padding: 40, color: 'var(--text-tertiary)' }}>
                                            No employees found matching the filters.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* Team Transfer Modal */}
            {transferModal && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(15, 23, 42, 0.72)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 9999,
                    backdropFilter: 'blur(8px)',
                    padding: 20
                }}>
                    <div style={{
                        background: '#ffffff',
                        border: '1px solid #e2e8f0',
                        borderRadius: 16,
                        width: '100%',
                        maxWidth: 480,
                        padding: 28,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <ArrowRightLeft size={18} color="#3b82f6" />
                                <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700 }}>Transfer Employee Team</h3>
                            </div>
                            <button
                                onClick={() => setTransferModal(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-tertiary)' }}
                            >
                                <X size={18} />
                            </button>
                        </div>

                        <div style={{ background: 'var(--bg-secondary)', padding: '12px 14px', borderRadius: 'var(--radius-sm)', marginBottom: 16, border: '1px solid var(--border-color)' }}>
                            <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{transferModal.name}</div>
                            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{transferModal.role} · Current Team: <strong>{transferModal.team_name || 'Core Engineering Squad'}</strong></div>
                        </div>

                        <form onSubmit={handleExecuteTransfer} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Reassign to Team *</label>
                                <select
                                    className="form-select"
                                    value={targetTeam}
                                    onChange={e => setTargetTeam(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                                >
                                    {teams.map(t => (
                                        <option key={t.team_id} value={t.team_id}>
                                            {t.name} ({t.dept || 'Engineering'})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Department *</label>
                                <select
                                    className="form-select"
                                    value={targetDept}
                                    onChange={e => setTargetDept(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', background: 'var(--bg-primary)', color: 'var(--text-primary)' }}
                                >
                                    <option value="Engineering">Engineering</option>
                                    <option value="Quality Assurance">Quality Assurance</option>
                                    <option value="Infrastructure & SRE">Infrastructure & SRE</option>
                                    <option value="Product">Product</option>
                                    <option value="Human Resources">Human Resources</option>
                                </select>
                            </div>

                            <div className="form-group">
                                <label className="form-label" style={{ fontWeight: 600, fontSize: '0.82rem' }}>Reassignment Reason / Transfer Notes *</label>
                                <textarea
                                    className="form-input"
                                    rows={3}
                                    placeholder="Explain the operational rationale (e.g. cross-sprint delivery focus, backend expertise needed)..."
                                    value={transferReason}
                                    onChange={e => setTransferReason(e.target.value)}
                                    required
                                    style={{ width: '100%', padding: '8px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem', resize: 'vertical' }}
                                />
                            </div>

                            {/* Transparent Actor Attribution */}
                            <div style={{ background: '#3b82f610', padding: '10px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid #3b82f630' }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    Audit Trail Attribution (Transparent):
                                </div>
                                <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#3b82f6', marginTop: 2 }}>
                                    Action by: {user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)'}
                                </div>
                            </div>

                            <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 10 }}>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setTransferModal(null)}
                                    disabled={transferring}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    disabled={transferring}
                                    style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                >
                                    <Check size={14} /> {transferring ? 'Transferring...' : 'Confirm Transfer'}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
