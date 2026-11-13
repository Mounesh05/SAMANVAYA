/**
 * CR-007: CEO access, as the UI presents it.
 * Backend counterparts live in backend/tests/test_ceo_access.py.
 */
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { hasPermission, PERMISSIONS } from '../auth/permissions';
import { canOpenPage } from '../routes/access';
import { useAuthStore } from '../store/useAuthStore';
import { ReportsPage } from '../pages/reports/ReportsPage';
import { roleUser } from './utils/roleUser';

const CEO = roleUser('CEO', { employee_id: 'CEO-1' });

function renderReports(user) {
  useAuthStore.setState({ user, token: 't', isAuthenticated: true });
  return render(
    <MemoryRouter initialEntries={['/reports']}>
      <Routes>
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/risk" element={<p>Risk page</p>} />
        <Route path="/quality" element={<p>Quality page</p>} />
        <Route path="*" element={<p>Other page</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => vi.clearAllMocks());

describe('CR-007 CEO permissions', () => {
  it.each([
    'MANAGE_REPOSITORY_LINK', 'MANAGE_TEST_AUTOMATION', 'ACCEPT_STORY', 'CLEAR_RISK_CACHE', 'MANAGE_RISK_CONFIG',
  ])('no longer gives the CEO %s', (name) => {
    expect(hasPermission(CEO, PERMISSIONS[name])).toBe(false);
  });

  it('keeps executive and organisation-design rights', () => {
    for (const name of ['VIEW_ALL_DATA', 'VIEW_AUDIT_LOGS', 'MANAGE_GLOBAL_RISK_CONFIG', 'MANAGE_TEAMS', 'ASSIGN_TEAM_LEAD']) {
      expect(hasPermission(CEO, PERMISSIONS[name])).toBe(true);
    }
    expect(canOpenPage(CEO, 'reports')).toBe(true);
    expect(canOpenPage(CEO, 'ceoRisk')).toBe(true);
  });
});

describe('CR-007 Reports page', () => {
  it('offers no fake download and links the CEO to live pages', async () => {
    renderReports(CEO);
    expect(screen.queryByRole('button', { name: /Export CSV/i })).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole('button', { name: /Open Delivery & Risk Governance/i }));
    expect(await screen.findByText('Risk page')).toBeInTheDocument();
  });

  it('sends the CEO to the executive quality page', async () => {
    renderReports(CEO);
    await userEvent.setup().click(screen.getByRole('button', { name: /Open Engineering Quality/i }));
    expect(await screen.findByText('Quality page')).toBeInTheDocument();
  });

  it('shows only reports whose page the user can open', () => {
    renderReports(roleUser('PM'));
    expect(screen.queryByRole('button', { name: /Delivery & Risk Governance/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Open Project Portfolio/i })).toBeInTheDocument();
  });
});
