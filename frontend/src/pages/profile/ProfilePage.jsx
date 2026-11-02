/**
 * Profile Page — all authenticated roles
 */
import { useAuth } from '../../auth/AuthContext';
import { RoleBadge } from '../../components/common/Badges';
import { formatDate } from '../../utils/dates';
import { User, Mail, Building2, GitBranch, Calendar, Shield } from 'lucide-react';
import { initials } from '../../utils/formatters';

export function ProfilePage() {
  const { user } = useAuth();

  if (!user) return null;

  const fields = [
    { icon: User,      label: 'Full Name',    value: user.name },
    { icon: Mail,      label: 'Email',        value: user.email },
    { icon: Shield,    label: 'Role',         value: user.role, render: () => <RoleBadge role={user.role} /> },
    { icon: Building2, label: 'Department',   value: user.dept },
    { icon: GitBranch, label: 'GitHub',       value: user.github_username || '—' },
    { icon: Calendar,  label: 'Employee ID',  value: user.employee_id },
  ];

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">Your account information</p>
        </div>
      </div>

      <div style={{ maxWidth: 640 }}>
        {/* Avatar + name card */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-6)', marginBottom: 'var(--space-6)' }}>
          <div
            className="avatar avatar-xl"
            style={{ fontSize: '1.5rem', background: 'linear-gradient(135deg, var(--brand-500), var(--brand-700))', boxShadow: 'var(--shadow-glow)' }}
            aria-hidden="true"
          >
            {initials(user.name)}
          </div>
          <div>
            <div style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>
              {user.name}
            </div>
            <RoleBadge role={user.role} />
            {user.dept && (
              <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: 4 }}>
                {user.dept}
              </div>
            )}
          </div>
        </div>

        {/* Detail fields */}
        <div className="card">
          <div className="card-header">
            <div className="card-title">Account Details</div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            {fields.map((field, i) => {
              const Icon = field.icon;
              return (
                <div
                  key={field.label}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-4)',
                    padding: 'var(--space-4) 0',
                    borderBottom: i < fields.length - 1 ? '1px solid var(--border)' : 'none',
                  }}
                >
                  <div style={{ width: 36, height: 36, borderRadius: 'var(--radius-md)', background: 'var(--bg-elevated)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)', flexShrink: 0 }}>
                    <Icon size={16} aria-hidden="true" />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: '0.6875rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 2 }}>
                      {field.label}
                    </div>
                    <div style={{ fontSize: '0.875rem', color: 'var(--text-primary)', fontWeight: 500 }}>
                      {field.render ? field.render() : (field.value || '—')}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="card" style={{ marginTop: 'var(--space-4)', borderColor: 'var(--border-light)' }}>
          <div style={{ fontSize: '0.8125rem', color: 'var(--text-muted)' }}>
            To update your profile information, contact your HR administrator.
          </div>
        </div>
      </div>
    </div>
  );
}
