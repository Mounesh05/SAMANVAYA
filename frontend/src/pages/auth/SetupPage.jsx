import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../../api/auth.api';

export function SetupPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    setup_secret: '',
    email: 'demo.ceo@example.com',
    organisation_password: '',
    employee_password: '',
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const update = (event) => {
    setForm({ ...form, [event.target.name]: event.target.value });
  };

  const submit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    try {
      await authApi.initializeDemoAdmin(form);
      setMessage('Initial administrator created. Redirecting to login...');
      setTimeout(() => navigate('/login'), 1000);
    } catch (err) {
      setError(err.message || 'Setup failed');
    }
  };

  return (
    <main style={{ maxWidth: '440px', margin: '4rem auto', padding: '1.5rem' }}>
      <h1>Local Demo Setup</h1>
      <p>Create the first local administrator for the isolated demo database.</p>
      <form onSubmit={submit} style={{ display: 'grid', gap: '1rem' }}>
        <input name="setup_secret" type="password" placeholder="Setup secret" value={form.setup_secret} onChange={update} required />
        <input name="email" type="email" value={form.email} onChange={update} required />
        <input name="organisation_password" type="password" placeholder="Organisation password" value={form.organisation_password} onChange={update} required />
        <input name="employee_password" type="password" placeholder="Employee password" value={form.employee_password} onChange={update} required />
        <button type="submit">Create DEMO-CEO</button>
      </form>
      {message && <p>{message}</p>}
      {error && <p role="alert">{error}</p>}
    </main>
  );
}
