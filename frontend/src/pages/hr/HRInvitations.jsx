import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import { UserPlus, Users, Clock, CheckCircle, XCircle, Mail, Filter, X, Briefcase } from 'lucide-react';
import { hrAPI } from '../../services/api';
import ConfirmToast from '../../components/ConfirmToast';

const availableRoles = ['Project Manager', 'Scrum Master', 'Developer', 'DevOps Engineer', 'QA Engineer', 'HR Manager'];
const departments = ['Engineering', 'Operations', 'Quality', 'Human Resources', 'Management'];
const projects = ['Sprint Alpha', 'Sprint Beta', 'Sprint Gamma', 'Sprint Delta'];

const statusColors = { Screening: '#6b7280', Interview: '#3b82f6', 'Offer Sent': '#f59e0b', Hired: '#10b981', Rejected: '#ef4444' };

export default function HRInvitations() {
    const [candidates, setCandidates] = useState([]);
    const [showForm, setShowForm] = useState(false);
    const [roleFilter, setRoleFilter] = useState('All');
    const [statusFilter, setStatusFilter] = useState('All');
    const [newCandidate, setNewCandidate] = useState({ name: '', email: '', role: '', dept: '', project: '', experience: '' });

    useEffect(() => {
        hrAPI.hrCandidates().then(data => { if (data?.length) setCandidates(data); }).catch(() => { });
    }, []);

    const filteredCandidates = candidates.filter(c => {
        if (roleFilter !== 'All' && c.role !== roleFilter) return false;
        if (statusFilter !== 'All' && c.status !== statusFilter) return false;
        return true;
    });

    const handleAddCandidate = (e) => {
        e.preventDefault();
        const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const candidate = {
            id: Date.now(),
            ...newCandidate,
            appliedDate: today,
            status: 'Screening',
        };
        setCandidates(prev => [candidate, ...prev]);
        hrAPI.createCandidate(candidate).catch(err => console.error('Failed to create candidate:', err));
        setNewCandidate({ name: '', email: '', role: '', dept: '', project: '', experience: '' });
        setShowForm(false);
    };

    const handleStatusChange = (id, newStatus) => {
        setCandidates(prev => prev.map(c => c.id === id ? { ...c, status: newStatus } : c));
        hrAPI.updateCandidate(id, { status: newStatus }).catch(err => console.error('Failed to update candidate status:', err));
    };

    const [confirmRemove, setConfirmRemove] = useState(null);

    const handleRemove = (id) => {
        setConfirmRemove(id);
    };

    const handleConfirmRemove = async () => {
        const id = confirmRemove;
        setConfirmRemove(null);
        try {
            await hrAPI.deleteCandidate(id);
        } catch (err) {
            console.error('Failed to delete candidate:', err);
        }
        setCandidates(prev => prev.filter(c => c.id !== id));
    };

    return (
        <div>
            {confirmRemove && (
                <ConfirmToast
                    message="Are you sure you want to remove this candidate? This action cannot be undone."
                    onConfirm={handleConfirmRemove}
                    onCancel={() => setConfirmRemove(null)}
                />
            )}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Users size={24} />} value={candidates.length} label="Total Candidates" color="blue" delay={0} />
                <StatsCard icon={<Clock size={24} />} value={candidates.filter(c => c.status === 'Screening' || c.status === 'Interview').length} label="In Pipeline" color="orange" delay={0.08} />
                <StatsCard icon={<Mail size={24} />} value={candidates.filter(c => c.status === 'Offer Sent').length} label="Offers Sent" color="purple" delay={0.16} />
                <StatsCard icon={<CheckCircle size={24} />} value={candidates.filter(c => c.status === 'Hired').length} label="Hired" color="green" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header">
                    <span className="card-title">Hiring Pipeline</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        <Filter size={16} color="var(--text-tertiary)" />
                        <select value={roleFilter} onChange={e => setRoleFilter(e.target.value)}
                            style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                            <option value="All">All Roles</option>
                            {availableRoles.map(r => <option key={r} value={r}>{r}</option>)}
                        </select>
                        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                            style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}>
                            <option value="All">All Status</option>
                            <option value="Screening">Screening</option>
                            <option value="Interview">Interview</option>
                            <option value="Offer Sent">Offer Sent</option>
                            <option value="Hired">Hired</option>
                            <option value="Rejected">Rejected</option>
                        </select>
                        <button className="btn btn-primary btn-sm" style={{ display: 'flex', alignItems: 'center', gap: 6 }} onClick={() => setShowForm(!showForm)}>
                            {showForm ? <X size={14} /> : <UserPlus size={14} />} {showForm ? 'Close' : 'Add Candidate'}
                        </button>
                    </div>
                </div>

                {/* Add Candidate Form */}
                {showForm && (
                    <div className="card-body" style={{ borderBottom: '1px solid var(--border-color)' }}>
                        <form onSubmit={handleAddCandidate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                            <div className="form-group">
                                <label className="form-label">Full Name *</label>
                                <input className="form-input" placeholder="e.g. John Doe" value={newCandidate.name} onChange={e => setNewCandidate({ ...newCandidate, name: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Email *</label>
                                <input className="form-input" type="email" placeholder="john@example.com" value={newCandidate.email} onChange={e => setNewCandidate({ ...newCandidate, email: e.target.value })} required />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Experience</label>
                                <input className="form-input" placeholder="e.g. 5 years" value={newCandidate.experience} onChange={e => setNewCandidate({ ...newCandidate, experience: e.target.value })} />
                            </div>
                            <div className="form-group">
                                <label className="form-label">Role *</label>
                                <select className="form-select" value={newCandidate.role} onChange={e => setNewCandidate({ ...newCandidate, role: e.target.value })} required>
                                    <option value="">Select Role</option>
                                    {availableRoles.map(r => <option key={r} value={r}>{r}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Department *</label>
                                <select className="form-select" value={newCandidate.dept} onChange={e => setNewCandidate({ ...newCandidate, dept: e.target.value })} required>
                                    <option value="">Select Department</option>
                                    {departments.map(d => <option key={d} value={d}>{d}</option>)}
                                </select>
                            </div>
                            <div className="form-group">
                                <label className="form-label">Assign to Project</label>
                                <select className="form-select" value={newCandidate.project} onChange={e => setNewCandidate({ ...newCandidate, project: e.target.value })}>
                                    <option value="">Select Project</option>
                                    {projects.map(p => <option key={p} value={p}>{p}</option>)}
                                </select>
                            </div>
                            <div style={{ gridColumn: '1 / -1' }}>
                                <button className="btn btn-primary" type="submit"><UserPlus size={16} /> Add Candidate</button>
                            </div>
                        </form>
                    </div>
                )}

                {/* Candidates Table */}
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Email</th>
                                    <th>Role</th>
                                    <th>Department</th>
                                    <th>Project</th>
                                    <th>Experience</th>
                                    <th>Applied</th>
                                    <th>Status</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredCandidates.map(c => (
                                    <tr key={c.id}>
                                        <td style={{ fontWeight: 600, fontSize: '0.85rem' }}>{c.name}</td>
                                        <td style={{ fontSize: '0.82rem' }}>{c.email}</td>
                                        <td><span className="badge badge-info">{c.role}</span></td>
                                        <td style={{ fontSize: '0.82rem' }}>{c.dept}</td>
                                        <td style={{ fontSize: '0.82rem' }}>{c.project || '—'}</td>
                                        <td style={{ fontSize: '0.82rem' }}>{c.experience}</td>
                                        <td style={{ fontSize: '0.8rem' }}>{c.appliedDate}</td>
                                        <td>
                                            <select value={c.status} onChange={e => handleStatusChange(c.id, e.target.value)}
                                                style={{
                                                    padding: '4px 8px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.78rem',
                                                    fontWeight: 600, color: statusColors[c.status], background: `${statusColors[c.status]}10`
                                                }}>
                                                <option value="Screening">Screening</option>
                                                <option value="Interview">Interview</option>
                                                <option value="Offer Sent">Offer Sent</option>
                                                <option value="Hired">Hired</option>
                                                <option value="Rejected">Rejected</option>
                                            </select>
                                        </td>
                                        <td>
                                            <button className="btn btn-sm btn-secondary" title="Remove" onClick={() => handleRemove(c.id)} style={{ padding: '4px 8px', color: '#ef4444' }}>
                                                <XCircle size={13} />
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                {filteredCandidates.length === 0 && (
                                    <tr><td colSpan={9} style={{ textAlign: 'center', padding: 32, color: 'var(--text-tertiary)' }}>No candidates found.</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>
        </div>
    );
}
