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

const mockAdversarialEmployees = [
  // Excluded executive & evaluators
  { employee_id: 'DEMO-HR', name: 'HR Manager', role: 'HR', designation: 'HR Lead' },
  { employee_id: 'DEMO-CEO', name: 'Executive CEO', role: 'CEO', designation: 'Chief Executive' },
  { employee_id: 'OTHER-HR', name: 'Other HR Specialist', role: 'HR', designation: 'People Partner' },
  { employee_id: 'OTHER-CEO', name: 'Interim CEO', role: 'CEO', designation: 'Executive' },

  // Non-engineering roles that must NEVER appear
  { employee_id: 'DEMO-PM', name: 'Peter PM', role: 'PM', designation: 'Senior Product Manager' },
  { employee_id: 'PM-2', name: 'Pamela PM', role: 'pm', designation: 'Technical PM' },
  { employee_id: 'EMP-INTERN', name: 'Ian Intern', role: 'INTERN', designation: 'Engineering Intern' },
  { employee_id: 'EMP-DESIGNER', name: 'Dana Designer', role: 'DESIGNER', designation: 'UI/UX Designer' },
  { employee_id: 'EMP-MARKETING', name: 'Mark Marketing', role: 'MARKETING', designation: 'Growth Lead' },
  { employee_id: 'EMP-FINANCE', name: 'Fiona Finance', role: 'FINANCE', designation: 'Controller' },
  { employee_id: 'EMP-ADMIN', name: 'Adam Admin', role: 'ADMIN', designation: 'System Admin' },
  { employee_id: 'EMP-NULL-ROLE', name: 'No Role Emp', role: null, designation: 'Unknown' },
  { employee_id: 'EMP-EMPTY-ROLE', name: 'Empty Role Emp', role: '', designation: 'Unknown' },

  // Spoofed identities: Excluded IDs with engineering roles
  { employee_id: 'DEMO-HR', name: 'Spoofed HR as Dev', role: 'DEVELOPER', designation: 'Spoofed' },
  { employee_id: 'DEMO-CEO', name: 'Spoofed CEO as Lead', role: 'LEAD', designation: 'Spoofed' },

  // Legitimate engineering contributors with varying casing
  { employee_id: 'ENG-DEV-1', name: 'Alice Developer', role: 'DEVELOPER', designation: 'Backend' },
  { employee_id: 'ENG-DEV-LOWER', name: 'Alex Lowcase Dev', role: 'developer', designation: 'Frontend' },
  { employee_id: 'ENG-LEAD-1', name: 'Bob TechLead', role: 'LEAD', designation: 'Staff Eng' },
  { employee_id: 'ENG-LEAD-MIX', name: 'Bella Lead', role: 'Lead', designation: 'Tech Lead' },
  { employee_id: 'ENG-QA-1', name: 'Charlie Quality', role: 'QA', designation: 'SDET' },
  { employee_id: 'ENG-QA-LOWER', name: 'Chloe QA', role: 'qa', designation: 'QA Specialist' },
  { employee_id: 'ENG-OPS-1', name: 'Dave DevOps', role: 'DEVOPS', designation: 'SRE' },
  { employee_id: 'ENG-OPS-MIX', name: 'Dan DevOps', role: 'DevOps', designation: 'Infra Eng' },
];

const mockDashboardResponse = (id) => ({
  developer_id: id,
  developer_name: `Engineer ${id}`,
  overall_score: 87.5,
  final_score: 87.5,
  grade: 'A',
  trend: 'stable',
  is_hr_view: true,
  summary: 'Solid performance',
  strengths: ['Testing', 'Code Review'],
  areas_for_growth: ['Documentation'],
  recommendations: ['Keep mentoring junior staff'],
});

