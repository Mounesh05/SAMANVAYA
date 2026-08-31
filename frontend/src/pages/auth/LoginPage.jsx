import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { authApi } from '../../api/auth.api';
import { Card } from '../../components/common/Card';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import { Shield, Sparkles, AlertCircle, KeyRound, Mail, UserCheck } from 'lucide-react';
import { ROLES } from '../../utils/constants';

export function LoginPage() {
  const [activeTab, setActiveTab] = useState('simple'); // 'simple' | 'full'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Full login state
  const [employeeId, setEmployeeId] = useState('');
  const [orgPassword, setOrgPassword] = useState('');
  const [empPassword, setEmpPassword] = useState('');

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const { setAuth } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      let response;
      if (activeTab === 'simple') {
        if (!email || !password) {
          setError('Please provide both email and password');
          setIsLoading(false);
          return;
        }
        response = await authApi.login({ email, password });
      } else {
        if (!employeeId || !orgPassword || !empPassword) {
          setError('Please fill in all employee and organisation credentials');
          setIsLoading(false);
          return;
        }
        response = await authApi.loginFull({
          employee_id: employeeId,
          organisation_password: orgPassword,
          employee_password: empPassword,
        });
      }

      if (response && response.token) {
        setAuth(response.token, response.user);
        const role = response.user?.role?.toLowerCase() || 'developer';
        const from = location.state?.from?.pathname || `/${role}/dashboard`;
        navigate(from, { replace: true });
      } else {
        setError('Login failed: Token not received from server');
      }
    } catch (err) {
      setError(err.message || 'Authentication failed. Please check your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: '100vh',
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1.5rem',
        background: 'radial-gradient(ellipse at top, #1e293b 0%, #0a0e17 70%)',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background decoration elements */}
      <div
        style={{
          position: 'absolute',
          width: '500px',
          height: '500px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.15) 0%, rgba(0, 0, 0, 0) 70%)',
          top: '-100px',
          right: '-100px',
          pointerEvents: 'none',
        }}
      />
      <div
        style={{
          position: 'absolute',
          width: '400px',
          height: '400px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(168, 85, 247, 0.15) 0%, rgba(0, 0, 0, 0) 70%)',
          bottom: '-100px',
          left: '-100px',
          pointerEvents: 'none',
        }}
      />

      <div style={{ width: '100%', maxWidth: '440px', zIndex: 10 }}>
        {/* Brand Logo & Title */}
        <div style={{ textAlign: 'center', marginBottom: '2rem' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: 'var(--radius-lg)',
              background: 'linear-gradient(135deg, #3b82f6 0%, #a855f7 100%)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#fff',
              fontWeight: '900',
              fontSize: '1.75rem',
              boxShadow: '0 0 25px rgba(59, 130, 246, 0.4)',
              marginBottom: '1rem',
            }}
          >
            S
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: '800', letterSpacing: '-0.03em' }}>
            <span className="gradient-text">SAMANVAYA</span>
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-muted)', marginTop: '0.25rem' }}>
            AI-Powered Software Engineering & Performance Platform
          </p>
        </div>

        {/* Login Card */}
        <Card padding="lg" style={{ border: '1px solid var(--border-default)' }}>
          {/* Method Tabs */}
          <div
            style={{
              display: 'flex',
              background: 'var(--bg-input)',
              padding: '0.25rem',
              borderRadius: 'var(--radius-md)',
              marginBottom: '1.5rem',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <button
              type="button"
              onClick={() => {
                setActiveTab('simple');
                setError('');
              }}
              style={{
                flex: 1,
                padding: '0.45rem',
                fontSize: '0.8125rem',
                fontWeight: '600',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: activeTab === 'simple' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'simple' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
              }}
            >
              Email Login
            </button>
            <button
              type="button"
              onClick={() => {
                setActiveTab('full');
                setError('');
              }}
              style={{
                flex: 1,
                padding: '0.45rem',
                fontSize: '0.8125rem',
                fontWeight: '600',
                borderRadius: 'var(--radius-sm)',
                border: 'none',
                background: activeTab === 'full' ? 'var(--primary)' : 'transparent',
                color: activeTab === 'full' ? '#fff' : 'var(--text-muted)',
                cursor: 'pointer',
                transition: 'all var(--transition-fast)',
              }}
            >
              Org / Employee ID
            </button>
          </div>

          {error && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem',
                padding: '0.75rem 1rem',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--danger-light)',
                border: '1px solid var(--danger-border)',
                color: 'var(--danger)',
                fontSize: '0.8125rem',
                marginBottom: '1.25rem',
              }}
            >
              <AlertCircle size={16} style={{ flexShrink: 0 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.15rem' }}>
            {activeTab === 'simple' ? (
              <>
                <Input
                  label="Email Address"
                  type="email"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  leftIcon={<Mail size={16} />}
                  required
                />
                <Input
                  label="Password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  leftIcon={<KeyRound size={16} />}
                  required
                />
              </>
            ) : (
              <>
                <Input
                  label="Employee ID"
                  placeholder="e.g. E001 or DEV001"
                  value={employeeId}
                  onChange={(e) => setEmployeeId(e.target.value)}
                  leftIcon={<UserCheck size={16} />}
                  required
                />
                <Input
                  label="Organisation Password"
                  type="password"
                  placeholder="Org password"
                  value={orgPassword}
                  onChange={(e) => setOrgPassword(e.target.value)}
                  leftIcon={<Shield size={16} />}
                  required
                />
                <Input
                  label="Employee Password"
                  type="password"
                  placeholder="Employee password"
                  value={empPassword}
                  onChange={(e) => setEmpPassword(e.target.value)}
                  leftIcon={<KeyRound size={16} />}
                  required
                />
              </>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
              style={{ marginTop: '0.5rem', width: '100%' }}
            >
              Sign In to Samanvaya
            </Button>
          </form>
        </Card>

        {/* Footer info */}
        <p style={{ textAlign: 'center', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '1.5rem' }}>
          Role-aware system supporting DEVELOPER, LEAD, PM, QA, DEVOPS, HR, & CEO roles.
        </p>
      </div>
    </div>
  );
}
