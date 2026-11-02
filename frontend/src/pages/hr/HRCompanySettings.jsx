import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AnimatedCard from '../../components/AnimatedCard';
import { Settings, Building2, Shield, Sliders, Timer, Loader2, Plus, Edit2, Trash2, CheckCircle2, ArrowRightLeft, Globe, MapPin, Briefcase, UserCheck } from 'lucide-react';
import { hrAPI, companiesAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import ConfirmToast from '../../components/ConfirmToast';

export default function HRCompanySettings() {
    const { user, companies: authCompanies, currentCompany, switchCompany, refreshCompanies } = useAuth();
    const navigate = useNavigate();
    
    // RBAC: HR does not have permission to add company. Only CEO / Platform Admin can.
    const canAddCompany = user?.role === 'CEO' || user?.role === 'ADMIN' || user?.is_admin === true;
    
    // Tab state: 'companies' | 'policies'
    const [activeTab, setActiveTab] = useState('companies');

    /* Multi-Company Management */
    const [companiesList, setCompaniesList] = useState([]);
    const [loadingCompanies, setLoadingCompanies] = useState(true);
    const [showAddCompanyModal, setShowAddCompanyModal] = useState(false);
    const [editingCompany, setEditingCompany] = useState(null);
    const [confirmDeleteId, setConfirmDeleteId] = useState(null);
    const [newCompanyData, setNewCompanyData] = useState({
        company_id: '',
        name: '',
        domain: '',
        industry: 'Technology & AI',
        location: 'Bengaluru, India',
    });

    /* Policy & Company Info Settings */
    const [company, setCompany] = useState({ name: '', domain: '', industry: '', location: '' });
    const [weights, setWeights] = useState({ sprint: 0, alignment: 0, delivery: 0, behaviour: 0 });
    const [sprintPolicy, setSprintPolicy] = useState({ duration: 0, maxSP: 0, approvalSLA: 0 });
    const [behaviourAssign, setBehaviourAssign] = useState([]);
    const [promotionWeightEdit, setPromotionWeightEdit] = useState([]);
    const [loadingSettings, setLoadingSettings] = useState(true);
    const [saving, setSaving] = useState(false);
    const [toastMessage, setToastMessage] = useState(null);

    // Fetch live companies
    const loadCompanies = async () => {
        try {
            const data = await companiesAPI.getAll();
            if (Array.isArray(data)) {
                setCompaniesList(data);
            }
        } catch (err) {
            console.error('Failed to load companies:', err);
        } finally {
            setLoadingCompanies(false);
        }
    };

    useEffect(() => {
        loadCompanies();
        hrAPI.companySettings()
            .then(data => {
                if (data) {
                    setCompany(data.company || { name: '', domain: '', industry: '', location: '' });
                    setWeights(data.weights || { sprint: 0, alignment: 0, delivery: 0, behaviour: 0 });
                    setSprintPolicy(data.sprintPolicy || { duration: 0, maxSP: 0, approvalSLA: 0 });
                    setBehaviourAssign(data.behaviourAssign || []);
                    setPromotionWeightEdit(data.promotionWeightEdit || []);
                }
            })
            .catch(err => console.error('Failed to fetch settings:', err))
            .finally(() => setLoadingSettings(false));
    }, []);

    const totalWeight = Object.values(weights).reduce((a, b) => a + b, 0);
    const allRoles = ['CEO', 'HR', 'PM', 'LEAD', 'DEVELOPER', 'DEVOPS', 'QA'];

    const toggleRole = (list, setList, role) => {
        setList(prev => prev.includes(role) ? prev.filter(r => r !== role) : [...prev, role]);
    };

    // Multi-Company Handlers
    const handleCreateCompany = async (e) => {
        e.preventDefault();
        if (!canAddCompany) {
            alert('HR does not have permission to add companies. Only Executive Leadership (CEO / Platform Admin) can register companies.');
            return;
        }
        const actor = user?.name ? `${user.name} (${user.role || 'CEO'})` : 'Alexander Sterling (CEO)';
        const payload = {
            ...newCompanyData,
            company_id: newCompanyData.company_id.trim() || `ORG-00${companiesList.length + 1}`,
            status: 'Active',
            created_by: actor,
        };
        try {
            await companiesAPI.create(payload);
            setToastMessage(`Company "${payload.name}" successfully created by ${actor}!`);
            setShowAddCompanyModal(false);
            setNewCompanyData({ company_id: '', name: '', domain: '', industry: 'Technology & AI', location: 'Bengaluru, India' });
            await loadCompanies();
            if (refreshCompanies) refreshCompanies();
        } catch (err) {
            console.error('Failed to create company:', err);
            alert('Failed to create company. Please check company ID uniqueness.');
        }
    };

    const handleUpdateCompany = async (e) => {
        e.preventDefault();
        if (!editingCompany) return;
        const actor = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';
        const cId = editingCompany.id || editingCompany.company_id;
        try {
            await companiesAPI.update(cId, {
                ...editingCompany,
                updated_by: actor,
            });
            setToastMessage(`Company "${editingCompany.name}" updated successfully by ${actor}!`);
            setEditingCompany(null);
            await loadCompanies();
            if (refreshCompanies) refreshCompanies();
        } catch (err) {
            console.error('Failed to update company:', err);
            alert('Failed to update company.');
        }
    };

    const handleDeleteCompany = async () => {
        const id = confirmDeleteId;
        setConfirmDeleteId(null);
        const actor = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';
        try {
            await companiesAPI.delete(id, actor);
            setToastMessage(`Company ${id} removed successfully by ${actor}.`);
            await loadCompanies();
            if (refreshCompanies) refreshCompanies();
        } catch (err) {
            console.error('Failed to delete company:', err);
            alert('Failed to delete company.');
        }
    };

    // Save Policy Settings
    const handleSaveSettings = async () => {
        if (totalWeight !== 100) {
            alert('Total performance weights must equal 100%');
            return;
        }
        setSaving(true);
        const actor = user?.name ? `${user.name} (${user.role || 'HR'})` : 'Priya Sharma (HR)';
        try {
            await hrAPI.updateCompanySettings({
                company,
                weights,
                sprintPolicy,
                behaviourAssign,
                promotionWeightEdit,
                updated_by: actor
            });
            setToastMessage(`Company settings successfully updated by ${actor}!`);
        } catch (err) {
            console.error('Failed to save settings:', err);
            alert('Failed to save settings. Please try again.');
        } finally {
            setSaving(false);
        }
    };

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
                    message={`Are you sure you want to delete company "${confirmDeleteId}"? This action removes all tenant associations.`}
                    onConfirm={handleDeleteCompany}
                    onCancel={() => setConfirmDeleteId(null)}
                />
            )}

            {/* Top Navigation Tabs */}
            <div style={{ display: 'flex', gap: 12, marginBottom: 24, borderBottom: '1px solid var(--border-color)', paddingBottom: 12 }}>
                <button
                    onClick={() => setActiveTab('companies')}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '10px 20px',
                        borderRadius: 'var(--radius-md)',
                        fontWeight: 700,
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                        border: 'none',
                        background: activeTab === 'companies' ? '#3b82f6' : 'var(--bg-secondary)',
                        color: activeTab === 'companies' ? '#ffffff' : 'var(--text-secondary)',
                        transition: 'all 0.2s ease',
                    }}
                >
                    <Building2 size={18} />
                    Multi-Company Tenants ({companiesList.length})
                </button>
                <button
                    onClick={() => setActiveTab('policies')}
                    style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 8,
                        padding: '10px 20px',
                        borderRadius: 'var(--radius-md)',
                        fontWeight: 700,
                        fontSize: '0.9rem',
                        cursor: 'pointer',
                        border: 'none',
                        background: activeTab === 'policies' ? '#3b82f6' : 'var(--bg-secondary)',
                        color: activeTab === 'policies' ? '#ffffff' : 'var(--text-secondary)',
                        transition: 'all 0.2s ease',
                    }}
                >
                    <Sliders size={18} />
                    Policies & Performance Rules
                </button>
            </div>

            {/* TAB 1: MULTI-COMPANY TENANT DIRECTORY */}
            {activeTab === 'companies' && (
                <div>
                    <AnimatedCard delay={0.1}>
                        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                    <Building2 size={20} color="#3b82f6" />
                                    Company Directory & Multi-Tenant Architecture
                                </span>
                                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '4px 0 0 0' }}>
                                    Executive Leadership (CEO / Admin) registers companies. HR manages organization projects and teams.
                                </p>
                            </div>
                            {canAddCompany && (
                                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                                    <button
                                        className="btn btn-secondary"
                                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                        onClick={() => navigate('/admin/create-company')}
                                    >
                                        <Shield size={16} /> SuperAdmin Provisioning
                                    </button>
                                    <button
                                        className="btn btn-primary"
                                        style={{ display: 'flex', alignItems: 'center', gap: 6 }}
                                        onClick={() => setShowAddCompanyModal(true)}
                                    >
                                        <Plus size={16} /> Quick Add Company
                                    </button>
                                </div>
                            )}
                        </div>

                        <div className="card-body" style={{ padding: 0 }}>
                            {loadingCompanies ? (
                                <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)' }}>
                                    <Loader2 size={28} className="spin" style={{ marginBottom: 10 }} />
                                    <div>Loading corporate tenants...</div>
                                </div>
                            ) : (
                                <div className="table-wrapper">
                                    <table className="table">
                                        <thead>
                                            <tr>
                                                <th>Company Tenant</th>
                                                <th>Tenant ID</th>
                                                <th>Domain</th>
                                                <th>Industry</th>
                                                <th>Headquarters</th>
                                                <th>Status</th>
                                                <th>Audit & Transparency</th>
                                                <th>Actions</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {companiesList.map(c => {
                                                const cId = c.id || c.company_id;
                                                const currentId = currentCompany?.id || currentCompany?.company_id;
                                                const isActive = currentId === cId;
                                                return (
                                                    <tr key={cId} style={{ background: isActive ? '#3b82f608' : 'transparent' }}>
                                                        <td>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                                                <div style={{
                                                                    width: 40,
                                                                    height: 40,
                                                                    borderRadius: 'var(--radius-md)',
                                                                    background: isActive ? '#3b82f6' : 'var(--bg-secondary)',
                                                                    color: isActive ? '#fff' : 'var(--text-primary)',
                                                                    display: 'flex',
                                                                    alignItems: 'center',
                                                                    justifyContent: 'center',
                                                                    fontWeight: 800,
                                                                    fontSize: '0.9rem',
                                                                    border: '1px solid var(--border-color)',
                                                                }}>
                                                                    <Building2 size={20} />
                                                                </div>
                                                                <div>
                                                                    <div style={{ fontWeight: 700, fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                                                        {c.name}
                                                                        {isActive && (
                                                                            <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.7rem' }}>
                                                                                <CheckCircle2 size={11} /> Active Tenant
                                                                            </span>
                                                                        )}
                                                                    </div>
                                                                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                                                        {c.description || 'Enterprise Organization'}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <span className="badge badge-info" style={{ fontFamily: 'monospace', fontWeight: 600 }}>
                                                                {cId}
                                                            </span>
                                                        </td>
                                                        <td>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.82rem' }}>
                                                                <Globe size={13} color="var(--text-tertiary)" /> {c.domain || 'samanvaya.io'}
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.82rem' }}>
                                                                <Briefcase size={13} color="var(--text-tertiary)" /> {c.industry || 'Technology'}
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: '0.82rem' }}>
                                                                <MapPin size={13} color="var(--text-tertiary)" /> {c.location || 'India'}
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <span className="badge badge-success">
                                                                {c.status || 'Active'}
                                                            </span>
                                                        </td>
                                                        <td>
                                                            <div style={{ fontSize: '0.72rem', display: 'flex', flexDirection: 'column', gap: 3 }}>
                                                                <div style={{ color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                                                                    <UserCheck size={12} color="#3b82f6" />
                                                                    <span>Created by: <b>{c.created_by || 'Alexander Sterling (CEO)'}</b></span>
                                                                </div>
                                                                {c.updated_by && (
                                                                    <div style={{ color: 'var(--text-tertiary)', fontSize: '0.68rem' }}>
                                                                        Mod: {c.updated_by}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </td>
                                                        <td>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                                {!isActive && (
                                                                    <button
                                                                        className="btn btn-sm btn-primary"
                                                                        style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '4px 10px', fontSize: '0.75rem' }}
                                                                        onClick={() => switchCompany(c)}
                                                                        title="Switch workspace context to this company"
                                                                    >
                                                                        <ArrowRightLeft size={12} /> Switch
                                                                    </button>
                                                                )}
                                                                {canAddCompany && (
                                                                    <button
                                                                        className="btn btn-sm btn-secondary"
                                                                        style={{ padding: '4px 8px' }}
                                                                        onClick={() => setEditingCompany({ ...c })}
                                                                        title="Edit Company Details"
                                                                    >
                                                                        <Edit2 size={13} />
                                                                    </button>
                                                                )}
                                                                {canAddCompany && companiesList.length > 1 && (
                                                                    <button
                                                                        className="btn btn-sm btn-secondary"
                                                                        style={{ padding: '4px 8px', color: '#ef4444' }}
                                                                        onClick={() => setConfirmDeleteId(cId)}
                                                                        title="Delete Company"
                                                                    >
                                                                        <Trash2 size={13} />
                                                                    </button>
                                                                )}
                                                            </div>
                                                        </td>
                                                    </tr>
                                                );
                                            })}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    </AnimatedCard>

                    {/* ADD COMPANY MODAL */}
                    {showAddCompanyModal && canAddCompany && (
                        <div style={{
                            position: 'fixed',
                            top: 0, left: 0, right: 0, bottom: 0,
                            background: 'rgba(0,0,0,0.5)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 1000,
                            backdropFilter: 'blur(3px)'
                        }}>
                            <div style={{
                                background: 'var(--bg-primary)',
                                borderRadius: 'var(--radius-lg)',
                                border: '1px solid var(--border-color)',
                                padding: 28,
                                width: '100%',
                                maxWidth: 520,
                                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                    <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <Building2 size={20} color="#3b82f6" /> Add New Company
                                    </h3>
                                    <button
                                        onClick={() => setShowAddCompanyModal(false)}
                                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-tertiary)' }}
                                    >
                                        ✕
                                    </button>
                                </div>

                                <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginBottom: 20 }}>
                                    Adding a new company provisions an isolated corporate workspace with its own roles, teams, and dashboards.
                                </p>

                                <form onSubmit={handleCreateCompany} style={{ display: 'grid', gap: 14 }}>
                                    <div>
                                        <label className="form-label">Company ID *</label>
                                        <input
                                            className="form-input"
                                            placeholder="e.g. ORG-004"
                                            value={newCompanyData.company_id}
                                            onChange={e => setNewCompanyData({ ...newCompanyData, company_id: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Company Name *</label>
                                        <input
                                            className="form-input"
                                            placeholder="e.g. Horizon Cloud Systems"
                                            value={newCompanyData.name}
                                            onChange={e => setNewCompanyData({ ...newCompanyData, name: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Domain *</label>
                                        <input
                                            className="form-input"
                                            placeholder="e.g. horizoncloud.io"
                                            value={newCompanyData.domain}
                                            onChange={e => setNewCompanyData({ ...newCompanyData, domain: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                        <div>
                                            <label className="form-label">Industry</label>
                                            <input
                                                className="form-input"
                                                placeholder="e.g. Cloud & Cybersecurity"
                                                value={newCompanyData.industry}
                                                onChange={e => setNewCompanyData({ ...newCompanyData, industry: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="form-label">Headquarters Location</label>
                                            <input
                                                className="form-input"
                                                placeholder="e.g. Hyderabad, India"
                                                value={newCompanyData.location}
                                                onChange={e => setNewCompanyData({ ...newCompanyData, location: e.target.value })}
                                            />
                                        </div>
                                    </div>

                                    <div style={{ background: 'var(--bg-secondary)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                        <b>Transparency:</b> Will be logged in the immutable audit trail as created by <b>{user?.name || 'Alexander Sterling'} ({user?.role || 'Admin/HR'})</b>.
                                    </div>

                                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                                        <button type="button" className="btn btn-secondary" onClick={() => setShowAddCompanyModal(false)}>
                                            Cancel
                                        </button>
                                        <button type="submit" className="btn btn-primary" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                            <Building2 size={16} /> Create Company
                                        </button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}

                    {/* EDIT COMPANY MODAL */}
                    {editingCompany && (
                        <div style={{
                            position: 'fixed',
                            top: 0, left: 0, right: 0, bottom: 0,
                            background: 'rgba(0,0,0,0.5)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            zIndex: 1000,
                            backdropFilter: 'blur(3px)'
                        }}>
                            <div style={{
                                background: 'var(--bg-primary)',
                                borderRadius: 'var(--radius-lg)',
                                border: '1px solid var(--border-color)',
                                padding: 28,
                                width: '100%',
                                maxWidth: 520,
                                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
                            }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                    <h3 style={{ margin: 0, fontSize: '1.15rem', display: 'flex', alignItems: 'center', gap: 8 }}>
                                        <Edit2 size={18} color="#3b82f6" /> Edit Company ({editingCompany.id || editingCompany.company_id})
                                    </h3>
                                    <button
                                        onClick={() => setEditingCompany(null)}
                                        style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1.2rem', color: 'var(--text-tertiary)' }}
                                    >
                                        ✕
                                    </button>
                                </div>

                                <form onSubmit={handleUpdateCompany} style={{ display: 'grid', gap: 14 }}>
                                    <div>
                                        <label className="form-label">Company Name *</label>
                                        <input
                                            className="form-input"
                                            value={editingCompany.name}
                                            onChange={e => setEditingCompany({ ...editingCompany, name: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Domain *</label>
                                        <input
                                            className="form-input"
                                            value={editingCompany.domain}
                                            onChange={e => setEditingCompany({ ...editingCompany, domain: e.target.value })}
                                            required
                                        />
                                    </div>
                                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                                        <div>
                                            <label className="form-label">Industry</label>
                                            <input
                                                className="form-input"
                                                value={editingCompany.industry || ''}
                                                onChange={e => setEditingCompany({ ...editingCompany, industry: e.target.value })}
                                            />
                                        </div>
                                        <div>
                                            <label className="form-label">Headquarters Location</label>
                                            <input
                                                className="form-input"
                                                value={editingCompany.location || ''}
                                                onChange={e => setEditingCompany({ ...editingCompany, location: e.target.value })}
                                            />
                                        </div>
                                    </div>

                                    <div style={{ background: 'var(--bg-secondary)', padding: '10px 14px', borderRadius: 'var(--radius-sm)', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                        <b>Transparency:</b> Will be logged as updated by <b>{user?.name || 'Alexander Sterling'} ({user?.role || 'Admin/HR'})</b>.
                                    </div>

                                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 10 }}>
                                        <button type="button" className="btn btn-secondary" onClick={() => setEditingCompany(null)}>
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
                </div>
            )}

            {/* TAB 2: POLICIES & PERFORMANCE RULES */}
            {activeTab === 'policies' && (
                <div>
                    <div className="grid-2 mb-lg">
                        {/* Company Info */}
                        <AnimatedCard delay={0.1}>
                            <div className="card-header">
                                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Building2 size={18} /> Active Company Metadata</span>
                            </div>
                            <div className="card-body">
                                <div style={{ display: 'grid', gap: 16 }}>
                                    {Object.entries(company).map(([key, val]) => (
                                        <div key={key}>
                                            <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>
                                                {key === 'name' ? 'Company Name' : key.charAt(0).toUpperCase() + key.slice(1)}
                                            </label>
                                            <input type="text" value={val}
                                                onChange={e => setCompany(prev => ({ ...prev, [key]: e.target.value }))}
                                                style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }} />
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </AnimatedCard>

                        {/* Sprint Policy */}
                        <AnimatedCard delay={0.18}>
                            <div className="card-header">
                                <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Timer size={18} /> Sprint Policy</span>
                            </div>
                            <div className="card-body">
                                <div style={{ display: 'grid', gap: 16 }}>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Sprint Duration (days)</label>
                                        <input type="number" value={sprintPolicy.duration}
                                            onChange={e => setSprintPolicy(prev => ({ ...prev, duration: Number(e.target.value) }))}
                                            style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }} />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Max Story Points per Sprint</label>
                                        <input type="number" value={sprintPolicy.maxSP}
                                            onChange={e => setSprintPolicy(prev => ({ ...prev, maxSP: Number(e.target.value) }))}
                                            style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }} />
                                    </div>
                                    <div>
                                        <label style={{ display: 'block', fontSize: '0.75rem', color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: 4 }}>Approval SLA Time (hours)</label>
                                        <input type="number" value={sprintPolicy.approvalSLA}
                                            onChange={e => setSprintPolicy(prev => ({ ...prev, approvalSLA: Number(e.target.value) }))}
                                            style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border-color)', fontSize: '0.9rem' }} />
                                    </div>
                                </div>
                            </div>
                        </AnimatedCard>
                    </div>

                    {/* Performance Weights */}
                    <AnimatedCard delay={0.26}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Sliders size={18} /> Performance Weights</span>
                            <span className={`badge ${totalWeight === 100 ? 'badge-success' : 'badge-danger'}`}>
                                Total: {totalWeight}%{totalWeight !== 100 ? ' ⚠ Must equal 100%' : ' ✓'}
                            </span>
                        </div>
                        <div className="card-body">
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
                                {[
                                    { key: 'sprint', label: 'Sprint Contribution', color: '#3b82f6' },
                                    { key: 'alignment', label: 'Alignment Score', color: '#10b981' },
                                    { key: 'delivery', label: 'Delivery', color: '#f59e0b' },
                                    { key: 'behaviour', label: 'Behaviour', color: '#8b5cf6' },
                                ].map(w => (
                                    <div key={w.key} style={{ padding: '18px 20px', background: 'var(--bg-secondary)', borderRadius: 'var(--radius-md)', borderLeft: `4px solid ${w.color}` }}>
                                        <div style={{ fontWeight: 700, fontSize: '0.85rem', marginBottom: 10, color: w.color }}>{w.label}</div>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                                            <input type="range" min="0" max="100" value={weights[w.key]}
                                                onChange={e => setWeights(prev => ({ ...prev, [w.key]: Number(e.target.value) }))}
                                                style={{ flex: 1, accentColor: w.color }} />
                                            <span style={{ fontWeight: 800, fontSize: '1.1rem', color: w.color, minWidth: 45, textAlign: 'center' }}>{weights[w.key]}%</span>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    </AnimatedCard>

                    {/* Access Control */}
                    <AnimatedCard delay={0.34} style={{ marginTop: 20 }}>
                        <div className="card-header">
                            <span className="card-title" style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Shield size={18} /> Access Control</span>
                        </div>
                        <div className="card-body">
                            <div className="grid-2" style={{ gap: 24 }}>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: 12 }}>Who can assign Behaviour Marks?</div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                        {allRoles.map(r => (
                                            <button key={r} onClick={() => toggleRole(behaviourAssign, setBehaviourAssign, r)}
                                                style={{
                                                    padding: '6px 14px', borderRadius: 'var(--radius-xl)', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s ease',
                                                    background: behaviourAssign.includes(r) ? '#3b82f6' : '#fff', color: behaviourAssign.includes(r) ? '#fff' : 'var(--text-secondary)',
                                                    border: `1px solid ${behaviourAssign.includes(r) ? '#3b82f6' : 'var(--border-color)'}`
                                                }}>{r}</button>
                                        ))}
                                    </div>
                                </div>
                                <div>
                                    <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: 12 }}>Who can edit Promotion Weights?</div>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                                        {allRoles.map(r => (
                                            <button key={r} onClick={() => toggleRole(promotionWeightEdit, setPromotionWeightEdit, r)}
                                                style={{
                                                    padding: '6px 14px', borderRadius: 'var(--radius-xl)', fontSize: '0.82rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s ease',
                                                    background: promotionWeightEdit.includes(r) ? '#8b5cf6' : '#fff', color: promotionWeightEdit.includes(r) ? '#fff' : 'var(--text-secondary)',
                                                    border: `1px solid ${promotionWeightEdit.includes(r) ? '#8b5cf6' : 'var(--border-color)'}`
                                                }}>{r}</button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </AnimatedCard>

                    <div style={{ marginTop: 20, display: 'flex', justifyContent: 'flex-end' }}>
                        <button className="btn btn-primary" onClick={handleSaveSettings} disabled={saving} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            {saving ? <Loader2 size={16} className="spin" /> : null}
                            {saving ? 'Saving...' : 'Save All Settings'}
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
}
