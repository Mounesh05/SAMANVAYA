/**
 * The real route table (routes/index.jsx) serves "/dashboard" for every role.
 * The app shell and dashboard pages are stand-ins; routing and guards are real.
 */
import { render, screen } from '@testing-library/react';
import { MemoryRouter, Outlet } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { AppRoutes } from '../routes';
import { useAuthStore } from '../store/useAuthStore';
import { ROLES } from '../utils/constants';

vi.mock('../components/layout/AppShell', () => ({ AppShell: () => <Outlet /> }));
const page = (name) => () => <p>{name}</p>;
vi.mock('../pages/developer/DeveloperDashboardPage', () => ({ DeveloperDashboardPage: page('DEVELOPER dashboard') }));
vi.mock('../pages/lead/LeadDashboardPage', () => ({ LeadDashboardPage: page('LEAD dashboard') }));
vi.mock('../pages/pm/PMDashboardPage', () => ({ PMDashboardPage: page('PM dashboard') }));
vi.mock('../pages/qa/QADashboardPage', () => ({ QADashboardPage: page('QA dashboard') }));
vi.mock('../pages/devops/DevOpsDashboardPage', () => ({ DevOpsDashboardPage: page('DEVOPS dashboard') }));
vi.mock('../pages/hr/HRDashboardPage', () => ({ HRDashboardPage: page('HR dashboard') }));
vi.mock('../pages/ceo/CEODashboardPage', () => ({ CEODashboardPage: page('CEO dashboard') }));

beforeEach(() => useAuthStore.setState({ user: null, token: null, isAuthenticated: false }));

describe('AppRoutes: /dashboard', () => {
  it.each(Object.values(ROLES))('%s gets their own dashboard, not 404', async (role) => {
    useAuthStore.setState({ user: { employee_id: `E-${role}`, role, permissions: [] }, token: null, isAuthenticated: true });
    render(<MemoryRouter initialEntries={['/dashboard']}><AppRoutes /></MemoryRouter>);
    expect(await screen.findByText(`${role} dashboard`, {}, { timeout: 5000 })).toBeInTheDocument();
  });
});
