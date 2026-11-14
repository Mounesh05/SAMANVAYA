import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it } from 'vitest';
import React from 'react';
import { Sidebar } from './Sidebar';
import { useAuthStore } from '../../store/useAuthStore';
import { useThemeStore } from '../../store/useThemeStore';
import { ROLES } from '../../utils/constants';
import { permissionsFor } from '../../tests/utils/roleUser';

describe('Sidebar Navigation Stress & Role Matrix Suite', () => {
  beforeEach(() => {
    useAuthStore.getState().logout();
    useThemeStore.setState({ sidebarCollapsed: false });
  });

  const getRenderedNavLinks = () => {
    const nav = screen.getByRole('navigation');
    const links = nav.querySelectorAll('a');
    return Array.from(links).map((link) => ({
      href: link.getAttribute('href'),
      text: link.textContent.trim(),
      title: link.getAttribute('title') || '',
    }));
  };

  it('rigorously tests HR navigation tabs, links, dynamic labels, and forbidden tabs', () => {
    useAuthStore.getState().setAuth('mock-token-hr', {
      employee_id: 'DEMO-HR',
      name: 'HR Director',
      role: ROLES.HR,
      permissions: permissionsFor(ROLES.HR, false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const rendered = getRenderedNavLinks();
    const renderedHrefs = rendered.map((r) => r.href);

    // HR MUST have these exact routes:
    const expectedHRRoutes = [
      '/hr/dashboard',
      '/employees',
      '/transfers',
      '/performance',
      '/feedback',
      '/audit',
      '/approvals', // CR-010: HR requests and approves role changes
      '/reports', // CR-011: HR downloads the aggregated performance report
    ];
    expect(renderedHrefs.sort()).toEqual(expectedHRRoutes.sort());

    // Verify HR dynamic label contract (R2)
    const performanceItem = rendered.find((r) => r.href === '/performance');
    expect(performanceItem).toBeDefined();
    expect(performanceItem.text).toBe('Performance Outcomes');

    const feedbackItem = rendered.find((r) => r.href === '/feedback');
    expect(feedbackItem).toBeDefined();
    expect(feedbackItem.text).toBe('Workplace Assessment');

    // Verify HR is NEVER exposed to engineering or dev work tabs
    const forbiddenForHR = [
      '/projects',
      '/sprints',
      '/stories',
      '/tasks',
      '/board',
      '/teams',
      '/code-quality',
      '/pull-requests',
      '/github/sync',
      '/tests',
      '/bugs',
      '/pipelines',
      '/deployments',
      '/incidents',
      '/cicd-logs',
      '/evaluation',
      '/quality',
      '/risk',
      '/organization',
    ];

    for (const forbidden of forbiddenForHR) {
      expect(renderedHrefs).not.toContain(forbidden);
    }
  });

  it('tests full role matrix for all 6 non-HR roles asserting exact routes and standard labels', () => {
    const roleSpecifications = [
      {
        role: ROLES.CEO,
        expectedRoutes: [
          '/ceo/dashboard',
          '/projects',
          '/employees',
          '/teams',
          '/bugs',
          '/incidents',
          // CR-015: '/evaluation' moved to Leads
          '/performance',
          '/feedback',
          '/reports',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        forbiddenRoutes: [
          '/transfers',
          '/sprints',
          '/stories',
          '/tasks',
          '/board',
          '/code-quality',
          '/pull-requests',
          '/github/sync',
          '/tests',
          '/pipelines',
          '/deployments',
          '/cicd-logs',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: 'Role Feedback',
      },
      {
        role: ROLES.PM,
        expectedRoutes: [
          '/pm/dashboard',
          '/projects',
          '/sprints',
          '/stories',
          '/tasks',
          '/board',
          '/bugs',
          '/performance',
          '/feedback',
          '/reports',
          '/incidents', // CR-014: PMs triage their projects' incidents
        ],
        forbiddenRoutes: [
          '/employees',
          '/transfers',
          '/teams',
          '/code-quality',
          '/pull-requests',
          '/github/sync',
          '/tests',
          '/pipelines',
          '/deployments',
          '/cicd-logs',
          '/evaluation',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: 'Role Feedback',
      },
      {
        role: ROLES.LEAD,
        expectedRoutes: [
          '/lead/dashboard',
          '/projects',
          '/sprints',
          '/stories',
          '/tasks',
          '/board',
          '/teams',
          '/code-quality',
          '/pull-requests',
          '/github/sync',
          '/bugs',
          '/pipelines',
          '/deployments',
          '/incidents',
          '/cicd-logs',
          '/evaluation',
          '/performance',
          '/feedback',
          // CR-004: Leads approve transfers at their manager stage.
          '/transfers',
        ],
        forbiddenRoutes: [
          '/employees',
          '/tests',
          '/reports',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: 'Role Feedback',
      },
      {
        role: ROLES.DEVELOPER,
        expectedRoutes: [
          '/developer/dashboard',
          '/projects',
          '/sprints',
          '/stories',
          '/tasks',
          '/board',
          '/code-quality',
          '/pull-requests',
          '/bugs',
          '/cicd-logs',
          '/performance',
          // CR-001: Developers request and follow their own transfers.
          '/transfers',
          // CR-001: Developers report incidents and see their own reports.
          '/incidents',
        ],
        // Developers do NOT have feedback link.
        // CR-001: GitHub Sync (integration setup) and AI Evaluation (their own
        // evaluation lives on Performance) left the Developer menu. Without a
        // team_id there is no "My Team" link, and the team list stays hidden.
        forbiddenRoutes: [
          '/feedback',
          '/employees',
          '/github/sync',
          '/evaluation',
          '/teams',
          '/tests',
          '/pipelines',
          '/deployments',
          '/reports',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: null,
      },
      {
        role: ROLES.QA,
        expectedRoutes: [
          '/qa/dashboard',
          '/projects',
          '/sprints',
          '/stories',
          '/tasks',
          '/code-quality',
          '/pull-requests',
          '/tests',
          '/bugs',
          '/pipelines',
          '/cicd-logs',
          '/performance',
          '/feedback',
          // CR-002: QA works the Review column and can report incidents.
          '/board',
          '/incidents',
        ],
        forbiddenRoutes: [
          '/github/sync',
          '/deployments',
          '/evaluation',
          '/employees',
          '/transfers',
          '/teams',
          '/reports',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: 'Role Feedback',
      },
      {
        role: ROLES.DEVOPS,
        expectedRoutes: [
          '/devops/dashboard',
          '/projects',
          '/sprints',
          '/stories',
          '/tasks',
          '/code-quality',
          '/pull-requests',
          '/github/sync',
          '/bugs',
          '/pipelines',
          '/deployments',
          '/incidents',
          '/cicd-logs',
          '/performance',
          '/feedback',
        ],
        forbiddenRoutes: [
          '/board',
          '/tests',
          '/evaluation',
          '/employees',
          '/transfers',
          '/teams',
          '/reports',
          '/audit',
          '/quality',
          '/risk',
          '/organization',
        ],
        performanceLabel: 'Performance',
        feedbackLabel: 'Role Feedback',
      },
    ];

    for (const spec of roleSpecifications) {
      useAuthStore.getState().logout();
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: `DEMO-${spec.role}`,
        name: `User ${spec.role}`,
        role: spec.role,
        permissions: permissionsFor(spec.role, false),
        is_admin: false,
      });

      const { unmount } = render(
        <MemoryRouter>
          <Sidebar />
        </MemoryRouter>
      );

      const rendered = getRenderedNavLinks();
      const renderedHrefs = rendered.map((r) => r.href);

      // Verify exact expected routes match
      expect(renderedHrefs.sort(), `Failed route set for role ${spec.role}`).toEqual(spec.expectedRoutes.sort());

      // Verify forbidden routes are absent
      for (const forbidden of spec.forbiddenRoutes) {
        expect(renderedHrefs, `Role ${spec.role} unexpectedly contains ${forbidden}`).not.toContain(forbidden);
      }

      // Verify performance label is standard "Performance" (never "Performance Outcomes")
      const perf = rendered.find((r) => r.href === '/performance');
      expect(perf).toBeDefined();
      expect(perf.text).toBe(spec.performanceLabel);
      expect(perf.text).not.toBe('Performance Outcomes');

      // Verify feedback link and label
      const fb = rendered.find((r) => r.href === '/feedback');
      if (spec.feedbackLabel) {
        expect(fb).toBeDefined();
        expect(fb.text).toBe(spec.feedbackLabel);
        expect(fb.text).not.toBe('Workplace Assessment');
      } else {
        expect(fb).toBeUndefined();
      }

      unmount();
    }
  });

  it('handles unauthenticated or empty user state safely without crashing or exposing links', () => {
    useAuthStore.getState().logout();

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const nav = screen.getByRole('navigation');
    const links = nav.querySelectorAll('a');
    expect(links.length).toBe(0);

    // Profile fallback footer should show 'User'
    expect(screen.getByText('User')).toBeInTheDocument();
  });

  it('handles lowercase role strings robustly', () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-HR-LOWER',
      name: 'Lowercase HR',
      role: 'hr',
      permissions: permissionsFor('hr', false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const rendered = getRenderedNavLinks();
    const performanceItem = rendered.find((r) => r.href === '/performance');
    expect(performanceItem).toBeDefined();
    expect(performanceItem.text).toBe('Performance Outcomes');
  });

  it('handles unknown roles gracefully without exposing role-restricted tabs', () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-UNKNOWN',
      name: 'Unknown Role User',
      role: 'CONTRACTOR',
      permissions: permissionsFor('CONTRACTOR', false),
      is_admin: false,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const rendered = getRenderedNavLinks();
    expect(rendered.length).toBe(0);
  });

  it('properly renders titles and accessibility in collapsed mode for HR and engineering roles', () => {
    useThemeStore.setState({ sidebarCollapsed: true });

    useAuthStore.getState().setAuth('mock-token-hr', {
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

    const rendered = getRenderedNavLinks();
    const performanceItem = rendered.find((r) => r.href === '/performance');
    expect(performanceItem).toBeDefined();
    expect(performanceItem.title).toBe('Performance Outcomes');

    const feedbackItem = rendered.find((r) => r.href === '/feedback');
    expect(feedbackItem).toBeDefined();
    expect(feedbackItem.title).toBe('Workplace Assessment');
  });

  it('verifies admin user bypasses standard role filters while preserving HR labels if role is HR', () => {
    useAuthStore.getState().setAuth('mock-token-admin', {
      employee_id: 'DEMO-ADMIN-HR',
      name: 'Admin HR',
      role: ROLES.HR,
      permissions: permissionsFor(ROLES.HR, true),
      is_admin: true,
    });

    render(
      <MemoryRouter>
        <Sidebar />
      </MemoryRouter>
    );

    const rendered = getRenderedNavLinks();
    const performanceItem = rendered.find((r) => r.href === '/performance');
    expect(performanceItem.text).toBe('Performance Outcomes');

    const feedbackItem = rendered.find((r) => r.href === '/feedback');
    expect(feedbackItem.text).toBe('Workplace Assessment');
  });
});
