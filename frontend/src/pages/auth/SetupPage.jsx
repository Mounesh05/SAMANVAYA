import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth.api';
import { Button } from '../../components/common/Button';
import './LoginPage.css';

const EMPTY_ACCOUNT = { name: '', employee_id: '', email: '', organisation_password: '', employee_password: '' };

/**
 * CR-012: first-run setup creates two separate accounts. The Chief Executive
 * has no admin rights; the platform administrator (DevOps role) runs the
 * system. Both are created together or not at all.
 * CR-016: each account is a real person, with their own name and employee ID.
 */
function AccountFields({ legend, note, name, account, onChange }) {
  return (
    <fieldset className="setup-account">
      <legend>{legend}</legend>
      {note && <p>{note}</p>}
      <label>
        Full name
        <input name={`${name}.name`} autoComplete="off" value={account.name} onChange={onChange} required minLength={2} maxLength={100} />
      </label>
      <label>
        Employee ID
        <input name={`${name}.employee_id`} autoComplete="off" value={account.employee_id} onChange={onChange}
          required minLength={2} maxLength={30} pattern="[A-Za-z0-9][A-Za-z0-9_\-]*"
          title="Letters, numbers, hyphens or underscores, as in your HR records" />
      </label>
      <label>
        Work email
        <input name={`${name}.email`} type="email" autoComplete="off" value={account.email} onChange={onChange} required />
      </label>
      <label>
        Organisation password
        <input name={`${name}.organisation_password`} type="password" autoComplete="new-password"
          value={account.organisation_password} onChange={onChange} required />
      </label>
      <label>
        Employee password
        <input name={`${name}.employee_password`} type="password" autoComplete="new-password"
          value={account.employee_password} onChange={onChange} required />
      </label>
    </fieldset>
  );
}

export function SetupPage() {
  const navigate = useNavigate();
  const [secret, setSecret] = useState('');
  const [accounts, setAccounts] = useState({ ceo: { ...EMPTY_ACCOUNT }, admin: { ...EMPTY_ACCOUNT } });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const update = (event) => {
    const [who, field] = event.target.name.split('.');
    setAccounts({ ...accounts, [who]: { ...accounts[who], [field]: event.target.value } });
  };

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      await authApi.initializeFirstAccounts({ setup_secret: secret, ceo: accounts.ceo, admin: accounts.admin });
      const ids = `${accounts.ceo.employee_id.trim().toUpperCase()} and ${accounts.admin.employee_id.trim().toUpperCase()}`;
      setMessage(`Accounts ${ids} created. Redirecting to sign-in...`);
      setTimeout(() => navigate('/login'), 1000);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Setup failed');
    }
  };

  return (
    <main className="setup-page">
      <div className="signin-logo">
        <span className="signin-mark" aria-hidden="true">S</span>
        Samanvaya
      </div>
      <h1>First-run setup</h1>
      <p className="setup-intro">
        Create the first two accounts for your organisation, using each person&apos;s real name and employee
        ID. The Chief Executive and the platform administrator are separate, so account changes can be
        approved by a second person. Everyone else is added later by HR and the administrator.
      </p>
      <form onSubmit={submit} className="setup-form">
        <label>
          Setup secret
          <input name="setup_secret" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} required />
        </label>
        <div className="work-grid setup-accounts">
          <AccountFields
            legend="Chief Executive (no admin rights)"
            note="This account can act as the second reviewer on account changes that require approval."
            name="ceo"
            account={accounts.ceo}
            onChange={update}
          />
          <AccountFields
            legend="Platform administrator (admin rights)"
            note="This account has the DevOps role and admin rights to set up teams, accounts and platform settings."
            name="admin"
            account={accounts.admin}
            onChange={update}
          />
        </div>
        <Button type="submit">Create both accounts</Button>
      </form>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
