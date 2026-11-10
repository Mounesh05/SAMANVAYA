import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { PerformancePage } from './PerformancePage';
import { performanceApi } from '../../api/performance.api';
import { employeesApi } from '../../api/employees.api';
import { useAuthStore } from '../../store/useAuthStore';
import { ToastProvider } from '../../components/common/Toast';
import { ROLES } from '../../utils/constants';

vi.mock('../../api/performance.api', () => ({
  performanceApi: {
    getDeveloperDashboard: vi.fn(),
    evaluateDeveloper: vi.fn(),
  },
}));

vi.mock('../../api/employees.api', () => ({
  employeesApi: {
    list: vi.fn(),
  },
}));

const mockEmployees = [
  { employee_id: 'DEMO-HR', name: 'HR Manager', role: 'HR', designation: 'HR Lead' },
  { employee_id: 'DEMO-CEO', name: 'Executive CEO', role: 'CEO', designation: 'Chief Executive' },
  { employee_id: 'DEMO-PM', name: 'Product Manager', role: 'PM', designation: 'Senior PM' },
  { employee_id: 'DEMO-DEV1', name: 'Alice Developer', role: 'DEVELOPER', designation: 'Fullstack Dev' },
  { employee_id: 'DEMO-LEAD1', name: 'Bob Lead', role: 'LEAD', designation: 'Tech Lead' },
  { employee_id: 'DEMO-QA1', name: 'Charlie QA', role: 'QA', designation: 'Quality Analyst' },
  { employee_id: 'DEMO-OPS1', name: 'Dave DevOps', role: 'DEVOPS', designation: 'Site Reliability' },
];

const mockDashboardData = {
  developer_id: 'DEMO-DEV1',
  developer_name: 'Alice Developer',
  overall_score: 88,
  final_score: 88,
  grade: 'A',
  trend: 'improving',
  is_hr_view: true,
  summary: 'Consistent delivery and high code quality.',
  strengths: ['Architecture', 'Testing'],
  areas_for_growth: ['Mentorship'],
  recommendations: ['Consider presenting tech talks.'],
};

function renderPage(initialEntries = ['/performance']) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <ToastProvider>
          <PerformancePage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('PerformancePage Evaluation Eligibility & Auto-Defaulting', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout();
    employeesApi.list.mockResolvedValue(mockEmployees);
    performanceApi.getDeveloperDashboard.mockResolvedValue(mockDashboardData);
  });

  it('as HR user, does not query DEMO-HR or DEMO-CEO and defaults to first eligible engineering contributor', async () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-HR',
      name: 'HR Manager',
      role: ROLES.HR,
      is_admin: false,
    });

    renderPage(['/performance']);

    // Wait for the performance dashboard data to load
    await waitFor(() => {
      expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('DEMO-DEV1');
    });

    // Ensure it NEVER called DEMO-HR or DEMO-CEO
    const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
    expect(calledIds).not.toContain('DEMO-HR');
    expect(calledIds).not.toContain('DEMO-CEO');
    expect(calledIds).not.toContain('');
  });

  it('restricts dropdown strictly to engineering contributors, excluding HR, CEO, and PM', async () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-HR',
      name: 'HR Manager',
      role: ROLES.HR,
      is_admin: false,
    });

    renderPage(['/performance']);

    // Wait for the select dropdown to appear
    const select = await screen.findByRole('combobox');
    expect(select).toBeInTheDocument();

    const options = Array.from(select.querySelectorAll('option'))
      .map((o) => o.value)
      .filter(Boolean);

    // Eligible engineering roles should be included
    expect(options).toEqual(['DEMO-DEV1', 'DEMO-LEAD1', 'DEMO-QA1', 'DEMO-OPS1']);

    // Non-engineering roles and excluded IDs must NOT be in the options
    expect(options).not.toContain('DEMO-HR');
    expect(options).not.toContain('DEMO-CEO');
    expect(options).not.toContain('DEMO-PM');
    expect(options).toHaveLength(4);
  });

  it('allows switching to another engineering contributor in the dropdown', async () => {
    useAuthStore.getState().setAuth('mock-token', {
      employee_id: 'DEMO-HR',
      name: 'HR Manager',
      role: ROLES.HR,
      is_admin: false,
    });

    renderPage(['/performance']);

    const select = await screen.findByRole('combobox');
    fireEvent.change(select, { target: { value: 'DEMO-QA1' } });

    await waitFor(() => {
      expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('DEMO-QA1');
    });
  });
});
