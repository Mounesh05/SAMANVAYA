import React from 'react';
import { useAuthStore } from '../../store/useAuthStore';
import { PageHeader } from '../../components/layout/PageHeader';
import { Card } from '../../components/common/Card';
import { Button } from '../../components/common/Button';
import { ROLE_LABELS, ROLE_COLORS } from '../../utils/constants';
import { User, Mail, Shield, Building2, GitPullRequest, KeyRound, LogOut } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export function ProfilePage() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

  const role = user?.role?.toUpperCase() || 'DEVELOPER';
  const roleColor = ROLE_COLORS[role] || '#3b82f6';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div>
      <PageHeader
        title="User Profile & Settings"
        subtitle="Manage account information, organizational role, and notification preferences."
        actions={
          <Button variant="danger" leftIcon={<LogOut size={16} />} onClick={handleLogout}>
            Sign Out
          </Button>
        }
      />

      <div style={{ maxWidth: '680px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
        {/* Profile Card */}
        <Card padding="lg">
          <div style={{ display: 'flex', alignItems: 'center', gap: '1.25rem', marginBottom: '1.5rem' }}>
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '50%',
                backgroundColor: `${roleColor}25`,
                border: `2px solid ${roleColor}`,
                color: roleColor,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: '900',
                fontSize: '1.75rem',
              }}
            >
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div>
              <h2 style={{ fontSize: '1.25rem', fontWeight: '800', color: 'var(--text-primary)' }}>
                {user?.name || 'User'}
              </h2>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.25rem' }}>
                <span
                  style={{
                    padding: '0.15rem 0.5rem',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: `${roleColor}20`,
                    color: roleColor,
                    fontWeight: '700',
                    fontSize: '0.75rem',
                  }}
                >
                  {ROLE_LABELS[role] || role}
                </span>
                <span style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
                  ID: <strong className="font-mono">{user?.employee_id || 'E001'}</strong>
                </span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', fontSize: '0.875rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                <Mail size={16} /> Email Address
              </span>
              <strong style={{ color: 'var(--text-primary)' }}>{user?.email || '—'}</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                <Building2 size={16} /> Department
              </span>
              <strong style={{ color: 'var(--text-primary)' }}>{user?.dept || 'Engineering'}</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                <GitPullRequest size={16} /> GitHub Username
              </span>
              <strong style={{ color: 'var(--text-primary)' }}>{user?.github_username || 'Not connected'}</strong>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 0', borderTop: '1px solid var(--border-subtle)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)' }}>
                <Shield size={16} /> Security Role
              </span>
              <strong style={{ color: roleColor }}>{role}</strong>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
