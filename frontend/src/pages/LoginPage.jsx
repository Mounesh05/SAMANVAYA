import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth, MOCK_USERS, COMPANY_PASSWORD } from '../context/AuthContext';
import { LogIn, Eye, EyeOff, ShieldCheck, KeyRound, User } from 'lucide-react';

export default function LoginPage() {
    const [userId, setUserId] = useState('');
    const [companyPwd, setCompanyPwd] = useState('');
    const [personalPwd, setPersonalPwd] = useState('');
    const [showCompanyPwd, setShowCompanyPwd] = useState(false);
    const [showPersonalPwd, setShowPersonalPwd] = useState(false);
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);
    const { login } = useAuth();
    const navigate = useNavigate();

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        await new Promise(r => setTimeout(r, 600));
        const result = await login(userId, companyPwd, personalPwd);
        if (result.success) {
            navigate('/dashboard', { replace: true });
        } else {
            setError(result.error);
        }
        setLoading(false);
    };

    return (
        <div className="login-form-section">
            <div className="login-card">
                {/* Welcome heading */}
                <div className="login-brand" style={{ textAlign: 'center' }}>
                    <img
                        src="/logo.jpeg"
                        alt="Samanvaya"
                        style={{
                            width: 84,
                            height: 84,
                            borderRadius: 18,
                            marginBottom: 14,
                            objectFit: 'cover',
                            boxShadow: '0 6px 28px rgba(99, 102, 241, 0.65), 0 0 50px rgba(56, 189, 248, 0.35)',
                            border: '2px solid rgba(255, 255, 255, 0.35)',
                            display: 'inline-block'
                        }}
                    />
                    <div className="login-brand-name">Welcome Back</div>
                    <p className="login-brand-tagline">Sign in to access your dashboard</p>
                </div>

                {error && <div className="login-error">{error}</div>}

                <form onSubmit={handleSubmit}>
                    {/* User ID */}
                    <div className="form-group">
                        <label className="form-label"><User size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> User ID</label>
                        <input className="form-input" type="text" placeholder="e.g. EMP-CEO-001"
                            value={userId} onChange={(e) => setUserId(e.target.value)} autoFocus required />
                    </div>

                    {/* Company Password */}
                    <div className="form-group">
                        <label className="form-label"><ShieldCheck size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Company Password</label>
                        <div style={{ position: 'relative' }}>
                            <input className="form-input" type={showCompanyPwd ? 'text' : 'password'}
                                placeholder="Enter institutional password"
                                value={companyPwd} onChange={(e) => setCompanyPwd(e.target.value)} required />
                            <button type="button" onClick={() => setShowCompanyPwd(!showCompanyPwd)}
                                style={{
                                    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                                    color: 'var(--text-tertiary)', background: 'none', border: 'none', cursor: 'pointer'
                                }}>
                                {showCompanyPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    {/* Personal Password */}
                    <div className="form-group">
                        <label className="form-label"><KeyRound size={14} style={{ marginRight: 4, verticalAlign: 'middle' }} /> Personal Password</label>
                        <div style={{ position: 'relative' }}>
                            <input className="form-input" type={showPersonalPwd ? 'text' : 'password'}
                                placeholder="Enter your personal password"
                                value={personalPwd} onChange={(e) => setPersonalPwd(e.target.value)} required />
                            <button type="button" onClick={() => setShowPersonalPwd(!showPersonalPwd)}
                                style={{
                                    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                                    color: 'var(--text-tertiary)', background: 'none', border: 'none', cursor: 'pointer'
                                }}>
                                {showPersonalPwd ? <EyeOff size={18} /> : <Eye size={18} />}
                            </button>
                        </div>
                    </div>

                    <button className="btn btn-primary w-full" type="submit" disabled={loading}
                        style={{ marginTop: 8, height: 46 }}>
                        {loading ? (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <span className="spinner" style={{
                                    width: 18, height: 18, border: '2px solid rgba(255,255,255,0.3)',
                                    borderTopColor: '#fff', borderRadius: '50%', animation: 'spin 0.6s linear infinite'
                                }} /> Signing in…
                            </span>
                        ) : (
                            <span style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                                <LogIn size={18} /> Sign In
                            </span>
                        )}
                    </button>
                </form>

                {/* Credentials Hint */}
                <div className="login-hint">
                    <div className="login-hint-title">Demo Credentials</div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: 8 }}>
                        <strong>Company Password:</strong> <code style={{ background: '#f3f4f6', padding: '2px 6px', borderRadius: 4 }}>{COMPANY_PASSWORD}</code>
                    </div>
                    <div className="login-hint-users">
                        {MOCK_USERS.map(u => (
                            <div
                                key={u.id}
                                className="login-hint-user"
                                style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                                onClick={() => {
                                    setUserId(u.id);
                                    setCompanyPwd(COMPANY_PASSWORD);
                                    setPersonalPwd(u.password);
                                }}
                                title={`Click to autofill ${u.role} credentials`}
                            >
                                <strong>{u.role}:</strong> {u.id} / {u.password}
                            </div>
                        ))}
                    </div>
                </div>
            </div>
            <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
    );
}
