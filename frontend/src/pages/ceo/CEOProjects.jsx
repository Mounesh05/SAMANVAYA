import { useState, useEffect } from 'react';
import AnimatedCard from '../../components/AnimatedCard';
import StatsCard from '../../components/StatsCard';
import {
    FolderPlus, Folder, Users, Clock, CheckCircle, Play, Pause, X,
    Filter, Edit2, Trash2, Loader2, Building2, UserCheck, ShieldAlert
} from 'lucide-react';
import { projectsAPI, employeesAPI, sprintsAPI, companiesAPI, teamsAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

const statusColors = {
    Active: '#10b981',
    'On Hold': '#f59e0b',
    Completed: '#3b82f6',
    Cancelled: '#ef4444'
};

export default function CEOProjects() {
    const { user, currentCompany, companies } = useAuth();

    const [projects, setProjects] = useState([]);
    const [statusFilter, setStatusFilter] = useState('All');
    const [companyFilter, setCompanyFilter] = useState('All');
    const [loading, setLoading] = useState(true);

    // Modal states
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [editingProject, setEditingProject] = useState(null);
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [toastMessage, setToastMessage] = useState(null);

    // Reference options
    const [availablePMs, setAvailablePMs] = useState([]);
    const [sprintOptions, setSprintOptions] = useState([]);
    const [teamOptions, setTeamOptions] = useState([]);
    const [companyOptions, setCompanyOptions] = useState([]);

    // Form states
    const [newProject, setNewProject] = useState({
        name: '',
        description: '',
        client: '',
        sprint: '',
        assignedPM: '',
        company_id: '',
        team_name: ''
    });

    const loadData = async () => {
        try {
            const [projData, empData, sprData, compData, teamData] = await Promise.all([
                projectsAPI.getAll(),
                employeesAPI.getAll().catch(() => []),
                sprintsAPI.getAll().catch(() => []),
                companiesAPI.getAll().catch(() => []),
                teamsAPI.getAll().catch(() => [])
            ]);

            if (projData) setProjects(projData);

            if (empData) {
                const pms = empData
                    .filter(e => e.role === 'PM' || e.dept === 'Management')
                    .map(e => ({ id: e.employee_id || e.id, name: e.name }));
                setAvailablePMs(pms.length ? pms : [{ id: 'EMP-003', name: 'Marcus Vance' }, { id: 'EMP-004', name: 'Priya Sharma' }]);
            }

            if (sprData) setSprintOptions(sprData);
            if (compData) setCompanyOptions(compData);
            if (teamData) setTeamOptions(teamData);

            if (currentCompany && !newProject.company_id) {
                setNewProject(prev => ({ ...prev, company_id: currentCompany.id || currentCompany.company_id }));
            }
        } catch (err) {
            console.error('Failed to fetch project data:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
        const cid = currentCompany?.id || currentCompany?.company_id;
        if (cid) {
            setCompanyFilter(cid);
        }
    }, [currentCompany]);

    const currentActor = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';

    // CREATE
    const handleCreateProject = async (e) => {
        e.preventDefault();
        const today = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
        const companyId = newProject.company_id || currentCompany?.id || currentCompany?.company_id || 'ORG-001';
        const selectedCompany = companyOptions.find(c => (c.id || c.company_id) === companyId);
        const companyName = selectedCompany?.name || currentCompany?.name || 'Samanvaya Inc.';

        const projectPayload = {
            id: `PRJ-${String(projects.length + 1).padStart(2, '0')}-${Date.now().toString().slice(-4)}`,
            name: newProject.name,
            description: newProject.description,
            client: newProject.client,
            sprint: newProject.sprint || 'Sprint 42 (Current)',
            assignedPM: newProject.assignedPM || (availablePMs[0]?.name || 'Marcus Vance'),
            status: 'Active',
            createdDate: today,
            members: 4,
            company_id: companyId,
            org_id: companyId,
            company_name: companyName,
            team_names: newProject.team_name ? [newProject.team_name] : ['Core Platform Squad'],
            created_by: currentActor,
            updated_by: currentActor
        };

        try {
            await projectsAPI.create(projectPayload);
            setProjects(prev => [projectPayload, ...prev]);
            setToastMessage(`Project "${projectPayload.name}" created successfully by ${currentActor}!`);
            setShowCreateModal(false);
            setNewProject({ name: '', description: '', client: '', sprint: '', assignedPM: '', company_id: currentCompany?.id || currentCompany?.company_id || '', team_name: '' });
        } catch (err) {
            console.error('Failed to create project:', err);
            alert('Failed to create project. Please try again.');
        }
    };

    // UPDATE
    const handleUpdateProject = async (e) => {
        e.preventDefault();
        if (!editingProject) return;

        const companyId = editingProject.company_id || editingProject.org_id || 'ORG-001';
        const selectedCompany = companyOptions.find(c => (c.id || c.company_id) === companyId);

        const updatePayload = {
            name: editingProject.name,
            description: editingProject.description,
            client: editingProject.client,
            sprint: editingProject.sprint,
            assignedPM: editingProject.assignedPM,
            status: editingProject.status,
            company_id: companyId,
            org_id: companyId,
            company_name: selectedCompany?.name || editingProject.company_name || 'Samanvaya Inc.',
            team_names: Array.isArray(editingProject.team_names) ? editingProject.team_names : [editingProject.team_names],
            updated_by: currentActor
        };

        try {
            await projectsAPI.update(editingProject.id, updatePayload);
            setProjects(prev => prev.map(p => p.id === editingProject.id ? { ...p, ...updatePayload } : p));
            setToastMessage(`Project "${editingProject.name}" updated successfully by ${currentActor}!`);
            setEditingProject(null);
        } catch (err) {
            console.error('Failed to update project:', err);
            alert('Failed to update project.');
        }
    };

    // STATUS QUICK-TOGGLE
    const handleStatusChange = async (id, newStatus) => {
        setProjects(prev => prev.map(p => p.id === id ? { ...p, status: newStatus, updated_by: currentActor } : p));
        try {
            await projectsAPI.update(id, { status: newStatus, updated_by: currentActor });
        } catch (err) {
            console.error('Failed to update project status:', err);
        }
    };

    // DELETE
    const handleConfirmDelete = async () => {
        const id = confirmDeleteId;
        setConfirmDeleteId(null);
        try {
            await projectsAPI.delete(id, currentActor);
            setProjects(prev => prev.filter(p => p.id !== id));
            setToastMessage(`Project ${id} deleted successfully by ${currentActor}.`);
        } catch (err) {
            console.error('Failed to delete project:', err);
            alert('Failed to delete project.');
        }
    };

    if (loading) {
        return (
            <div style={{ textAlign: 'center', padding: 100, color: 'var(--text-tertiary)' }}>
                <Loader2 size={32} className="spin" style={{ marginBottom: 12 }} />
                <div>Loading enterprise projects...</div>
            </div>
        );
    }

    const filteredProjects = projects.filter(p => {
        const matchStatus = statusFilter === 'All' || p.status === statusFilter;
        const pCompanyId = p.company_id || p.org_id;
        const matchCompany = companyFilter === 'All' ||
            pCompanyId === companyFilter ||
            p.company_name === companyFilter ||
            (companyOptions.find(c => (c.id || c.company_id) === companyFilter)?.name === p.company_name);
        return matchStatus && matchCompany;
    });

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
                    message={`Are you sure you want to permanently delete project ${confirmDeleteId}? This action cannot be undone.`}
                    onConfirm={handleConfirmDelete}
                    onCancel={() => setConfirmDeleteId(null)}
                />
            )}

            {/* Metrics */}
            <div className="stats-grid mb-lg">
                <StatsCard icon={<Folder size={24} />} value={projects.length} label="Total Projects" color="blue" delay={0} />
                <StatsCard icon={<Play size={24} />} value={projects.filter(p => p.status === 'Active').length} label="Active" color="green" delay={0.08} />
                <StatsCard icon={<Pause size={24} />} value={projects.filter(p => p.status === 'On Hold').length} label="On Hold" color="orange" delay={0.16} />
                <StatsCard icon={<CheckCircle size={24} />} value={projects.filter(p => p.status === 'Completed').length} label="Completed" color="purple" delay={0.24} />
            </div>

            <AnimatedCard delay={0.3}>
                <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 12 }}>
                    <div>
                        <span className="card-title">Projects Management</span>
                        <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: 2 }}>
                            Multi-tenant project portfolio with live team assignments and transparent actor audit.
                        </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                        {/* Company Filter */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Building2 size={15} color="var(--text-tertiary)" />
                            <select
                                value={companyFilter}
                                onChange={e => setCompanyFilter(e.target.value)}
                                style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}
                            >
                                <option value="All">All Companies</option>
                                {companyOptions.map(c => {
                                    const cId = c.id || c.company_id;
                                    const cCode = c.code || cId;
                                    return (
                                        <option key={cId} value={cId}>{c.name} ({cCode})</option>
                                    );
                                })}
                            </select>
                        </div>

                        {/* Status Filter */}
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <Filter size={15} color="var(--text-tertiary)" />
                            <select
                                value={statusFilter}
                                onChange={e => setStatusFilter(e.target.value)}
                                style={{ padding: '6px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.82rem' }}
                            >
                                <option value="All">All Status</option>
                                <option value="Active">Active</option>
                                <option value="On Hold">On Hold</option>
                                <option value="Completed">Completed</option>
                                <option value="Cancelled">Cancelled</option>
                            </select>
                        </div>

                        <button
                            className="btn btn-primary btn-sm"
                            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                            onClick={() => setShowCreateModal(true)}
                        >
                            <FolderPlus size={15} /> New Project
                        </button>
                    </div>
                </div>

                {/* Table */}
                <div className="card-body" style={{ padding: 0 }}>
                    <div className="table-wrapper">
                        <table className="table">
                            <thead>
                                <tr>
                                    <th>Project Details</th>
                                    <th>Tenant / Company</th>
                                    <th>Client</th>
                                    <th>Sprint</th>
                                    <th>Assigned PM & Teams</th>
                                    <th>Status</th>
                                    <th>Audit & Transparency</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredProjects.map(p => (
                                    <tr key={p.id}>
                                        <td>
                                            <div style={{ fontWeight: 700, fontSize: '0.88rem', color: 'var(--text-primary)' }}>{p.name}</div>
                                            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', maxWidth: 220, lineHeight: 1.4, marginTop: 2 }}>
                                                {p.description}
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                                                <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-primary)' }}>
                                                    {p.company_name || companyOptions.find(c => (c.id || c.company_id) === (p.company_id || p.org_id))?.name || 'Samanvaya Inc.'}
                                                </span>
                                                <span className="badge badge-info" style={{ fontFamily: 'monospace', fontSize: '0.7rem', width: 'fit-content' }}>
                                                    {p.company_id || p.org_id || 'ORG-001'}
                                                </span>
                                            </div>
                                        </td>
                                        <td style={{ fontSize: '0.82rem', fontWeight: 600 }}>{p.client}</td>
                                        <td>
                                            <span className="badge badge-secondary" style={{ fontSize: '0.75rem' }}>
                                                {p.sprint}
                                            </span>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.82rem', fontWeight: 600 }}>
                                                    <Users size={12} color="#3b82f6" /> {p.assignedPM}
                                                </span>
                                                {p.team_names && p.team_names.length > 0 && (
                                                    <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)' }}>
                                                        {p.team_names.join(', ')}
                                                    </span>
                                                )}
                                            </div>
                                        </td>
                                        <td>
                                            <select
                                                value={p.status}
                                                onChange={e => handleStatusChange(p.id, e.target.value)}
                                                style={{
                                                    padding: '4px 8px',
                                                    borderRadius: 'var(--radius-sm)',
                                                    border: '1px solid var(--border-color)',
                                                    fontSize: '0.78rem',
                                                    fontWeight: 600,
                                                    color: statusColors[p.status],
                                                    background: `${statusColors[p.status]}12`
                                                }}
                                            >
                                                <option value="Active">Active</option>
                                                <option value="On Hold">On Hold</option>
                                                <option value="Completed">Completed</option>
                                                <option value="Cancelled">Cancelled</option>
                                            </select>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: '0.72rem' }}>
                                                <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                    <UserCheck size={11} color="#3b82f6" />
                                                    <span>By: <b>{p.created_by || 'Alexander Sterling (CEO)'}</b></span>
                                                </div>
                                                {p.updated_by && (
                                                    <div style={{ color: 'var(--text-tertiary)', fontSize: '0.68rem' }}>
                                                        Mod: {p.updated_by}
                                                    </div>
                                                )}
                                            </div>
                                        </td>
                                        <td>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    title="Edit Project"
                                                    onClick={() => setEditingProject({ ...p })}
                                                    style={{ padding: '4px 8px' }}
                                                >
                                                    <Edit2 size={13} />
                                                </button>
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    title="Delete Project"
                                                    onClick={() => setConfirmDeleteId(p.id)}
                                                    style={{ padding: '4px 8px', color: '#ef4444' }}
                                                >
                                                    <Trash2 size={13} />
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                                {filteredProjects.length === 0 && (
                                    <tr>
                                        <td colSpan={8} style={{ textAlign: 'center', padding: 36, color: 'var(--text-tertiary)' }}>
                                            No projects found matching the criteria.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            </AnimatedCard>

            {/* CREATE PROJECT MODAL */}
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
                        maxWidth: 620,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        {/* Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div style={{
                                    width: 42,
                                    height: 42,
                                    borderRadius: 10,
                                    background: 'rgba(37, 99, 235, 0.1)',
                                    color: '#2563eb',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    flexShrink: 0
                                }}>
                                    <FolderPlus size={22} />
                                </div>
                                <div>
                                    <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
                                        Create New Enterprise Project
                                    </h3>
                                    <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: 3 }}>
                                        Register a new delivery project, assign technical squads, and set PM leadership.
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setShowCreateModal(false)}
                                style={{
                                    width: 32,
                                    height: 32,
                                    borderRadius: 8,
                                    background: '#f1f5f9',
                                    border: 'none',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: '#64748b',
                                    fontSize: '1rem',
                                    transition: 'all 0.2s ease'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.background = '#e2e8f0'; e.currentTarget.style.color = '#0f172a'; }}
                                onMouseLeave={e => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#64748b'; }}
                            >
                                ✕
                            </button>
                        </div>

                        <form onSubmit={handleCreateProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Project Name <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    className="form-input"
                                    placeholder="e.g. NextGen Microservices Engine"
                                    value={newProject.name}
                                    onChange={e => setNewProject({ ...newProject, name: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                />
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Client Name <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    className="form-input"
                                    placeholder="e.g. Siemens Healthineers"
                                    value={newProject.client}
                                    onChange={e => setNewProject({ ...newProject, client: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                />
                            </div>

                            <div style={{ gridColumn: '1 / -1' }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Project Scope & Description <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <textarea
                                    className="form-input"
                                    rows={2}
                                    placeholder="Core architecture milestones, microservices setup, release goals..."
                                    value={newProject.description}
                                    onChange={e => setNewProject({ ...newProject, description: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff',
                                        resize: 'vertical'
                                    }}
                                    required
                                />
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Assign to Company Tenant <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <select
                                    className="form-select"
                                    value={newProject.company_id || (currentCompany?.company_id || currentCompany?.id || 'ORG-001')}
                                    onChange={e => setNewProject({ ...newProject, company_id: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                >
                                    {companyOptions.map(c => {
                                        const cId = c.id || c.company_id || 'ORG-001';
                                        const cCode = c.code || cId;
                                        return (
                                            <option key={cId} value={cId}>
                                                {c.name} ({cCode})
                                            </option>
                                        );
                                    })}
                                </select>
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Sprint Target <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <select
                                    className="form-select"
                                    value={newProject.sprint}
                                    onChange={e => setNewProject({ ...newProject, sprint: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                >
                                    <option value="">Select Target Sprint</option>
                                    {sprintOptions.length ? sprintOptions.map(s => (
                                        <option key={s.id || s.name} value={s.name}>{s.name || s}</option>
                                    )) : (
                                        <>
                                            <option value="Sprint 42 (Current)">Sprint 42 (Current)</option>
                                            <option value="Sprint 43 (Upcoming)">Sprint 43 (Upcoming)</option>
                                        </>
                                    )}
                                </select>
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Assigned Project Manager <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <select
                                    className="form-select"
                                    value={newProject.assignedPM}
                                    onChange={e => setNewProject({ ...newProject, assignedPM: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                >
                                    <option value="">Select Project Manager</option>
                                    {availablePMs.map(pm => (
                                        <option key={pm.id} value={pm.name}>{pm.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Assigned Team Squad
                                </label>
                                <select
                                    className="form-select"
                                    value={newProject.team_name}
                                    onChange={e => setNewProject({ ...newProject, team_name: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                >
                                    <option value="">Select Squad (Optional)</option>
                                    {teamOptions.map(t => (
                                        <option key={t.id || t.team_id} value={t.name}>{t.name}</option>
                                    ))}
                                </select>
                            </div>

                            {/* Transparency Notice */}
                            <div style={{
                                gridColumn: '1 / -1',
                                background: '#f8fafc',
                                border: '1px solid #e2e8f0',
                                padding: '12px 16px',
                                borderRadius: 10,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                fontSize: '0.82rem',
                                color: '#475569'
                            }}>
                                <UserCheck size={16} color="#3b82f6" style={{ flexShrink: 0 }} />
                                <div>
                                    <span style={{ fontWeight: 600, color: '#1e293b' }}>Audit & Transparency:</span> This project creation will be permanently recorded in the immutable audit trail as initiated by <b style={{ color: '#0f172a' }}>{currentActor}</b>.
                                </div>
                            </div>

                            {/* Modal Footer */}
                            <div style={{
                                gridColumn: '1 / -1',
                                display: 'flex',
                                justifyContent: 'flex-end',
                                gap: 12,
                                marginTop: 8,
                                paddingTop: 16,
                                borderTop: '1px solid #f1f5f9'
                            }}>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setShowCreateModal(false)}
                                    style={{
                                        padding: '10px 20px',
                                        borderRadius: 8,
                                        fontWeight: 600,
                                        fontSize: '0.88rem'
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 8,
                                        padding: '10px 22px',
                                        borderRadius: 8,
                                        fontWeight: 600,
                                        fontSize: '0.88rem',
                                        boxShadow: '0 4px 14px rgba(192, 57, 43, 0.3)'
                                    }}
                                >
                                    <FolderPlus size={16} /> Create Project
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* EDIT PROJECT MODAL */}
            {editingProject && (
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
                        maxWidth: 620,
                        boxShadow: '0 25px 50px -12px rgba(15, 23, 42, 0.45), 0 0 0 1px rgba(0, 0, 0, 0.05)',
                        animation: 'fadeIn 0.2s ease-out'
                    }}>
                        {/* Header */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 20 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                <div style={{
                                    width: 42,
                                    height: 42,
                                    borderRadius: 10,
                                    background: 'rgba(37, 99, 235, 0.1)',
                                    color: '#2563eb',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    flexShrink: 0
                                }}>
                                    <Edit2 size={20} />
                                </div>
                                <div>
                                    <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: 700, color: '#0f172a' }}>
                                        Edit Project Details
                                    </h3>
                                    <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: 3 }}>
                                        Updating project parameters for <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#2563eb' }}>{editingProject.id}</span>
                                    </div>
                                </div>
                            </div>
                            <button
                                onClick={() => setEditingProject(null)}
                                style={{
                                    width: 32,
                                    height: 32,
                                    borderRadius: 8,
                                    background: '#f1f5f9',
                                    border: 'none',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    color: '#64748b',
                                    fontSize: '1rem',
                                    transition: 'all 0.2s ease'
                                }}
                                onMouseEnter={e => { e.currentTarget.style.background = '#e2e8f0'; e.currentTarget.style.color = '#0f172a'; }}
                                onMouseLeave={e => { e.currentTarget.style.background = '#f1f5f9'; e.currentTarget.style.color = '#64748b'; }}
                            >
                                ✕
                            </button>
                        </div>

                        <form onSubmit={handleUpdateProject} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Project Name <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    className="form-input"
                                    value={editingProject.name}
                                    onChange={e => setEditingProject({ ...editingProject, name: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                />
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Client Name <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <input
                                    className="form-input"
                                    value={editingProject.client}
                                    onChange={e => setEditingProject({ ...editingProject, client: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                />
                            </div>

                            <div style={{ gridColumn: '1 / -1' }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Description <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <textarea
                                    className="form-input"
                                    rows={2}
                                    value={editingProject.description}
                                    onChange={e => setEditingProject({ ...editingProject, description: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff',
                                        resize: 'vertical'
                                    }}
                                    required
                                />
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Delivery Status
                                </label>
                                <select
                                    className="form-select"
                                    value={editingProject.status}
                                    onChange={e => setEditingProject({ ...editingProject, status: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                >
                                    <option value="Active">Active</option>
                                    <option value="On Hold">On Hold</option>
                                    <option value="Completed">Completed</option>
                                    <option value="Cancelled">Cancelled</option>
                                </select>
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Target Sprint
                                </label>
                                <input
                                    className="form-input"
                                    value={editingProject.sprint}
                                    onChange={e => setEditingProject({ ...editingProject, sprint: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                />
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Assigned Project Manager <span style={{ color: '#ef4444' }}>*</span>
                                </label>
                                <select
                                    className="form-select"
                                    value={editingProject.assignedPM}
                                    onChange={e => setEditingProject({ ...editingProject, assignedPM: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                    required
                                >
                                    {availablePMs.map(pm => (
                                        <option key={pm.id} value={pm.name}>{pm.name}</option>
                                    ))}
                                </select>
                            </div>

                            <div>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 600, color: '#1e293b', marginBottom: 6 }}>
                                    Company Tenant
                                </label>
                                <select
                                    className="form-select"
                                    value={editingProject.company_id || 'ORG-001'}
                                    onChange={e => setEditingProject({ ...editingProject, company_id: e.target.value })}
                                    style={{
                                        border: '1.5px solid #cbd5e1',
                                        borderRadius: 8,
                                        padding: '10px 14px',
                                        fontSize: '0.88rem',
                                        color: '#0f172a',
                                        background: '#ffffff'
                                    }}
                                >
                                    {companyOptions.map(c => {
                                        const cId = c.id || c.company_id || 'ORG-001';
                                        const cCode = c.code || cId;
                                        return (
                                            <option key={cId} value={cId}>
                                                {c.name} ({cCode})
                                            </option>
                                        );
                                    })}
                                </select>
                            </div>

                            {/* Transparency Notice */}
                            <div style={{
                                gridColumn: '1 / -1',
                                background: '#f8fafc',
                                border: '1px solid #e2e8f0',
                                padding: '12px 16px',
                                borderRadius: 10,
                                display: 'flex',
                                alignItems: 'center',
                                gap: 10,
                                fontSize: '0.82rem',
                                color: '#475569'
                            }}>
                                <UserCheck size={16} color="#3b82f6" style={{ flexShrink: 0 }} />
                                <div>
                                    <span style={{ fontWeight: 600, color: '#1e293b' }}>Audit & Transparency:</span> Updates will be attributed in the organizational event log to <b style={{ color: '#0f172a' }}>{currentActor}</b>.
                                </div>
                            </div>

                            {/* Modal Footer */}
                            <div style={{
                                gridColumn: '1 / -1',
                                display: 'flex',
                                justifyContent: 'flex-end',
                                gap: 12,
                                marginTop: 8,
                                paddingTop: 16,
                                borderTop: '1px solid #f1f5f9'
                            }}>
                                <button
                                    type="button"
                                    className="btn btn-secondary"
                                    onClick={() => setEditingProject(null)}
                                    style={{
                                        padding: '10px 20px',
                                        borderRadius: 8,
                                        fontWeight: 600,
                                        fontSize: '0.88rem'
                                    }}
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="btn btn-primary"
                                    style={{
                                        display: 'inline-flex',
                                        alignItems: 'center',
                                        gap: 8,
                                        padding: '10px 22px',
                                        borderRadius: 8,
                                        fontWeight: 600,
                                        fontSize: '0.88rem',
                                        boxShadow: '0 4px 14px rgba(192, 57, 43, 0.3)'
                                    }}
                                >
                                    <CheckCircle size={16} /> Save Changes
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}