function renderPerformancePage(initialEntries = ['/performance']) {
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

describe('PerformancePage Adversarial Stress Tests: Network Lifecycle & Eligibility', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout();
    employeesApi.list.mockResolvedValue(mockAdversarialEmployees);
    performanceApi.getDeveloperDashboard.mockImplementation((id) =>
      Promise.resolve(mockDashboardResponse(id))
    );
  });

  describe('1. Network Lifecycle & Auto-Defaulting Integrity', () => {
    it('HR user mount: strictly 0 calls to DEMO-HR or DEMO-CEO; immediately defaults to first eligible engineer', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      // Wait until query for first valid engineer resolves
      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      // Assert that DEMO-HR was NEVER called
      const calls = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calls).not.toContain('DEMO-HR');
      expect(calls).not.toContain('DEMO-CEO');
      expect(calls).not.toContain('');
      expect(calls).not.toContain(undefined);

      // Verify the EXACT first call was ENG-DEV-1
      expect(calls[0]).toBe('ENG-DEV-1');
      expect(calls.filter((id) => id === 'DEMO-HR')).toHaveLength(0);
      expect(calls.filter((id) => id === 'DEMO-CEO')).toHaveLength(0);
    });

    it('HR user with adversarial URL param ?developer=DEMO-HR: NEVER queries DEMO-HR (0 calls) and defaults to first eligible engineer', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance?developer=DEMO-HR']);

      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).not.toContain('DEMO-HR');
      expect(calledIds.filter((id) => id === 'DEMO-HR')).toHaveLength(0);
    });

    it('HR user with adversarial URL param ?developer=DEMO-CEO: NEVER queries DEMO-CEO (0 calls) and defaults to first eligible engineer', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance?developer=DEMO-CEO']);

      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).not.toContain('DEMO-CEO');
      expect(calledIds.filter((id) => id === 'DEMO-CEO')).toHaveLength(0);
    });

    it('HR user with adversarial URL param ?developer=DEMO-PM: corrects to first eligible engineer once list resolves', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance?developer=DEMO-PM']);

      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).not.toContain('DEMO-HR');
      expect(calledIds).not.toContain('DEMO-CEO');
    });

    it('CEO user mount: strictly 0 calls to DEMO-CEO; defaults to first eligible contributor', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-CEO',
        name: 'Executive CEO',
        role: ROLES.CEO,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).not.toContain('DEMO-CEO');
      expect(calledIds).not.toContain('DEMO-HR');
      expect(calledIds.filter((id) => id === 'DEMO-CEO')).toHaveLength(0);
    });

    it('Delayed employee API response: zero premature network calls while employees are loading', async () => {
      let resolveEmployees;
      const delayedEmployeesPromise = new Promise((resolve) => {
        resolveEmployees = resolve;
      });
      employeesApi.list.mockReturnValue(delayedEmployeesPromise);

      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      // While employees are loading, getDeveloperDashboard MUST NOT have been called
      expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalled();

      // Now resolve the employee list
      resolveEmployees(mockAdversarialEmployees);

      // Once resolved, it should cleanly invoke the first contributor
      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-DEV-1');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).not.toContain('DEMO-HR');
      expect(calledIds).not.toContain('DEMO-CEO');
    });

    it('Empty employee list: handles empty data gracefully without throwing or calling dashboard API', async () => {
      employeesApi.list.mockResolvedValue([]);

      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      // Expect loading state to show
      expect(await screen.findByText('Loading performance evaluation data...')).toBeInTheDocument();

      // Ensure no dashboard calls were fired
      expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalled();
    });

    it('Zero eligible engineering contributors (only HR, CEO, PM): does not throw and makes 0 dashboard calls', async () => {
      employeesApi.list.mockResolvedValue([
        { employee_id: 'DEMO-HR', name: 'HR Manager', role: 'HR' },
        { employee_id: 'DEMO-CEO', name: 'CEO', role: 'CEO' },
        { employee_id: 'DEMO-PM', name: 'PM', role: 'PM' },
      ]);

      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      expect(await screen.findByText('Loading performance evaluation data...')).toBeInTheDocument();
      expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalled();
    });
  });

  describe('2. Dropdown Evaluation Eligibility Stress Tests', () => {
    it('restricts dropdown strictly to DEVELOPER, LEAD, QA, DEVOPS and excludes all others', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      const select = await screen.findByRole('combobox');
      expect(select).toBeInTheDocument();

      const options = Array.from(select.querySelectorAll('option'))
        .map((o) => o.value)
        .filter(Boolean);

      // Verify legitimate engineering contributors are all included
      const expectedEngineers = [
        'ENG-DEV-1',
        'ENG-DEV-LOWER',
        'ENG-LEAD-1',
        'ENG-LEAD-MIX',
        'ENG-QA-1',
        'ENG-QA-LOWER',
        'ENG-OPS-1',
        'ENG-OPS-MIX',
      ];
      expect(options).toEqual(expectedEngineers);

      // Assert non-engineering and executive roles are strictly excluded
      const prohibitedIds = [
        'DEMO-HR',
        'DEMO-CEO',
        'OTHER-HR',
        'OTHER-CEO',
        'DEMO-PM',
        'PM-2',
        'EMP-INTERN',
        'EMP-DESIGNER',
        'EMP-MARKETING',
        'EMP-FINANCE',
        'EMP-ADMIN',
        'EMP-NULL-ROLE',
        'EMP-EMPTY-ROLE',
      ];
      for (const id of prohibitedIds) {
        expect(options).not.toContain(id);
      }
    });

    it('switching contributors in dropdown calls dashboard with newly selected contributor', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderPerformancePage(['/performance']);

      const select = await screen.findByRole('combobox');
      fireEvent.change(select, { target: { value: 'ENG-OPS-MIX' } });

      await waitFor(() => {
        expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('ENG-OPS-MIX');
      });

      const calledIds = performanceApi.getDeveloperDashboard.mock.calls.map(([id]) => id);
      expect(calledIds).toContain('ENG-OPS-MIX');
      expect(calledIds).not.toContain('DEMO-HR');
      expect(calledIds).not.toContain('DEMO-CEO');
    });
  });
});
