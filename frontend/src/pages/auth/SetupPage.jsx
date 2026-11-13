import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth.api';

const EMPTY_ACCOUNT = { email: '', organisation_password: '', employee_password: '' };

/**
 * CR-012: first-run setup creates two separate accounts. The Chief Executive
 * has no admin rights; the platform administrator (DevOps role) runs the
 * system. Both are created together or not at all.
 */
function AccountFields({ legend, name, account, onChange }) {
  return (
    <fieldset style={{ display: 'grid', gap: '0.6rem', border: '1px solid var(--border-subtle, #ccc)', padding: '1rem' }}>
      <legend>{legend}</legend>
      <label>
        Email
        <input name={`${name}.email`} type="email" value={account.email} onChange={onChange} required />
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
      await authApi.initializeDemoAdmin({ setup_secret: secret, ceo: accounts.ceo, admin: accounts.admin });
      setMessage('Chief Executive (DEMO-CEO) and platform administrator (DEMO-ADMIN) created. Redirecting to login...');
      setTimeout(() => navigate('/login'), 1000);
    } catch (err) {
      setError(err?.response?.data?.detail || err.message || 'Setup failed');
    }
  };

  return (
    <main style={{ maxWidth: '480px', margin: '4rem auto', padding: '1.5rem' }}>
      <h1>Local Demo Setup</h1>
      <p>
        Create the first two accounts for the isolated demo database. The Chief Executive and the
        platform administrator are separate, so account changes can be approved by a second person.
      </p>
      <form onSubmit={submit} style={{ display: 'grid', gap: '1rem' }}>
        <label>
          Setup secret
          <input name="setup_secret" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} required />
        </label>
        <AccountFields legend="Chief Executive (DEMO-CEO, no admin rights)" name="ceo" account={accounts.ceo} onChange={update} />
        <AccountFields legend="Platform administrator (DEMO-ADMIN, DevOps role)" name="admin" account={accounts.admin} onChange={update} />
        <button type="submit">Create both accounts</button>
      </form>
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
