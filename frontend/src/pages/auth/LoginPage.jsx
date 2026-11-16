import React, { useState } from 'react';
import { Navigate, useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useAuthStore } from '../../store/useAuthStore';
import { authApi } from '../../api/auth.api';
import { useThemeStore } from '../../store/useThemeStore';
import { Input } from '../../components/common/Input';
import { Button } from '../../components/common/Button';
import {
  Shield, AlertCircle, KeyRound, UserCheck, Info, Lock, Moon, Sun, LineChart, Bug, Award, Sparkles,
} from 'lucide-react';
import './LoginPage.css';

/**
 * CR-016: one sign-in rule for every employee (larger-company model).
 *
 * - Employee ID or work email, plus the organisation password and the
 *   employee password. Both passwords are always checked by the backend.
 * - One message for every failure, so the page never tells anyone whether
 *   an account exists or is inactive (the backend does the same).
 * - No self-registration and no role list: accounts are created by HR and
 *   admins, and each person lands on their own home page after sign-in.
 */
export const SIGN_IN_FAILED =
  'Sign-in failed. Check your ID and both passwords, or contact your administrator.';

const PUBLIC_PATHS = ['/login', '/setup'];

function safeReturnPath(location) {
  const path = location.state?.from?.pathname;
  if (!path || !path.startsWith('/') || path.startsWith('//') || PUBLIC_PATHS.includes(path)) return '/';
  return path + (location.state?.from?.search || '');
}

export function LoginPage() {
  const [identifier, setIdentifier] = useState('');
  const [orgPassword, setOrgPassword] = useState('');
  const [empPassword, setEmpPassword] = useState('');
  const [capsLock, setCapsLock] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const { setAuth, isAuthenticated, user } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const sessionExpired = searchParams.get('expired') === 'true';
  const { theme, toggleTheme } = useThemeStore();

  // Already signed in: go to the home page instead of showing the form.
  if (isAuthenticated && user) {
    return <Navigate to={safeReturnPath(location)} replace />;
  }

  const trackCapsLock = (event) => {
    if (typeof event.getModifierState === 'function') setCapsLock(event.getModifierState('CapsLock'));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (isLoading) return;
    setError('');

    const id = identifier.trim();
    if (!id || !orgPassword || !empPassword) {
      setError('Enter your employee ID or work email and both passwords.');
      return;
    }

    setIsLoading(true);
    try {
      const response = await authApi.login({
        identifier: id,
        organisation_password: orgPassword,
        employee_password: empPassword,
      });
      if (!response?.token || !response?.user) {
        setError(SIGN_IN_FAILED);
        return;
      }
      setAuth(response.token, response.user);
      // The router sends each person to their own home page from "/".
      navigate(safeReturnPath(location), { replace: true });
    } catch (err) {
      const status = err?.status ?? err?.response?.status;
      if (status === 429) {
        setError('Too many sign-in attempts. Wait a minute, then try again.');
      } else if (status === undefined) {
        setError('The server could not be reached. Check your connection and try again.');
      } else {
        setError(SIGN_IN_FAILED);
      }
      // Never keep passwords in the form after a failed attempt.
      setOrgPassword('');
      setEmpPassword('');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="signin">
      <header className="signin-shell signin-header">
        <div className="signin-logo">
          <span className="signin-mark" aria-hidden="true">S</span>
          SAMANVAYA
        </div>
        <button
          type="button"
          className="signin-theme"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        >
          {theme === 'dark' ? <Sun size={15} aria-hidden="true" /> : <Moon size={15} aria-hidden="true" />}
          {theme === 'dark' ? 'Light' : 'Dark'}
        </button>
      </header>

      <div className="signin-shell signin-body">
        <aside className="signin-intro" aria-label="About Samanvaya">
          <span className="eyebrow">
            <Sparkles size={14} aria-hidden="true" />
            AI-assisted engineering platform
          </span>
          <h2>Plan, deliver and review engineering work in one place.</h2>
          <p className="lead">
            AI reads pull requests, sprint data and code quality to flag risk and gather evidence. People review
            it and make every final decision.
          </p>
          <ul className="signin-points">
            <li>
              <span className="icon" aria-hidden="true"><LineChart size={19} /></span>
              <div>
                <strong>AI delivery risk</strong>
                <span>Sprint and project risk scored from live delivery data, with reports for leadership.</span>
              </div>
            </li>
            <li>
              <span className="icon" aria-hidden="true"><Bug size={19} /></span>
              <div>
                <strong>Code quality and incidents</strong>
                <span>AI-assisted code checks, CI results, defects and incident triage in one place.</span>
              </div>
            </li>
            <li>
              <span className="icon" aria-hidden="true"><Award size={19} /></span>
              <div>
                <strong>Fair, AI-assisted reviews</strong>
                <span>AI gathers evidence from real work; people review it, and every decision is recorded.</span>
              </div>
            </li>
          </ul>
        </aside>

        <main className="signin-card">
          <h1>Sign in</h1>
          <p className="subtitle">Use the account your organisation gave you.</p>

          {sessionExpired && !error && (
            <div role="status" className="signin-notice info">
              <Info size={16} aria-hidden="true" />
              <span>Your session has ended. Sign in again to continue.</span>
            </div>
          )}

          {error && (
            <div role="alert" className="signin-notice error">
              <AlertCircle size={16} aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} noValidate aria-busy={isLoading} className="signin-fields">
            <Input
              label="Employee ID or work email"
              name="username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              placeholder="e.g. EMP-1042 or employee@example.com"
              value={identifier}
              onChange={(e) => setIdentifier(e.target.value)}
              leftIcon={<UserCheck size={16} />}
              maxLength={254}
              autoFocus
              required
            />
            <Input
              label="Organisation password"
              type="password"
              name="organisation-password"
              autoComplete="current-password"
              placeholder="Shared by your organisation"
              value={orgPassword}
              onChange={(e) => setOrgPassword(e.target.value)}
              onKeyUp={trackCapsLock}
              onKeyDown={trackCapsLock}
              leftIcon={<Shield size={16} />}
              maxLength={256}
              required
            />
            <Input
              label="Employee password"
              type="password"
              name="password"
              autoComplete="current-password"
              placeholder="Your own password"
              value={empPassword}
              onChange={(e) => setEmpPassword(e.target.value)}
              onKeyUp={trackCapsLock}
              onKeyDown={trackCapsLock}
              leftIcon={<KeyRound size={16} />}
              maxLength={256}
              required
            />

            {capsLock && (
              <p role="status" className="signin-caps">
                <AlertCircle size={13} aria-hidden="true" /> Caps Lock is on.
              </p>
            )}

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isLoading}
              disabled={isLoading}
              style={{ marginTop: '0.35rem', width: '100%' }}
            >
              Sign in
            </Button>
          </form>

          <div className="signin-help">
            <div>
              <strong>Forgot a password or locked out?</strong> Contact your IT administrator.
            </div>
            <div>
              <strong>New here?</strong> Accounts are created by HR; there is no self sign-up.
            </div>
          </div>

          <p className="signin-assurance">
            <Lock size={12} aria-hidden="true" />
            Two-password sign-in. Every sign-in is recorded.
          </p>
        </main>
      </div>

      <footer className="signin-shell signin-footer">
        <span>&copy; {new Date().getFullYear()} SAMANVAYA. All rights reserved.</span>
        <span>Authorised use only.</span>
      </footer>
    </div>
  );
}
