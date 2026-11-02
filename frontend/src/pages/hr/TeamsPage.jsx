import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import {
    Shield, Users, Plus, Edit2, Trash2, Loader2, Search, Filter,
    CheckCircle, X, UserPlus, UserMinus, Crown, Briefcase, Building2,
    Layers, ArrowRight
} from 'lucide-react';
import { teamsAPI, employeesAPI, projectsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

export default function TeamsPage() {
    const { user } = useAuth();

    const [teams, setTeams] = useState([]);
    const [employees, setEmployees] = useState([]);
    const [projects, setProjects] = useState([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [deptFilter, setDeptFilter] = useState('All');

    // Modals
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [editingTeam, setEditingTeam] = useState(null);
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [managingMembersTeam, setManagingMembersTeam] = useState(null);
    const [toastMessage, setToastMessage] = useState(null);

    // Form states for Create
    const [newTeam, setNewTeam] = useState({
        name: '',
        team_id: '',
        department: 'Engineering',
        description: '',
        team_lead_id: '',
        project_ids: []
    });

    // Form state for Adding Member in Managing Members Modal
    const [selectedEmployeeToAdd, setSelectedEmployeeToAdd] = useState('');

    const currentActor = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';

    const loadData = async () => {
        try {
            setLoading(true);
            const [tms, emps, prjs] = await Promise.all([
                teamsAPI.getAll().catch(() => []),
                employeesAPI.getAll().catch(() => []),
                projectsAPI.getAll().catch(() => [])
            ]);
            setTeams(Array.isArray(tms) ? tms : []);
            setEmployees(Array.isArray(emps) ? emps : []);
            setProjects(Array.isArray(prjs) ? prjs : []);
        } catch (err) {
            console.error('Failed to load teams data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, []);

    // ── CREATE TEAM ──
    const handleCreateTeam = async (e) => {
        e.preventDefault();
        if (!newTeam.name.trim()) return;

        const payload = {
            name: newTeam.name.trim(),
            team_id: newTeam.team_id.trim() || undefined,
            department: newTeam.department || 'Engineering',
            description: newTeam.description.trim(),
            team_lead_id: newTeam.team_lead_id || undefined,
            project_ids: newTeam.project_ids || []
        };

        try {
            await teamsAPI.create(payload);
            setToastMessage(`Team "${payload.name}" created successfully by ${currentActor}!`);
            setShowCreateModal(false);
            setNewTeam({ name: '', team_id: '', department: 'Engineering', description: '', team_lead_id: '', project_ids: [] });
            await loadData();
        } catch (err) {
            console.error('Failed to create team:', err);
            alert(err?.message || 'Failed to create team. Ensure Team ID is unique.');
        }
    };

    // ── UPDATE TEAM ──
    const handleUpdateTeam = async (e) => {
        e.preventDefault();
        if (!editingTeam) return;

        const targetId = editingTeam.team_id || editingTeam._id || editingTeam.id;
        const payload = {
            name: editingTeam.name,
            description: editingTeam.description,
            department: editingTeam.department,
            team_lead_id: editingTeam.team_lead_id || undefined,
            project_ids: editingTeam.project_ids || [],
            is_active: editingTeam.is_active !== undefined ? editingTeam.is_active : true
        };

        try {
            await teamsAPI.update(targetId, payload);
            setToastMessage(`Team "${editingTeam.name}" updated successfully!`);
            setEditingTeam(null);
            await loadData();
        } catch (err) {
            console.error('Failed to update team:', err);
            alert('Failed to update team details.');
        }
    };

    // ── DELETE TEAM ──
    const handleConfirmDelete = async () => {
        const id = confirmDeleteId;
        setConfirmDeleteId(null);
        try {
            await teamsAPI.delete(id);
            setToastMessage(`Team ${id} deleted successfully.`);
            await loadData();
        } catch (err) {
            console.error('Failed to delete team:', err);
            alert('Failed to delete team.');
        }
    };

    // ── MEMBERS MANAGEMENT ──
    const openManageMembers = (team) => {
        setManagingMembersTeam(team);
        setSelectedEmployeeToAdd('');
    };

    const handleAddMember = async () => {
        if (!selectedEmployeeToAdd || !managingMembersTeam) return;
        const teamId = managingMembersTeam.team_id || managingMembersTeam.id;
        try {
            await teamsAPI.addMember(teamId, selectedEmployeeToAdd);
            setToastMessage(`Employee ${selectedEmployeeToAdd} assigned to squad ${managingMembersTeam.name}`);
            setSelectedEmployeeToAdd('');
            await loadData();
            // Refresh modal team object
            const updated = await teamsAPI.getById(teamId);
            if (updated) setManagingMembersTeam(updated);
        } catch (err) {
            console.error('Failed to add team member:', err);
            alert('Failed to assign team member.');
        }
    };

    const handleRemoveMember = async (employeeId) => {
        if (!managingMembersTeam) return;
        const teamId = managingMembersTeam.team_id || managingMembersTeam.id;
        try {
            await teamsAPI.removeMember(teamId, employeeId);
            setToastMessage(`Employee removed from squad ${managingMembersTeam.name}`);
            await loadData();
            // Refresh modal team object
            const updated = await teamsAPI.getById(teamId);
            if (updated) setManagingMembersTeam(updated);
        } catch (err) {
            console.error('Failed to remove team member:', err);
            alert('Failed to remove member.');
        }
    };

    // Derived stats
    const totalTeams = teams.length;
    const activeTeams = teams.filter(t => t.is_active !== false).length;
    const teamsWithLead = teams.filter(t => t.team_lead_id || t.team_lead_name).length;
    const totalMembersAllocated = employees.filter(e => e.team_id).length;

    // Filtered teams list
    const filteredTeams = teams.filter(t => {
        const matchSearch = !search ||
            (t.name && t.name.toLowerCase().includes(search.toLowerCase())) ||
            (t.team_id && t.team_id.toLowerCase().includes(search.toLowerCase())) ||
            (t.team_lead_name && t.team_lead_name.toLowerCase().includes(search.toLowerCase())) ||
            (t.department && t.department.toLowerCase().includes(search.toLowerCase()));

        const matchDept = deptFilter === 'All' || t.department === deptFilter;
        return matchSearch && matchDept;
    });

    const uniqueDepartments = ['All', ...new Set(teams.map(t => t.department || 'Engineering'))];

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>
                <Loader2 size={32} className="spin" style={{ marginBottom: 12 }} />
                <div>Loading enterprise engineering squads...</div>
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

            {confirmDeleteId && (
                <ConfirmToast
                    message={`Are you sure you want to permanently delete team "${confirmDeleteId}"? All member associations will be dissociated.`}
                    onConfirm={handleConfirmDelete}
                    onCancel={() => setConfirmDeleteId(null)}
                />
            )}

            {/* Metrics */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Shield size={24} />} value={totalTeams} label="Total Squads" color="blue" delay={0} />
                <StatsCard icon={<CheckCircle size={24} />} value={activeTeams} label="Active Squads" color="green" delay={0.08} />
                <StatsCard icon={<Crown size={24} />} value={teamsWithLead} label="Squads with Leads" color="purple" delay={0.16} />
                <StatsCard icon={<Users size={24} />} value={totalMembersAllocated} label="Allocated Members" color="orange" delay={0.24} />
            </div>

            {/* Main Content Card */}
            <AnimatedCard delay={0.2}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                    <div>
                        <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <Shield size={20} color="#3b82f6" />
                            Teams & Engineering Squads
                        </span>
                        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: 3 }}>
                            Multi-tenant squad directory, team lead assignments, and member allocation management.
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                        {/* Search */}
                        <div style={{ position: 'relative' }}>
                            <Search size={15} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-tertiary)' }} />
                            <input
                                type="text"
                                className="form-input"
                                placeholder="Search squads or leads..."
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                style={{ paddingLeft: 32, width: 200, fontSize: '0.82rem' }}
                            />
                        </div>

                        {/* Dept Filter */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Filter size={15} color="var(--text-tertiary)" />
                            <select
                                value={deptFilter}
                                onChange={e => setDeptFilter(e.target.value)}
                                style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}
                            >
                                {uniqueDepartments.map(d => (
                                    <option key={d} value={d}>{d}</option>
                                ))}
                            </select>
                        </div>

                        {/* Create Team Button */}
                        <button
                            className="btn btn-primary btn-sm"
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                            onClick={() => setShowCreateModal(true)}
                        >
                            <Plus size={15} /> Create Team
                        </button>
                    </div>
                </div>

                <div className="card-body" style={{ padding: 'var(--space-4)' }}>
                    {filteredTeams.length === 0 ? (
                        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)' }}>
                            <Shield size={36} style={{ marginBottom: 10, opacity: 0.5 }} />
                            <div style={{ fontWeight: 600 }}>No squads found</div>
                            <div style={{ fontSize: '0.82rem', marginTop: 4 }}>Try clearing search or click "Create Team" to form a squad.</div>
                        </div>
                    ) : (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 'var(--space-4)' }}>
                            {filteredTeams.map(t => {
                                const teamId = t.team_id || t.id;
                                const leadObj = employees.find(e => e.employee_id === t.team_lead_id || e.id === t.team_lead_id);
                                const leadName = t.team_lead_name || leadObj?.name || 'Unassigned';
                                const memberList = employees.filter(e => e.team_id === teamId);
                                const memberCount = memberList.length || t.member_count || 0;

                                return (
                                    <div
                                        key={teamId}
                                        style={{
                                            border: '1px solid var(--border-color)',
                                            borderRadius: 'var(--radius-md)',
                                            padding: '18px 20px',
                                            background: 'var(--bg-secondary)',
                                            display: 'flex',
                                            flexDirection: 'column',
                                            justifyContent: 'space-between',
                                            transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                                        }}
                                    >
                                        <div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                                                    <div style={{
                                                        width: 38,
                                                        height: 38,
                                                        borderRadius: 'var(--radius-md)',
                                                        background: 'rgba(59, 130, 246, 0.15)',
                                                        color: '#3b82f6',
                                                        display: 'flex',
                                                        alignItems: 'center',
                                                        justifyContent: 'center',
                                                        fontWeight: 700
                                                    }}>
                                                        <Layers size={20} />
                                                    </div>
                                                    <div>
                                                        <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--text-primary)' }}>
                                                            {t.name}
                                                        </div>
                                                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
                                                            <span className="badge badge-info" style={{ fontFamily: 'monospace', fontSize: '0.7rem' }}>
                                                                {teamId}
                                                            </span>
                                                            <span className="badge badge-secondary" style={{ fontSize: '0.7rem' }}>
                                                                {t.department || 'Engineering'}
                                                            </span>
                                                        </div>
                                                    </div>
                                                </div>

                                                <span className={`badge ${t.is_active !== false ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.7rem' }}>
                                                    {t.is_active !== false ? 'Active' : 'Inactive'}
                                                </span>
                                            </div>

                                            <p style={{
                                                fontSize: '0.82rem',
                                                color: 'var(--text-secondary)',
                                                lineHeight: 1.4,
                                                marginBottom: 16,
                                                minHeight: 36
                                            }}>
                                                {t.description || 'Enterprise delivery engineering squad.'}
                                            </p>

                                            {/* Details Grid */}
                                            <div style={{
                                                display: 'grid',
                                                gridTemplateColumns: '1fr 1fr',
                                                gap: 10,
                                                background: 'var(--bg-primary)',
                                                padding: '10px 14px',
                                                borderRadius: 'var(--radius-sm)',
                                                border: '1px solid var(--border-color)',
                                                marginBottom: 16
                                            }}>
                                                <div>
                                                    <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                                        Team Lead
                                                    </div>
                                                    <div style={{ fontWeight: 600, fontSize: '0.82rem', color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                                                        <Crown size={12} color="#f59e0b" />
                                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{leadName}</span>
                                                    </div>
                                                </div>

                                                <div>
                                                    <div style={{ fontSize: '0.68rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                                        Members
                                                    </div>
                                                    <div style={{ fontWeight: 600, fontSize: '0.82rem', color: '#3b82f6', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
                                                        <Users size={12} /> {memberCount} Engineer{memberCount !== 1 ? 's' : ''}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Actions footer */}
                                        <div style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'space-between',
                                            borderTop: '1px solid var(--border-color)',
                                            paddingTop: 12,
                                            marginTop: 4
                                        }}>
                                            <button
                                                className="btn btn-sm btn-secondary"
                                                style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: '0.75rem', padding: '5px 10px' }}
                                                onClick={() => openManageMembers(t)}
                                            >
                                                <Users size={13} /> Manage Members
                                            </button>

                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    style={{ padding: '5px 8px' }}
                                                    onClick={() => setEditingTeam({ ...t })}
                                                    title="Edit Squad Details"
                                                >
                                                    <Edit2 size={13} />
                                                </button>
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    style={{ padding: '5px 8px', color: '#ef4444' }}
                                                    onClick={() => setConfirmDeleteId(teamId)}
                                                    title="Delete Squad"
                                                >
                                                    <Trash2 size={13} />
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>
            </AnimatedCard>

            {/* CREATE TEAM MODAL */}
            {showCreateModal && (
                <div style={{
                    position: 'fixed',
                    top: 0, left: 0, right: 0, bottom: 0,
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
                        borderRadius: 16,
                        border: '1px solid #e2e8f0',
                        padding: '28px 32px',
                        width: '100%',
                        maxWidth: 540,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Shield size={20} color="#3b82f6" /> Create New Engineering Squad
                            </h3>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-tertiary)' }}
                            >
                                ✕
                            </button>
                        </div>

                        <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 20 }}>
                            HR and Leadership provision teams to organize engineers, sprint goals, and delivery workflows.
                        </p>

                        <form onSubmit={handleCreateTeam} style={{ display: 'grid', gap: 14 }}>
                            <div>
                                <label className="form-label">Team Name *</label>
                                <input
                                    className="form-input"
                                    placeholder="e.g. Core Architecture Squad"
                                    value={newTeam.name}
                                    onChange={e => setNewTeam({ ...newTeam, name: e.target.value })}
                                    required
                                />
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <div>
                                    <label className="form-label">Team ID (Optional)</label>
                                    <input
                                        className="form-input"
                                        placeholder={`e.g. team-0${teams.length + 1}`}
                                        value={newTeam.team_id}
                                        onChange={e => setNewTeam({ ...newTeam, team_id: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Department</label>
                                    <select
                                        className="form-input"
                                        value={newTeam.department}
                                        onChange={e => setNewTeam({ ...newTeam, department: e.target.value })}
                                    >
                                        <option value="Engineering">Engineering</option>
                                        <option value="Product">Product</option>
                                        <option value="QA & Testing">QA & Testing</option>
                                        <option value="DevOps & Cloud">DevOps & Cloud</option>
                                        <option value="AI & Intelligence">AI & Intelligence</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="form-label">Description</label>
                                <textarea
                                    className="form-input"
                                    rows={2}
                                    placeholder="Team mission and technical responsibilities..."
                                    value={newTeam.description}
                                    onChange={e => setNewTeam({ ...newTeam, description: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="form-label">Assign Team Lead</label>
                                <select
                                    className="form-input"
                                    value={newTeam.team_lead_id}
                                    onChange={e => setNewTeam({ ...newTeam, team_lead_id: e.target.value })}
                                >
                                    <option value="">-- No Lead Assigned --</option>
                                    {employees.map(e => (
                                        <option key={e.employee_id || e.id} value={e.employee_id || e.id}>
                                            {e.name} ({e.role || 'Engineer'} - {e.employee_id || e.id})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setShowCreateModal(false)}
                                >
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary">
                                    Create Team
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* EDIT TEAM MODAL */}
            {editingTeam && (
                <div style={{
                    position: 'fixed',
                    top: 0, left: 0, right: 0, bottom: 0,
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
                        borderRadius: 16,
                        border: '1px solid #e2e8f0',
                        padding: '28px 32px',
                        width: '100%',
                        maxWidth: 540,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                <Edit2 size={18} color="#3b82f6" /> Edit Squad: {editingTeam.name}
                            </h3>
                            <button
                                onClick={() => setEditingTeam(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-tertiary)' }}
                            >
                                ✕
                            </button>
                        </div>

                        <form onSubmit={handleUpdateTeam} style={{ display: 'grid', gap: 14 }}>
                            <div>
                                <label className="form-label">Team Name *</label>
                                <input
                                    className="form-input"
                                    value={editingTeam.name || ''}
                                    onChange={e => setEditingTeam({ ...editingTeam, name: e.target.value })}
                                    required
                                />
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                <div>
                                    <label className="form-label">Department</label>
                                    <input
                                        className="form-input"
                                        value={editingTeam.department || ''}
                                        onChange={e => setEditingTeam({ ...editingTeam, department: e.target.value })}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Status</label>
                                    <select
                                        className="form-input"
                                        value={editingTeam.is_active !== false ? 'Active' : 'Inactive'}
                                        onChange={e => setEditingTeam({ ...editingTeam, is_active: e.target.value === 'Active' })}
                                    >
                                        <option value="Active">Active</option>
                                        <option value="Inactive">Inactive</option>
                                    </select>
                                </div>
                            </div>

                            <div>
                                <label className="form-label">Description</label>
                                <textarea
                                    className="form-input"
                                    rows={2}
                                    value={editingTeam.description || ''}
                                    onChange={e => setEditingTeam({ ...editingTeam, description: e.target.value })}
                                />
                            </div>

                            <div>
                                <label className="form-label">Reassign Team Lead</label>
                                <select
                                    className="form-input"
                                    value={editingTeam.team_lead_id || ''}
                                    onChange={e => setEditingTeam({ ...editingTeam, team_lead_id: e.target.value })}
                                >
                                    <option value="">-- No Lead Assigned --</option>
                                    {employees.map(e => (
                                        <option key={e.employee_id || e.id} value={e.employee_id || e.id}>
                                            {e.name} ({e.role || 'Engineer'} - {e.employee_id || e.id})
                                        </option>
                                    ))}
                                </select>
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 12 }}>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setEditingTeam(null)}
                                >
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary">
                                    Save Changes
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MANAGE MEMBERS MODAL */}
            {managingMembersTeam && (
                <div style={{
                    position: 'fixed',
                    top: 0, left: 0, right: 0, bottom: 0,
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
                        borderRadius: 16,
                        border: '1px solid #e2e8f0',
                        padding: '28px 32px',
                        width: '100%',
                        maxWidth: 600,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                            <div>
                                <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <Users size={18} color="#3b82f6" /> Squad Members: {managingMembersTeam.name}
                                </h3>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                                    Manage engineers assigned to this delivery team.
                                </div>
                            </div>
                            <button
                                onClick={() => setManagingMembersTeam(null)}
                                style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-tertiary)' }}
                            >
                                ✕
                            </button>
                        </div>

                        {/* Add Member Row */}
                        <div style={{
                            display: 'flex',
                            gap: 10,
                            marginBottom: 20,
                            padding: 14,
                            background: 'var(--bg-secondary)',
                            borderRadius: 'var(--radius-md)',
                            border: '1px solid var(--border-color)'
                        }}>
                            <select
                                className="form-input"
                                style={{ flex: 1, fontSize: '0.85rem' }}
                                value={selectedEmployeeToAdd}
                                onChange={e => setSelectedEmployeeToAdd(e.target.value)}
                            >
                                <option value="">-- Select Engineer to Assign --</option>
                                {employees
                                    .filter(e => e.team_id !== (managingMembersTeam.team_id || managingMembersTeam.id))
                                    .map(e => (
                                        <option key={e.employee_id || e.id} value={e.employee_id || e.id}>
                                            {e.name} ({e.role || 'Dev'} - {e.team_id ? `Currently: ${e.team_id}` : 'Unassigned'})
                                        </option>
                                    ))}
                            </select>
                            <button
                                className="btn btn-primary"
                                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 14px', fontSize: '0.85rem' }}
                                onClick={handleAddMember}
                                disabled={!selectedEmployeeToAdd}
                            >
                                <UserPlus size={15} /> Assign
                            </button>
                        </div>

                        {/* Current Members List */}
                        <div style={{ maxHeight: 280, overflowY: 'auto', border: '1px solid var(--border-color)', borderRadius: 'var(--radius-md)' }}>
                            {employees.filter(e => e.team_id === (managingMembersTeam.team_id || managingMembersTeam.id)).length === 0 ? (
                                <div style={{ textAlign: 'center', padding: 36, color: 'var(--text-tertiary)', fontSize: '0.85rem' }}>
                                    No members currently assigned to this squad.
                                </div>
                            ) : (
                                <table className="table" style={{ margin: 0 }}>
                                    <thead>
                                        <tr>
                                            <th>Engineer</th>
                                            <th>Role</th>
                                            <th>Employee ID</th>
                                            <th style={{ textAlign: 'right' }}>Action</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {employees
                                            .filter(e => e.team_id === (managingMembersTeam.team_id || managingMembersTeam.id))
                                            .map(member => (
                                                <tr key={member.employee_id || member.id}>
                                                    <td>
                                                        <div style={{ fontWeight: 600, fontSize: '0.85rem' }}>
                                                            {member.name}
                                                            {member.employee_id === managingMembersTeam.team_lead_id && (
                                                                <span className="badge badge-warning" style={{ marginLeft: 6, fontSize: '0.65rem' }}>
                                                                    Lead
                                                                </span>
                                                            )}
                                                        </div>
                                                    </td>
                                                    <td>
                                                        <span className="badge badge-info" style={{ fontSize: '0.72rem' }}>
                                                            {member.role || 'Engineer'}
                                                        </span>
                                                    </td>
                                                    <td style={{ fontFamily: 'monospace', fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                                                        {member.employee_id || member.id}
                                                    </td>
                                                    <td style={{ textAlign: 'right' }}>
                                                        <button
                                                            className="btn btn-sm btn-secondary"
                                                            style={{ color: '#ef4444', padding: '3px 8px', fontSize: '0.75rem' }}
                                                            onClick={() => handleRemoveMember(member.employee_id || member.id)}
                                                            title="Remove from squad"
                                                        >
                                                            <UserMinus size={13} />
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}
                                    </tbody>
                                </table>
                            )}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: 18 }}>
                            <button
                                className="btn btn-secondary"
                                onClick={() => setManagingMembersTeam(null)}
                            >
                                Done
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
