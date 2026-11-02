import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
    Shield, Building2, UserCheck, Key, Lock, CheckCircle2,
    AlertTriangle, RefreshCw, Eye, EyeOff, Copy, Check,
    Users, Briefcase, Mail, Phone, Globe, MapPin, Database,
    Server, ArrowRight, Sparkles, ExternalLink, Activity, Plus
} from 'lucide-react';
import { adminAPI } from '../../services/api';
import { useAuth } from '../../context/AuthContext';
import AnimatedCard from '../../components/AnimatedCard';

export default function AdminPanel({ defaultTab = 'profile' }) {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, refreshCompanies } = useAuth();

    // Determine initial tab from pathname or prop
    const getInitialTab = () => {
        if (location.pathname.includes('/admin/create-company')) return 'create';
        if (location.pathname.includes('/admin/companies')) return 'companies';
        if (location.pathname.includes('/admin/profile')) return 'profile';
        return defaultTab;
    };

    const [activeTab, setActiveTab] = useState(getInitialTab);
    const [adminKey, setAdminKey] = useState(() => {
        return sessionStorage.getItem('samanvaya_admin_key') || 'samanvaya-admin-2026';
    });
    const [isAuthenticated, setIsAuthenticated] = useState(false);
    const [keyInput, setKeyInput] = useState('');
    const [authError, setAuthError] = useState('');
    const [loading, setLoading] = useState(true);

    // Profile & Stats state
    const [profile, setProfile] = useState(null);
    const [companies, setCompanies] = useState([]);
    const [stats, setStats] = useState(null);
    const [refreshing, setRefreshing] = useState(false);

    // Password visibility toggles
    const [showCompanyPwd, setShowCompanyPwd] = useState(false);
    const [showCeoPwd, setShowCeoPwd] = useState(false);
    const [showHrPwd, setShowHrPwd] = useState(false);
    const [copiedKey, setCopiedKey] = useState(null);

    // Provisioning Form state
    const [provisioning, setProvisioning] = useState(false);
    const [provisionSuccess, setProvisionSuccess] = useState(null);
    const [provisionError, setProvisionError] = useState('');
    const [formData, setFormData] = useState({
        code: '',
        name: '',
        domain: '',
        industry: 'Enterprise AI & Cloud Software',
        location: 'Bengaluru HQ (Whitefield), Karnataka',
        company_password: 'Company@org123',
        description: 'Next-generation intelligent enterprise execution platform.',
        ceo: {
            name: '',
            email: '',
            employee_id: '',
            password: 'Emp@ceo123',
            phone: '+91 98450 11223',
            bio: 'Chief Executive Officer leading strategic growth and vision.',
        },
        hr: {
            name: '',
            email: '',
            employee_id: '',
            password: 'Emp@hr123',
            phone: '+91 98450 44556',
        }
    });

    // Reassign modal state
    const [reassignModal, setReassignModal] = useState({
        isOpen: false,
        company: null,
        role: 'CEO',
        name: '',
        email: '',
        employee_id: '',
        password: '',
        phone: ''
    });

    // Automatically synchronize IDs when company code changes
    const handleCodeChange = (codeVal) => {
        const clean = codeVal.toUpperCase().replace(/[^A-Z0-9]/g, '');
        setFormData(prev => ({
            ...prev,
            code: clean,
            domain: clean ? `${clean.toLowerCase()}.samanvaya.io` : '',
            ceo: {
                ...prev.ceo,
                employee_id: clean ? `EMP-CEO-${clean}-001` : prev.ceo.employee_id,
                email: clean && prev.ceo.name ? `${prev.ceo.name.toLowerCase().replace(/\s+/g, '.')}@${clean.toLowerCase()}.samanvaya.io` : prev.ceo.email,
            },
            hr: {
                ...prev.hr,
                employee_id: clean ? `EMP-HR-${clean}-001` : prev.hr.employee_id,
                email: clean && prev.hr.name ? `${prev.hr.name.toLowerCase().replace(/\s+/g, '.')}@${clean.toLowerCase()}.samanvaya.io` : prev.hr.email,
            }
        }));
    };

    // Load admin profile and data
    const loadAdminData = async (keyToUse = adminKey) => {
        setLoading(true);
        setAuthError('');
        try {
            const [profileData, statsData, companiesData] = await Promise.all([
                adminAPI.getProfile(keyToUse),
                adminAPI.getStats(keyToUse),
                adminAPI.getCompanies(keyToUse)
            ]);
            setProfile(profileData);
            setStats(statsData);
            setCompanies(companiesData || []);
            setIsAuthenticated(true);
            sessionStorage.setItem('samanvaya_admin_key', keyToUse);
        } catch (err) {
            console.error('Admin authentication failed:', err);
            setIsAuthenticated(false);
            setAuthError(err.message || 'Administrative verification failed. Invalid master key or credentials.');
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        loadAdminData();
    }, []);

    // Tab change sync with URL
    const handleTabChange = (tab) => {
        setActiveTab(tab);
        if (tab === 'profile') navigate('/admin/profile');
        else if (tab === 'companies') navigate('/admin/companies');
        else if (tab === 'create') navigate('/admin/create-company');
    };

    // Copy to clipboard helper
    const handleCopy = (text, key) => {
        navigator.clipboard.writeText(text);
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
    };

    // Submit Provisioning
    const handleProvision = async (e) => {
        e.preventDefault();
        setProvisionError('');
        setProvisionSuccess(null);
        setProvisioning(true);

        try {
            const result = await adminAPI.provisionCompany(formData, adminKey);
            setProvisionSuccess(result);
            if (refreshCompanies) refreshCompanies();
            await loadAdminData(adminKey);
        } catch (err) {
            console.error('Provisioning failed:', err);
            setProvisionError(err.message || 'Failed to provision company.');
        } finally {
            setProvisioning(false);
        }
    };

    // Submit Reassignment
    const handleReassignSubmit = async (e) => {
        e.preventDefault();
        try {
            await adminAPI.reassignLeader(reassignModal.company.id, {
                role: reassignModal.role,
                leader: {
                    name: reassignModal.name,
                    email: reassignModal.email,
                    employee_id: reassignModal.employee_id,
                    password: reassignModal.password || 'Emp@123',
                    phone: reassignModal.phone
                }
            }, adminKey);
            setReassignModal({ isOpen: false, company: null, role: 'CEO', name: '', email: '', employee_id: '', password: '', phone: '' });
            await loadAdminData(adminKey);
        } catch (err) {
            alert(`Reassignment failed: ${err.message}`);
        }
    };

    return (
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '16px 20px 48px' }}>
            {/* Header Banner */}
            <div style={{
                background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 60%, #4338ca 100%)',
                borderRadius: 'var(--radius-lg)',
                padding: '24px 32px',
                color: '#ffffff',
                marginBottom: 24,
                boxShadow: '0 10px 25px -5px rgba(30, 27, 75, 0.3)',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                flexWrap: 'wrap',
                gap: 16
            }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
                    <div style={{
                        width: 52,
                        height: 52,
                        borderRadius: 14,
                        background: 'rgba(255, 255, 255, 0.15)',
                        backdropFilter: 'blur(8px)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        border: '1px solid rgba(255, 255, 255, 0.25)'
                    }}>
                        <Shield size={28} color="#a5b4fc" />
                    </div>
                    <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                            <h1 style={{ margin: 0, fontSize: '1.45rem', fontWeight: 800, letterSpacing: '-0.02em' }}>
                                Samanvaya SuperAdmin
                            </h1>
                            <span style={{
                                background: '#10b981',
                                color: '#ffffff',
                                fontSize: '0.68rem',
                                padding: '2px 8px',
                                borderRadius: 12,
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em'
                            }}>
                                Backend Isolated
                            </span>
                        </div>
                        <p style={{ margin: '4px 0 0', fontSize: '0.86rem', opacity: 0.85 }}>
                            Internal tenant orchestration & executive leadership provisioning • <code style={{ background: 'rgba(255,255,255,0.12)', padding: '2px 6px', borderRadius: 4 }}>samanvaya.admin/profile</code>
                        </p>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <button
                        onClick={() => { setRefreshing(true); loadAdminData(adminKey); }}
                        className="btn btn-secondary btn-sm"
                        style={{
                            background: 'rgba(255, 255, 255, 0.12)',
                            color: '#ffffff',
                            border: '1px solid rgba(255, 255, 255, 0.25)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6
                        }}
                        disabled={refreshing}
                    >
                        <RefreshCw size={14} className={refreshing ? 'spin' : ''} />
                        <span>Refresh</span>
                    </button>
                    <button
                        onClick={() => navigate('/dashboard')}
                        className="btn btn-sm"
                        style={{
                            background: '#ffffff',
                            color: '#1e1b4b',
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            gap: 6
                        }}
                    >
                        <span>Exit to App</span>
                        <ArrowRight size={14} />
                    </button>
                </div>
            </div>

            {/* Admin Security Unlock Gate (Shown only if not authenticated) */}
            {!isAuthenticated && !loading && (
                <AnimatedCard delay={0}>
                    <div className="card-body" style={{ textAlign: 'center', padding: '48px 24px', maxWidth: 520, margin: '0 auto' }}>
                        <div style={{
                            width: 64,
                            height: 64,
                            borderRadius: '50%',
                            background: '#fee2e2',
                            color: '#ef4444',
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            marginBottom: 16
                        }}>
                            <Lock size={30} />
                        </div>
                        <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 8px' }}>
                            Restricted Backend Authentication
                        </h2>
                        <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: 24, lineHeight: 1.5 }}>
                            This administrative portal controls multi-tenant provisioning and executive credentials. Public API access is forbidden.
                        </p>

                        {authError && (
                            <div style={{
                                background: '#fef2f2',
                                color: '#b91c1c',
                                padding: '10px 14px',
                                borderRadius: 'var(--radius-sm)',
                                fontSize: '0.84rem',
                                marginBottom: 16,
                                textAlign: 'left',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8
                            }}>
                                <AlertTriangle size={16} flexShrink={0} />
                                <span>{authError}</span>
                            </div>
                        )}

                        <form onSubmit={(e) => { e.preventDefault(); setAdminKey(keyInput); loadAdminData(keyInput); }}>
                            <div style={{ marginBottom: 16 }}>
                                <label style={{ display: 'block', textAlign: 'left', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                    Master Admin Secret Key
                                </label>
                                <input
                                    type="password"
                                    className="form-control"
                                    placeholder="Enter administrative secret key..."
                                    value={keyInput}
                                    onChange={(e) => setKeyInput(e.target.value)}
                                    style={{ width: '100%', padding: '10px 14px', borderRadius: 'var(--radius-sm)' }}
                                    autoFocus
                                />
                                <span style={{ display: 'block', textAlign: 'left', fontSize: '0.74rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                                    Default master secret: <code>samanvaya-admin-2026</code>
                                </span>
                            </div>
                            <button
                                type="submit"
                                className="btn btn-primary"
                                style={{ width: '100%', padding: '10px 0', fontWeight: 700 }}
                            >
                                Verify & Access Admin Suite
                            </button>
                        </form>
                    </div>
                </AnimatedCard>
            )}

            {/* Authenticated Navigation Tabs */}
            {isAuthenticated && (
                <>
                    <div style={{
                        display: 'flex',
                        gap: 8,
                        marginBottom: 20,
                        borderBottom: '1px solid var(--border-color)',
                        paddingBottom: 8
                    }}>
                        <button
                            onClick={() => handleTabChange('profile')}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: '0.88rem',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                background: activeTab === 'profile' ? 'var(--brand-primary, #c0392b)' : 'transparent',
                                color: activeTab === 'profile' ? '#ffffff' : 'var(--text-secondary)'
                            }}
                        >
                            <Shield size={16} />
                            <span>Admin Profile (<code style={{ fontSize: '0.78rem' }}>samanvaya.admin/profile</code>)</span>
                        </button>

                        <button
                            onClick={() => handleTabChange('companies')}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: '0.88rem',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                background: activeTab === 'companies' ? 'var(--brand-primary, #c0392b)' : 'transparent',
                                color: activeTab === 'companies' ? '#ffffff' : 'var(--text-secondary)'
                            }}
                        >
                            <Building2 size={16} />
                            <span>Companies & Leadership ({companies.length})</span>
                        </button>

                        <button
                            onClick={() => handleTabChange('create')}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 8,
                                padding: '8px 16px',
                                borderRadius: 'var(--radius-md)',
                                border: 'none',
                                fontWeight: 700,
                                fontSize: '0.88rem',
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                background: activeTab === 'create' ? 'var(--brand-primary, #c0392b)' : 'transparent',
                                color: activeTab === 'create' ? '#ffffff' : 'var(--text-secondary)'
                            }}
                        >
                            <Plus size={16} />
                            <span>Provision New Company</span>
                        </button>
                    </div>

                    {/* ── TAB 1: ADMIN PROFILE (samanvaya.admin/profile) ── */}
                    {activeTab === 'profile' && profile && (
                        <div>
                            {/* KPI Metrics */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16, marginBottom: 24 }}>
                                <AnimatedCard delay={0}>
                                    <div className="card-body" style={{ padding: '20px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Total Registered Companies</span>
                                            <div style={{ padding: 8, borderRadius: 8, background: '#eff6ff', color: '#3b82f6' }}>
                                                <Building2 size={18} />
                                            </div>
                                        </div>
                                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                                            {profile.tenant_stats?.total_companies || companies.length}
                                        </div>
                                        <span style={{ fontSize: '0.74rem', color: '#10b981', fontWeight: 600 }}>Active Multi-Tenancy</span>
                                    </div>
                                </AnimatedCard>

                                <AnimatedCard delay={0.05}>
                                    <div className="card-body" style={{ padding: '20px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Assigned CEOs</span>
                                            <div style={{ padding: 8, borderRadius: 8, background: '#f5f3ff', color: '#8b5cf6' }}>
                                                <UserCheck size={18} />
                                            </div>
                                        </div>
                                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                                            {profile.tenant_stats?.assigned_ceos || 0}
                                        </div>
                                        <span style={{ fontSize: '0.74rem', color: '#8b5cf6', fontWeight: 600 }}>Executive Leadership</span>
                                    </div>
                                </AnimatedCard>

                                <AnimatedCard delay={0.1}>
                                    <div className="card-body" style={{ padding: '20px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Assigned HRs</span>
                                            <div style={{ padding: 8, borderRadius: 8, background: '#ecfdf5', color: '#10b981' }}>
                                                <Users size={18} />
                                            </div>
                                        </div>
                                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                                            {profile.tenant_stats?.assigned_hrs || 0}
                                        </div>
                                        <span style={{ fontSize: '0.74rem', color: '#10b981', fontWeight: 600 }}>People & Operations</span>
                                    </div>
                                </AnimatedCard>

                                <AnimatedCard delay={0.15}>
                                    <div className="card-body" style={{ padding: '20px' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
                                            <span style={{ fontSize: '0.82rem', fontWeight: 600, color: 'var(--text-secondary)' }}>Public API Shield</span>
                                            <div style={{ padding: 8, borderRadius: 8, background: '#ecfdf5', color: '#10b981' }}>
                                                <Shield size={18} />
                                            </div>
                                        </div>
                                        <div style={{ fontSize: '1.8rem', fontWeight: 800, color: '#10b981' }}>
                                            {profile.security_score}%
                                        </div>
                                        <span style={{ fontSize: '0.74rem', color: '#10b981', fontWeight: 600 }}>Zero Public Exposure</span>
                                    </div>
                                </AnimatedCard>
                            </div>

                            {/* System Profile Details */}
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 20 }}>
                                <AnimatedCard delay={0.2}>
                                    <div className="card-body" style={{ padding: 24 }}>
                                        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <Server size={18} color="var(--brand-primary)" />
                                            <span>Administrative Identity & Node</span>
                                        </h3>

                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                                <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>System Profile URL</span>
                                                <span style={{ fontSize: '0.84rem', fontWeight: 700, color: 'var(--brand-primary)' }}>
                                                    <code>{profile.profile_url}</code>
                                                </span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                                <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>Platform Administrator</span>
                                                <span style={{ fontSize: '0.84rem', fontWeight: 700 }}>{profile.authenticated_as}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                                <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>Administrative Role</span>
                                                <span className="badge badge-success" style={{ fontSize: '0.72rem' }}>{profile.admin_role}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid var(--border-color)' }}>
                                                <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>System License</span>
                                                <span style={{ fontSize: '0.84rem', fontWeight: 600 }}>{profile.license?.tier}</span>
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0' }}>
                                                <span style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>System Status</span>
                                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#10b981', fontWeight: 700, fontSize: '0.84rem' }}>
                                                    <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981' }} />
                                                    {profile.system_status}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </AnimatedCard>

                                <AnimatedCard delay={0.25}>
                                    <div className="card-body" style={{ padding: 24 }}>
                                        <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: '0 0 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
                                            <Lock size={18} color="#10b981" />
                                            <span>Security & Privacy Policies</span>
                                        </h3>

                                        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                                            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                                                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
                                                    Public API Shielding
                                                </div>
                                                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                                    Sensitive company credentials and administrative profiles are filtered out from public endpoints (<code>/api/companies</code>, <code>/api/homepage</code>).
                                                </div>
                                            </div>

                                            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                                                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
                                                    Dual-Password Cryptography
                                                </div>
                                                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                                    Organization master password and individual employee personal passwords use independent salted Bcrypt-12 encryption.
                                                </div>
                                            </div>

                                            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)' }}>
                                                <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 2 }}>
                                                    Immutable Audit Trail
                                                </div>
                                                <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                                    All tenant additions, CEO assignments, and HR onboarding are logged to persistent database records with timestamps and actor telemetry.
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </AnimatedCard>
                            </div>

                            {/* Recent Audit Trail */}
                            <div style={{ marginTop: 24 }}>
                                <AnimatedCard delay={0.3}>
                                    <div className="card-body" style={{ padding: 24 }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
                                            <h3 style={{ fontSize: '1.05rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
                                                <Activity size={18} color="#3b82f6" />
                                                <span>Immutable Administrative Audit Trail</span>
                                            </h3>
                                            <span style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>Live Database Logs</span>
                                        </div>

                                        <div style={{ overflowX: 'auto' }}>
                                            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                                                <thead>
                                                    <tr style={{ borderBottom: '1.5px solid var(--border-color)', textAlign: 'left', color: 'var(--text-secondary)' }}>
                                                        <th style={{ padding: '8px 12px' }}>Timestamp</th>
                                                        <th style={{ padding: '8px 12px' }}>Action</th>
                                                        <th style={{ padding: '8px 12px' }}>Target Resource</th>
                                                        <th style={{ padding: '8px 12px' }}>Operator</th>
                                                        <th style={{ padding: '8px 12px' }}>Audit Details</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {profile.recent_audits?.map((log, i) => (
                                                        <tr key={log.id || i} style={{ borderBottom: '1px solid var(--border-color)' }}>
                                                            <td style={{ padding: '10px 12px', whiteSpace: 'nowrap', color: 'var(--text-tertiary)' }}>{log.time}</td>
                                                            <td style={{ padding: '10px 12px', fontWeight: 600 }}>{log.action}</td>
                                                            <td style={{ padding: '10px 12px' }}>{log.name}</td>
                                                            <td style={{ padding: '10px 12px' }}>
                                                                <span className="badge" style={{ fontSize: '0.7rem', background: '#eff6ff', color: '#1d4ed8' }}>
                                                                    {log.by}
                                                                </span>
                                                            </td>
                                                            <td style={{ padding: '10px 12px', color: 'var(--text-secondary)' }}>{log.details}</td>
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </AnimatedCard>
                            </div>
                        </div>
                    )}

                    {/* ── TAB 2: COMPANIES & LEADERSHIP DIRECTORY ── */}
                    {activeTab === 'companies' && (
                        <div>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
                                <div>
                                    <h2 style={{ fontSize: '1.25rem', fontWeight: 800, margin: '0 0 4px' }}>
                                        Registered Companies & Executive Leadership
                                    </h2>
                                    <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', margin: 0 }}>
                                        Every tenant has assigned CEO and HR credentials. Confidential credentials remain hidden from public APIs.
                                    </p>
                                </div>
                                <button
                                    onClick={() => handleTabChange('create')}
                                    className="btn btn-primary"
                                    style={{ display: 'flex', alignItems: 'center', gap: 6, fontWeight: 700 }}
                                >
                                    <Plus size={16} />
                                    <span>Provision Company</span>
                                </button>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 20 }}>
                                {companies.map((co, idx) => (
                                    <AnimatedCard key={co.id || idx} delay={idx * 0.05}>
                                        <div className="card-body" style={{ padding: 24, display: 'flex', flexDirection: 'column', height: '100%' }}>
                                            {/* Company Header */}
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                                                <div>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                        <h3 style={{ fontSize: '1.1rem', fontWeight: 800, margin: 0 }}>{co.name}</h3>
                                                        <span className="badge badge-info" style={{ fontSize: '0.72rem', fontWeight: 700 }}>
                                                            {co.code || co.id}
                                                        </span>
                                                    </div>
                                                    <div style={{ fontSize: '0.78rem', color: 'var(--text-tertiary)', marginTop: 4 }}>
                                                        ID: <code>{co.id}</code> • {co.industry}
                                                    </div>
                                                </div>
                                                <span style={{
                                                    fontSize: '0.72rem',
                                                    padding: '2px 8px',
                                                    borderRadius: 12,
                                                    fontWeight: 700,
                                                    background: '#ecfdf5',
                                                    color: '#10b981'
                                                }}>
                                                    {co.status || 'Active'}
                                                </span>
                                            </div>

                                            {/* Domain & Location */}
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
                                                {co.domain && (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <Globe size={14} />
                                                        <span>{co.domain}</span>
                                                    </div>
                                                )}
                                                {co.location && (
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <MapPin size={14} />
                                                        <span>{co.location}</span>
                                                    </div>
                                                )}
                                            </div>

                                            {/* Assigned Leadership Section */}
                                            <div style={{
                                                background: 'var(--bg-secondary)',
                                                borderRadius: 'var(--radius-sm)',
                                                padding: '14px',
                                                border: '1px solid var(--border-color)',
                                                marginBottom: 16
                                            }}>
                                                <div style={{ fontSize: '0.74rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 10 }}>
                                                    Assigned Executive Leadership
                                                </div>

                                                {/* CEO Item */}
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                        <span style={{ background: '#8b5cf6', color: '#fff', fontSize: '0.65rem', fontWeight: 800, padding: '2px 6px', borderRadius: 4 }}>
                                                            CEO
                                                        </span>
                                                        <div>
                                                            <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>
                                                                {co.ceo?.name || 'Alexander Sterling'}
                                                            </div>
                                                            <div style={{ fontSize: '0.74rem', color: 'var(--text-tertiary)' }}>
                                                                {co.ceo?.email || 'ceo@samanvaya.io'} • <code>{co.ceo?.employee_id || 'EMP-CEO-001'}</code>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <button
                                                        onClick={() => setReassignModal({
                                                            isOpen: true,
                                                            company: co,
                                                            role: 'CEO',
                                                            name: co.ceo?.name || '',
                                                            email: co.ceo?.email || '',
                                                            employee_id: co.ceo?.employee_id || '',
                                                            password: '',
                                                            phone: co.ceo?.phone || ''
                                                        })}
                                                        className="btn btn-sm"
                                                        style={{ fontSize: '0.72rem', padding: '2px 8px', background: 'transparent', border: '1px solid var(--border-color)' }}
                                                    >
                                                        Edit
                                                    </button>
                                                </div>

                                                {/* HR Item */}
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                                        <span style={{ background: '#10b981', color: '#fff', fontSize: '0.65rem', fontWeight: 800, padding: '2px 6px', borderRadius: 4 }}>
                                                            HR
                                                        </span>
                                                        <div>
                                                            <div style={{ fontWeight: 700, fontSize: '0.84rem' }}>
                                                                {co.hr?.name || 'Priya Sharma'}
                                                            </div>
                                                            <div style={{ fontSize: '0.74rem', color: 'var(--text-tertiary)' }}>
                                                                {co.hr?.email || 'hr@samanvaya.io'} • <code>{co.hr?.employee_id || 'EMP-HR-001'}</code>
                                                            </div>
                                                        </div>
                                                    </div>
                                                    <button
                                                        onClick={() => setReassignModal({
                                                            isOpen: true,
                                                            company: co,
                                                            role: 'HR',
                                                            name: co.hr?.name || '',
                                                            email: co.hr?.email || '',
                                                            employee_id: co.hr?.employee_id || '',
                                                            password: '',
                                                            phone: co.hr?.phone || ''
                                                        })}
                                                        className="btn btn-sm"
                                                        style={{ fontSize: '0.72rem', padding: '2px 8px', background: 'transparent', border: '1px solid var(--border-color)' }}
                                                    >
                                                        Edit
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Footer stats */}
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: 8, fontSize: '0.78rem', color: 'var(--text-tertiary)' }}>
                                                <span>Active Employees: <strong style={{ color: 'var(--text-primary)' }}>{co.employee_count || 2}</strong></span>
                                                <span>Projects: <strong style={{ color: 'var(--text-primary)' }}>{co.project_count || 0}</strong></span>
                                            </div>
                                        </div>
                                    </AnimatedCard>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* ── TAB 3: PROVISION COMPANY & ASSIGN LEADERSHIP WIZARD ── */}
                    {activeTab === 'create' && (
                        <div style={{ maxWidth: 860, margin: '0 auto' }}>
                            <div style={{ marginBottom: 24, textAlign: 'center' }}>
                                <h2 style={{ fontSize: '1.4rem', fontWeight: 800, margin: '0 0 6px' }}>
                                    Provision New Company & Executive Leadership
                                </h2>
                                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', margin: 0 }}>
                                    Atomically registers the company tenant and initializes CEO and HR administrator accounts with encrypted passwords.
                                </p>
                            </div>

                            {/* Provision Success Alert */}
                            {provisionSuccess && (
                                <div style={{
                                    background: '#ecfdf5',
                                    border: '1.5px solid #10b981',
                                    borderRadius: 'var(--radius-md)',
                                    padding: '20px',
                                    marginBottom: 24,
                                    boxShadow: '0 4px 12px rgba(16, 185, 129, 0.15)'
                                }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#065f46', marginBottom: 12 }}>
                                        <CheckCircle2 size={24} color="#10b981" />
                                        <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 800 }}>
                                            {provisionSuccess.message}
                                        </h3>
                                    </div>
                                    <div style={{ fontSize: '0.84rem', color: '#047857', display: 'flex', flexDirection: 'column', gap: 6 }}>
                                        <div>Company Tenant ID: <strong>{provisionSuccess.company?.id}</strong></div>
                                        <div>CEO Employee ID: <strong>{provisionSuccess.assigned_leaders?.ceo?.employee_id}</strong> ({provisionSuccess.assigned_leaders?.ceo?.email})</div>
                                        <div>HR Employee ID: <strong>{provisionSuccess.assigned_leaders?.hr?.employee_id}</strong> ({provisionSuccess.assigned_leaders?.hr?.email})</div>
                                    </div>
                                    <div style={{ marginTop: 14, display: 'flex', gap: 10 }}>
                                        <button
                                            onClick={() => handleTabChange('companies')}
                                            className="btn btn-primary btn-sm"
                                            style={{ background: '#059669', borderColor: '#059669' }}
                                        >
                                            View in Companies Directory
                                        </button>
                                        <button
                                            onClick={() => {
                                                setProvisionSuccess(null);
                                                setFormData({
                                                    code: '',
                                                    name: '',
                                                    domain: '',
                                                    industry: 'Enterprise AI & Cloud Software',
                                                    location: 'Bengaluru HQ (Whitefield), Karnataka',
                                                    company_password: 'Company@org123',
                                                    description: '',
                                                    ceo: { name: '', email: '', employee_id: '', password: 'Emp@ceo123', phone: '', bio: '' },
                                                    hr: { name: '', email: '', employee_id: '', password: 'Emp@hr123', phone: '' }
                                                });
                                            }}
                                            className="btn btn-secondary btn-sm"
                                        >
                                            Provision Another Company
                                        </button>
                                    </div>
                                </div>
                            )}

                            {/* Provision Error Alert */}
                            {provisionError && (
                                <div style={{
                                    background: '#fef2f2',
                                    border: '1.5px solid #ef4444',
                                    borderRadius: 'var(--radius-md)',
                                    padding: '16px',
                                    color: '#b91c1c',
                                    marginBottom: 24,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: 10
                                }}>
                                    <AlertTriangle size={20} flexShrink={0} />
                                    <span style={{ fontSize: '0.88rem', fontWeight: 600 }}>{provisionError}</span>
                                </div>
                            )}

                            <form onSubmit={handleProvision}>
                                {/* SECTION 1: COMPANY PROFILE */}
                                <AnimatedCard delay={0}>
                                    <div className="card-body" style={{ padding: 28, marginBottom: 20 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, paddingBottom: 12, borderBottom: '1.5px solid var(--border-color)' }}>
                                            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#eff6ff', color: '#3b82f6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                <Building2 size={18} />
                                            </div>
                                            <div>
                                                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800 }}>1. Company Tenant Details</h3>
                                                <span style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>Basic organization information and tenant configuration</span>
                                            </div>
                                        </div>

                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    Company Name <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. Acme Innovations Corp"
                                                    value={formData.name}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    Company Code (Ticker/Slug) <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. ACME"
                                                    value={formData.code}
                                                    onChange={(e) => handleCodeChange(e.target.value)}
                                                />
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 4, display: 'block' }}>
                                                    Unique abbreviation used for Employee IDs and prefixes.
                                                </span>
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    Domain / Website
                                                </label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    placeholder="e.g. acme.samanvaya.io"
                                                    value={formData.domain}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, domain: e.target.value }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    Industry / Domain
                                                </label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    placeholder="e.g. Enterprise AI & Robotics"
                                                    value={formData.industry}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, industry: e.target.value }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HQ Location
                                                </label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    placeholder="e.g. Bengaluru, Karnataka, India"
                                                    value={formData.location}
                                                    onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    Company-wide Organization Password <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <div style={{ position: 'relative' }}>
                                                    <input
                                                        type={showCompanyPwd ? 'text' : 'password'}
                                                        required
                                                        className="form-control"
                                                        placeholder="Organisation Password"
                                                        value={formData.company_password}
                                                        onChange={(e) => setFormData(prev => ({ ...prev, company_password: e.target.value }))}
                                                        style={{ paddingRight: 40 }}
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => setShowCompanyPwd(!showCompanyPwd)}
                                                        style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}
                                                    >
                                                        {showCompanyPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                                                    </button>
                                                </div>
                                                <span style={{ fontSize: '0.72rem', color: 'var(--text-tertiary)', marginTop: 4, display: 'block' }}>
                                                    Shared organization password used for dual-credential employee sign-in.
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </AnimatedCard>

                                {/* SECTION 2: CEO ASSIGNMENT */}
                                <AnimatedCard delay={0.08}>
                                    <div className="card-body" style={{ padding: 28, marginBottom: 20 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, paddingBottom: 12, borderBottom: '1.5px solid var(--border-color)' }}>
                                            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#f5f3ff', color: '#8b5cf6', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                <UserCheck size={18} />
                                            </div>
                                            <div>
                                                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800 }}>2. Assign CEO (Executive Leadership)</h3>
                                                <span style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>Chief Executive Officer responsible for strategic oversight and project execution</span>
                                            </div>
                                        </div>

                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    CEO Full Name <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. Vikram Malhotra"
                                                    value={formData.ceo.name}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        ceo: { ...prev.ceo, name: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    CEO Email Address <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="email"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. ceo@acme.samanvaya.io"
                                                    value={formData.ceo.email}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        ceo: { ...prev.ceo, email: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    CEO Employee ID <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. EMP-CEO-ACME-001"
                                                    value={formData.ceo.employee_id}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        ceo: { ...prev.ceo, employee_id: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    CEO Personal Password <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <div style={{ position: 'relative' }}>
                                                    <input
                                                        type={showCeoPwd ? 'text' : 'password'}
                                                        required
                                                        className="form-control"
                                                        placeholder="Personal Password"
                                                        value={formData.ceo.password}
                                                        onChange={(e) => setFormData(prev => ({
                                                            ...prev,
                                                            ceo: { ...prev.ceo, password: e.target.value }
                                                        }))}
                                                        style={{ paddingRight: 40 }}
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => setShowCeoPwd(!showCeoPwd)}
                                                        style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}
                                                    >
                                                        {showCeoPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                                                    </button>
                                                </div>
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    CEO Phone Number
                                                </label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    placeholder="+91 98450 11223"
                                                    value={formData.ceo.phone}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        ceo: { ...prev.ceo, phone: e.target.value }
                                                    }))}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </AnimatedCard>

                                {/* SECTION 3: HR ASSIGNMENT */}
                                <AnimatedCard delay={0.16}>
                                    <div className="card-body" style={{ padding: 28, marginBottom: 24 }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 20, paddingBottom: 12, borderBottom: '1.5px solid var(--border-color)' }}>
                                            <div style={{ width: 34, height: 34, borderRadius: 8, background: '#ecfdf5', color: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                <Users size={18} />
                                            </div>
                                            <div>
                                                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 800 }}>3. Assign HR (People & Talent Management)</h3>
                                                <span style={{ fontSize: '0.76rem', color: 'var(--text-tertiary)' }}>Human Resources head managing employees, invitations, and company settings</span>
                                            </div>
                                        </div>

                                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 16 }}>
                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HR Full Name <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. Ananya Sen"
                                                    value={formData.hr.name}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        hr: { ...prev.hr, name: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HR Email Address <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="email"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. hr@acme.samanvaya.io"
                                                    value={formData.hr.email}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        hr: { ...prev.hr, email: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HR Employee ID <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <input
                                                    type="text"
                                                    required
                                                    className="form-control"
                                                    placeholder="e.g. EMP-HR-ACME-001"
                                                    value={formData.hr.employee_id}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        hr: { ...prev.hr, employee_id: e.target.value }
                                                    }))}
                                                />
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HR Personal Password <span style={{ color: '#ef4444' }}>*</span>
                                                </label>
                                                <div style={{ position: 'relative' }}>
                                                    <input
                                                        type={showHrPwd ? 'text' : 'password'}
                                                        required
                                                        className="form-control"
                                                        placeholder="Personal Password"
                                                        value={formData.hr.password}
                                                        onChange={(e) => setFormData(prev => ({
                                                            ...prev,
                                                            hr: { ...prev.hr, password: e.target.value }
                                                        }))}
                                                        style={{ paddingRight: 40 }}
                                                    />
                                                    <button
                                                        type="button"
                                                        onClick={() => setShowHrPwd(!showHrPwd)}
                                                        style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer' }}
                                                    >
                                                        {showHrPwd ? <EyeOff size={16} /> : <Eye size={16} />}
                                                    </button>
                                                </div>
                                            </div>

                                            <div>
                                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 6 }}>
                                                    HR Phone Number
                                                </label>
                                                <input
                                                    type="text"
                                                    className="form-control"
                                                    placeholder="+91 98450 44556"
                                                    value={formData.hr.phone}
                                                    onChange={(e) => setFormData(prev => ({
                                                        ...prev,
                                                        hr: { ...prev.hr, phone: e.target.value }
                                                    }))}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                </AnimatedCard>

                                {/* Action Submit Button */}
                                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 12 }}>
                                    <button
                                        type="button"
                                        onClick={() => handleTabChange('companies')}
                                        className="btn btn-secondary"
                                        style={{ padding: '12px 24px', fontWeight: 600 }}
                                    >
                                        Cancel
                                    </button>
                                    <button
                                        type="submit"
                                        className="btn btn-primary"
                                        disabled={provisioning}
                                        style={{
                                            padding: '12px 32px',
                                            fontWeight: 800,
                                            fontSize: '0.95rem',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: 8,
                                            boxShadow: '0 4px 14px rgba(192, 57, 43, 0.4)'
                                        }}
                                    >
                                        {provisioning ? (
                                            <>
                                                <span className="spin" style={{ display: 'inline-block' }}>⏳</span>
                                                <span>Provisioning Company & Leaders...</span>
                                            </>
                                        ) : (
                                            <>
                                                <Sparkles size={18} />
                                                <span>Provision Company & Assign Leaders</span>
                                            </>
                                        )}
                                    </button>
                                </div>
                            </form>
                        </div>
                    )}
                </>
            )}

            {/* Reassign Leader Modal */}
            {reassignModal.isOpen && (
                <div style={{
                    position: 'fixed',
                    top: 0,
                    left: 0,
                    right: 0,
                    bottom: 0,
                    background: 'rgba(0, 0, 0, 0.6)',
                    backdropFilter: 'blur(4px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    zIndex: 1000,
                    padding: 20
                }}>
                    <div style={{
                        background: 'var(--bg-card, #ffffff)',
                        borderRadius: 'var(--radius-lg)',
                        padding: '28px',
                        width: '100%',
                        maxWidth: 480,
                        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)'
                    }}>
                        <h3 style={{ margin: '0 0 6px', fontSize: '1.2rem', fontWeight: 800 }}>
                            Reassign {reassignModal.role} for {reassignModal.company?.name}
                        </h3>
                        <p style={{ margin: '0 0 20px', fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                            Update or assign a new executive to lead {reassignModal.role} operations.
                        </p>

                        <form onSubmit={handleReassignSubmit}>
                            <div style={{ marginBottom: 14 }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>Full Name</label>
                                <input
                                    type="text"
                                    required
                                    className="form-control"
                                    value={reassignModal.name}
                                    onChange={(e) => setReassignModal(prev => ({ ...prev, name: e.target.value }))}
                                />
                            </div>

                            <div style={{ marginBottom: 14 }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>Email</label>
                                <input
                                    type="email"
                                    required
                                    className="form-control"
                                    value={reassignModal.email}
                                    onChange={(e) => setReassignModal(prev => ({ ...prev, email: e.target.value }))}
                                />
                            </div>

                            <div style={{ marginBottom: 14 }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>Employee ID</label>
                                <input
                                    type="text"
                                    required
                                    className="form-control"
                                    value={reassignModal.employee_id}
                                    onChange={(e) => setReassignModal(prev => ({ ...prev, employee_id: e.target.value }))}
                                />
                            </div>

                            <div style={{ marginBottom: 20 }}>
                                <label style={{ display: 'block', fontSize: '0.82rem', fontWeight: 700, marginBottom: 4 }}>New Password (optional)</label>
                                <input
                                    type="password"
                                    className="form-control"
                                    placeholder="Leave blank to keep existing password"
                                    value={reassignModal.password}
                                    onChange={(e) => setReassignModal(prev => ({ ...prev, password: e.target.value }))}
                                />
                            </div>

                            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
                                <button
                                    type="button"
                                    onClick={() => setReassignModal({ isOpen: false, company: null, role: 'CEO', name: '', email: '', employee_id: '', password: '', phone: '' })}
                                    className="btn btn-secondary btn-sm"
                                >
                                    Cancel
                                </button>
                                <button type="submit" className="btn btn-primary btn-sm" style={{ fontWeight: 700 }}>
                                    Confirm Assignment
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

