import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { Bell, Building2, Check, CheckCircle2, Loader2, Shield } from 'lucide-react';

const roleColors = {
    CEO: '#8b5cf6',
    HR: '#10b981',
    PM: '#3b82f6',
    LEAD: '#f59e0b',
    DEVELOPER: '#06b6d4',
    DEVOPS: '#ec4899',
    QA: '#14b8a6',
};

export default function TopBar({ title }) {
    const { user, companies, currentCompany, switchCompany } = useAuth();
    const navigate = useNavigate();

    const currentCompanyIdentifier = currentCompany?.id || currentCompany?.code || '';
    const [selectedCompanyId, setSelectedCompanyId] = useState(currentCompanyIdentifier);
    const [isApplying, setIsApplying] = useState(false);
    const [appliedSuccess, setAppliedSuccess] = useState(false);

    useEffect(() => {
        if (currentCompanyIdentifier) {
            setSelectedCompanyId(currentCompanyIdentifier);
        }
    }, [currentCompanyIdentifier]);

    const hasPendingChanges = Boolean(selectedCompanyId && selectedCompanyId !== currentCompanyIdentifier);

    const handleApplyCompany = async () => {
        if (!selectedCompanyId) return;
        setIsApplying(true);
        try {
            switchCompany(selectedCompanyId);
            setAppliedSuccess(true);
            window.dispatchEvent(new CustomEvent('companyFilterApplied', {
                detail: { companyId: selectedCompanyId }
            }));
            setTimeout(() => {
                setAppliedSuccess(false);
            }, 2000);
        } catch (err) {
            console.error('Failed to apply company switch:', err);
        } finally {
            setIsApplying(false);
        }
    };

    return (
        <header className="topbar">
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <h1 className="topbar-title">{title}</h1>
                
                {/* Multi-Company Tenant Selector & Apply Button */}
                {companies && companies.length > 0 && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                background: 'var(--bg-secondary)',
                                padding: '4px 10px',
                                borderRadius: 'var(--radius-sm)',
                                border: hasPendingChanges ? '1.5px solid #3b82f6' : '1px solid var(--border-color)',
                                boxShadow: hasPendingChanges ? '0 0 0 2px rgba(59, 130, 246, 0.2)' : 'none',
                                transition: 'all 0.2s ease'
                            }}
                            title="Select Organization / Company Tenant"
                        >
                            <Building2 size={15} color={hasPendingChanges ? '#3b82f6' : 'var(--text-secondary)'} />
                            <select
                                id="topbar-company-select"
                                value={selectedCompanyId}
                                onChange={(e) => {
                                    setSelectedCompanyId(e.target.value);
                                    setAppliedSuccess(false);
                                }}
                                style={{
                                    background: 'transparent',
                                    border: 'none',
                                    fontSize: '0.82rem',
                                    fontWeight: 600,
                                    color: 'var(--text-primary)',
                                    outline: 'none',
                                    cursor: 'pointer'
                                }}
                            >
                                {companies.map(co => (
                                    <option key={co.id} value={co.id}>
                                        {co.name} ({co.code || co.id})
                                    </option>
                                ))}
                            </select>
                        </div>

                        {/* Apply Button */}
                        <button
                            id="topbar-company-apply-btn"
                            className="btn btn-sm"
                            onClick={handleApplyCompany}
                            disabled={isApplying || (!hasPendingChanges && !appliedSuccess)}
                            style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: 5,
                                padding: '5px 12px',
                                fontSize: '0.78rem',
                                fontWeight: 700,
                                borderRadius: 'var(--radius-sm)',
                                cursor: (hasPendingChanges || appliedSuccess) && !isApplying ? 'pointer' : 'default',
                                background: appliedSuccess
                                    ? '#10b981'
                                    : hasPendingChanges
                                        ? 'var(--primary-color, #c0392b)'
                                        : 'var(--bg-secondary)',
                                color: (appliedSuccess || hasPendingChanges) ? '#ffffff' : 'var(--text-tertiary)',
                                border: (appliedSuccess || hasPendingChanges) ? 'none' : '1px solid var(--border-color)',
                                boxShadow: hasPendingChanges ? '0 2px 8px rgba(192, 57, 43, 0.35)' : 'none',
                                transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                                opacity: (!hasPendingChanges && !appliedSuccess) ? 0.6 : 1,
                            }}
                            title={hasPendingChanges ? 'Apply selected company filter' : 'Filter already applied'}
                        >
                            {isApplying ? (
                                <>
                                    <Loader2 size={13} className="spin" />
                                    <span>Applying...</span>
                                </>
                            ) : appliedSuccess ? (
                                <>
                                    <CheckCircle2 size={13} />
                                    <span>Applied!</span>
                                </>
                            ) : (
                                <>
                                    <Check size={13} />
                                    <span>Apply</span>
                                </>
                            )}
                        </button>
                    </div>
                )}
            </div>

            <div className="topbar-right">
                {(user?.role === 'CEO' || user?.role === 'ADMIN' || user?.is_admin) && (
                    <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => navigate('/admin/profile')}
                        title="SuperAdmin Suite (samanvaya.admin/profile)"
                        style={{
                            borderRadius: 'var(--radius-sm)',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 5,
                            fontSize: '0.78rem',
                            fontWeight: 700,
                            padding: '5px 10px',
                            color: '#4338ca',
                            background: '#e0e7ff',
                            border: '1px solid #c7d2fe',
                            cursor: 'pointer'
                        }}
                    >
                        <Shield size={14} />
                        <span>Admin</span>
                    </button>
                )}
                <button className="btn btn-secondary btn-sm" style={{ borderRadius: '50%', width: 36, height: 36, padding: 0 }}>
                    <Bell size={18} />
                </button>
                <div
                    className="topbar-user topbar-user-clickable"
                    onClick={() => navigate('/profile')}
                    title="View Profile"
                    style={{ display: 'flex', alignItems: 'center', gap: 10 }}
                >
                    <div className="topbar-avatar">{user?.avatar || (user?.name ? user.name.slice(0, 2).toUpperCase() : 'U')}</div>
                    <div>
                        <div className="topbar-username" style={{ fontWeight: 600, fontSize: '0.85rem' }}>{user?.name || 'Administrator'}</div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span
                                className="badge"
                                style={{
                                    fontSize: '0.68rem',
                                    padding: '1px 6px',
                                    background: `${roleColors[user?.role] || '#3b82f6'}20`,
                                    color: roleColors[user?.role] || '#3b82f6',
                                    fontWeight: 700
                                }}
                            >
                                {user?.role || 'SYSTEM'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        </header>
    );
}
