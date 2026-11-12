import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../store/useAuthStore';
import { ROLES } from '../../utils/constants';
import { permissionsFor } from '../../tests/utils/roleUser';

describe('Sidebar HR Navigation', () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
  });

  it('renders Performance Outcomes and Workplace Assessment links when logged in as HR', () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-HR',
      name: 'HR Manager',
      role: ROLES.HR,
      permissions: permissionsFor(ROLES.HR, false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const performanceLink = screen.getByRole('link', { name: /Performance Outcomes/i });
    expect(performanceLink).toBeInTheDocument();
    expect(performanceLink).toHaveAttribute('href', '/performance');

    const feedbackLink = screen.getByRole('link', { name: /Workplace Assessment/i });
    expect(feedbackLink).toBeInTheDocument();
    expect(feedbackLink).toHaveAttribute('href', '/feedback');
  });

  it('renders standard labels for non-HR engineering roles', () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-DEV',
      name: 'Developer',
      role: ROLES.DEVELOPER,
      permissions: permissionsFor(ROLES.DEVELOPER, false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const performanceLink = screen.getByRole('link', { name: /^Performance$/i });
    expect(performanceLink).toBeInTheDocument();
    expect(performanceLink).toHaveAttribute('href', '/performance');

    // Developers do not have feedback link in sidebar
    expect(screen.queryByRole('link', { name: /Feedback/i })).not.toBeInTheDocument();
  });

  it('renders Role Feedback link for LEAD role', () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-LEAD',
      name: 'Lead Developer',
      role: ROLES.LEAD,
      permissions: permissionsFor(ROLES.LEAD, false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const feedbackLink = screen.getByRole('link', { name: /Role Feedback/i });
    expect(feedbackLink).toBeInTheDocument();
    expect(feedbackLink).toHaveAttribute('href', '/feedback');
  });
});
