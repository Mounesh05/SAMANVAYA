/**
 * CR-016: one sign-in form (larger-company model). Backend counterparts live
 * in backend/tests/test_sign_in.py.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginPage, SIGN_IN_FAILED } from '../pages/auth/LoginPage';
import { authApi } from '../api/auth.api';
import { useAuthStore } from '../store/useAuthStore';

vi.mock('../api/auth.api', () => ({ authApi: { login: vi.fn() } }));

const USER = { employee_id: 'EMP-1001', name: 'Asha Rao', role: 'DEVELOPER', permissions: [] };

function renderLogin(entry = '/login') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<p>Home page</p>} />
        <Route path="/projects" element={<p>Projects page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

async function signIn(user, id = 'EMP-1001', org = 'Org-Pass-1!', emp = 'Emp-Pass-2!') {
  if (id) await user.type(screen.getByLabelText(/Employee ID or work email/), id);
  if (org) await user.type(screen.getByLabelText(/Organisation password/), org);
  if (emp) await user.type(screen.getByLabelText(/Employee password/), emp);
  await user.click(screen.getByRole('button', { name: 'Sign in' }));
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
});

describe('CR-016 sign-in page', () => {
  it('shows one form with the ID field and both passwords, and no role list or sign-up', () => {
    renderLogin();
    expect(screen.getByLabelText(/Employee ID or work email/)).toHaveAttribute('autocomplete', 'username');
    expect(screen.getByLabelText(/Organisation password/)).toHaveAttribute('type', 'password');
    expect(screen.getByLabelText(/Employee password/)).toHaveAttribute('type', 'password');
    expect(screen.queryByRole('button', { name: /Email Login/i })).not.toBeInTheDocument();
    const text = document.body.textContent;
    for (const role of ['DEVELOPER', 'LEAD', 'DEVOPS', 'CEO', 'DEMO']) expect(text).not.toContain(role);
    expect(text).toMatch(/no\s+self sign-up/);
  });

  it('sends the ID and both passwords, then goes to the home page', async () => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: USER });
    renderLogin();
    await signIn(userEvent.setup(), '  asha.rao@company.com ');
    await waitFor(() => expect(authApi.login).toHaveBeenCalledWith({
      identifier: 'asha.rao@company.com', organisation_password: 'Org-Pass-1!', employee_password: 'Emp-Pass-2!',
    }));
    expect(await screen.findByText('Home page')).toBeInTheDocument();
    expect(useAuthStore.getState().user.employee_id).toBe('EMP-1001');
  });

  it('returns to the page the person asked for', async () => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: USER });
    render(
      <MemoryRouter initialEntries={[{ pathname: '/login', state: { from: { pathname: '/projects' } } }]}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/projects" element={<p>Projects page</p>} />
        </Routes>
      </MemoryRouter>,
    );
    await signIn(userEvent.setup());
    expect(await screen.findByText('Projects page')).toBeInTheDocument();
  });

  it('asks for every field before calling the server', async () => {
    renderLogin();
    await signIn(userEvent.setup(), 'EMP-1001', 'Org-Pass-1!', '');
    expect(authApi.login).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent('both passwords');
  });

  it('gives one message for any failure and clears both passwords', async () => {
    authApi.login.mockRejectedValue(Object.assign(new Error('Invalid credentials or user not active'), { status: 401 }));
    renderLogin();
    await signIn(userEvent.setup());
    expect(await screen.findByRole('alert')).toHaveTextContent(SIGN_IN_FAILED);
    expect(screen.getByLabelText(/Organisation password/)).toHaveValue('');
    expect(screen.getByLabelText(/Employee password/)).toHaveValue('');
    expect(screen.getByLabelText(/Employee ID or work email/)).toHaveValue('EMP-1001');
  });

  it('explains rate limiting and unreachable servers', async () => {
    authApi.login.mockRejectedValueOnce(Object.assign(new Error('Rate limit exceeded'), { status: 429 }));
    renderLogin();
    const user = userEvent.setup();
    await signIn(user);
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many sign-in attempts');

    authApi.login.mockRejectedValueOnce(new Error('Network Error'));
    await signIn(user, '');
    expect(await screen.findByRole('alert')).toHaveTextContent('could not be reached');
  });

  it('tells people when their session ended', () => {
    renderLogin('/login?expired=true');
    expect(screen.getByRole('status')).toHaveTextContent('Your session has ended');
  });

  it('has the brand panel, help, and a working theme switch', async () => {
    renderLogin();
    expect(screen.getByRole('complementary', { name: 'About Samanvaya' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    expect(screen.getByText(/Forgot a password or locked out\?/)).toBeInTheDocument();
    expect(screen.getByRole('contentinfo')).toHaveTextContent('Authorised use only');

    const before = document.documentElement.getAttribute('data-theme');
    await userEvent.setup().click(screen.getByRole('button', { name: /Switch to (light|dark) theme/ }));
    expect(document.documentElement.getAttribute('data-theme')).not.toBe(before);
  });

  it('sends people who are already signed in to the home page', () => {
    useAuthStore.setState({ user: USER, token: 'jwt', isAuthenticated: true });
    renderLogin();
    expect(screen.getByText('Home page')).toBeInTheDocument();
  });
});

describe('API error messages', () => {
  it('turns validation lists into readable text', async () => {
    const { readableDetail } = await vi.importActual('../api/client');
    expect(readableDetail([
      { loc: ['body', 'ceo', 'email'], msg: 'value is not a valid email address' },
      { loc: ['body', 'admin', 'employee_id'], msg: 'Value error, too short' },
    ])).toBe('ceo email: value is not a valid email address; admin employee_id: too short');
    expect(readableDetail('Plain message')).toBe('Plain message');
    expect(readableDetail(undefined)).toBeUndefined();
  });
});
