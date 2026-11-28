/**
 * Post-login routing: "/dashboard" sends each role to its own dashboard,
 * valid return paths are kept, unsafe ones are dropped, and RoleGuard still
 * decides access to whatever page a person returns to.
 */
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { LoginPage } from '../pages/auth/LoginPage';
import { RoleGuard } from '../auth/RoleGuard';
import { HomeRedirect, homePath, safeReturnPath } from '../routes/home';
import { authApi } from '../api/auth.api';
import { useAuthStore } from '../store/useAuthStore';
import { ROLES } from '../utils/constants';

vi.mock('../api/auth.api', () => ({ authApi: { login: vi.fn() } }));

const ALL_ROLES = Object.values(ROLES);
const user = (role) => ({ employee_id: `E-${role}`, name: role, role, permissions: [] });

// The real dashboard routes and guards, with stand-in pages.
function AppUnderTest({ entry }) {
  return (
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<HomeRedirect />} />
        <Route path="/dashboard" element={<HomeRedirect />} />
        {ALL_ROLES.map((role) => (
          <Route
            key={role}
            path={`/${role.toLowerCase()}/dashboard`}
            element={<RoleGuard page={`${role.toLowerCase()}Dashboard`}><p>{role} dashboard</p></RoleGuard>}
          />
        ))}
        <Route path="/projects" element={<RoleGuard page="projects"><p>Projects page</p></RoleGuard>} />
        <Route path="*" element={<p>Not found</p>} />
      </Routes>
    </MemoryRouter>
  );
}

function signedIn(role) {
  useAuthStore.setState({ user: user(role), token: null, isAuthenticated: true });
}

async function signIn() {
  const u = userEvent.setup();
  await u.type(screen.getByLabelText(/Employee ID or work email/), 'E-1');
  await u.type(screen.getByLabelText(/Organisation password/), 'Org-Pass-1!');
  await u.type(screen.getByLabelText(/Employee password/), 'Emp-Pass-2!');
  await u.click(screen.getByRole('button', { name: 'Sign in' }));
}

const loginFrom = (pathname, search = '') => ({ pathname: '/login', state: { from: { pathname, search } } });

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, token: null, isAuthenticated: false });
});

describe('"/dashboard" is role-aware', () => {
  it.each(ALL_ROLES)('%s opening /dashboard lands on their own dashboard', async (role) => {
    signedIn(role);
    render(<AppUnderTest entry="/dashboard" />);
    expect(await screen.findByText(`${role} dashboard`)).toBeInTheDocument();
    expect(screen.queryByText('Not found')).not.toBeInTheDocument();
  });

  it.each(ALL_ROLES)('%s signing in after opening /dashboard lands on their own dashboard', async (role) => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: user(role) });
    render(<AppUnderTest entry={loginFrom('/dashboard')} />);
    await signIn();
    expect(await screen.findByText(`${role} dashboard`)).toBeInTheDocument();
  });

  it('signed-out visitors to /dashboard are sent to sign in', async () => {
    render(<AppUnderTest entry="/dashboard" />);
    expect(await screen.findByLabelText(/Employee ID or work email/)).toBeInTheDocument();
  });

  it('an unrecognised role gets "not found", not another role\'s dashboard', async () => {
    useAuthStore.setState({ user: user('INTERN'), token: null, isAuthenticated: true });
    render(<AppUnderTest entry="/dashboard" />);
    expect(await screen.findByText(/page not found|not found/i)).toBeInTheDocument();
    for (const role of ALL_ROLES) expect(screen.queryByText(`${role} dashboard`)).not.toBeInTheDocument();
  });

  it('homePath covers exactly the seven roles', () => {
    for (const role of ALL_ROLES) expect(homePath(user(role))).toBe(`/${role.toLowerCase()}/dashboard`);
    expect(homePath(user('developer'))).toBe('/developer/dashboard');
    expect(homePath(user('ADMIN'))).toBeNull();
    expect(homePath(null)).toBeNull();
  });
});

describe('return paths after sign-in', () => {
  it('keeps a valid protected page with its query string', async () => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: user('PM') });
    render(<AppUnderTest entry={loginFrom('/projects', '?tab=risks')} />);
    await signIn();
    expect(await screen.findByText('Projects page')).toBeInTheDocument();
    expect(safeReturnPath({ pathname: '/projects', search: '?tab=risks' })).toBe('/projects?tab=risks');
  });

  it.each([
    ['protocol-relative', '//evil.example'],
    ['backslash host', '/\\evil.example'],
    ['encoded slashes', '/%2F%2Fevil.example'],
    ['absolute URL', 'https://evil.example/x'],
    ['javascript URL', 'javascript:alert(1)'],
    ['parent segments', '/projects/../../admin'],
    ['control character', '/projects\n/x'],
    ['bad encoding', '/%E0%A4%A'],
    ['sign-in page', '/login'],
    ['setup page', '/setup/'],
    ['missing', undefined],
    ['not a string', 42],
  ])('drops an unsafe destination (%s)', (_name, pathname) => {
    expect(safeReturnPath({ pathname })).toBe('/');
  });

  it('drops a query string that is not a query string', () => {
    expect(safeReturnPath({ pathname: '/projects', search: '//evil.example' })).toBe('/');
  });

  it('an unsafe destination after sign-in still lands on the role dashboard', async () => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: user('LEAD') });
    render(<AppUnderTest entry={loginFrom('//evil.example')} />);
    await signIn();
    expect(await screen.findByText('LEAD dashboard')).toBeInTheDocument();
  });
});

describe('return paths cannot bypass role access', () => {
  it.each([
    ['DEVELOPER', '/ceo/dashboard'],
    ['QA', '/hr/dashboard'],
    ['HR', '/developer/dashboard'],
    ['DEVOPS', '/lead/dashboard'],
  ])('%s returning to %s is sent to their own dashboard', async (role, target) => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: user(role) });
    render(<AppUnderTest entry={loginFrom(target)} />);
    await signIn();
    expect(await screen.findByText(`${role} dashboard`)).toBeInTheDocument();
    const owner = target.split('/')[1].toUpperCase();
    expect(screen.queryByText(`${owner} dashboard`)).not.toBeInTheDocument();
  });

  it('a role allowed on a shared page keeps it (LEAD on the QA dashboard)', async () => {
    authApi.login.mockResolvedValue({ token: 'jwt', user: user('LEAD') });
    render(<AppUnderTest entry={loginFrom('/qa/dashboard')} />);
    await signIn();
    await waitFor(() => expect(screen.getByText('QA dashboard')).toBeInTheDocument());
  });
});
