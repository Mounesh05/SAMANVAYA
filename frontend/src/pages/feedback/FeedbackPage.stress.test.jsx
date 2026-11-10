import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FeedbackPage } from './FeedbackPage';
import { employeesApi } from '../../api/employees.api';
import { useAuthStore } from '../../store/useAuthStore';
import { ToastProvider } from '../../components/common/Toast';
import { ROLES } from '../../utils/constants';

vi.mock('../../api/employees.api', () => ({
  employeesApi: {
    list: vi.fn(),
  },
}));

vi.mock('../../api/feedback.api', () => ({
  feedbackApi: {
    getPending: vi.fn(),
    saveDraft: vi.fn(),
    submitFeedback: vi.fn(),
    saveHRAssessmentDraft: vi.fn(),
    submitHRAssessment: vi.fn(),
    getHRAssessments: vi.fn(),
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

function renderFeedbackPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ToastProvider>
          <FeedbackPage />
        </ToastProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('FeedbackPage Adversarial Stress Tests: Eligibility & Self-Evaluation Prevention', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout();
    employeesApi.list.mockResolvedValue(mockAdversarialEmployees);
  });

  describe('1. Dropdown Role & ID Filtering for HR User', () => {
    it('restricts HR evaluation target strictly to engineering contributors and excludes DEMO-HR, DEMO-CEO, PM, and non-eng roles', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderFeedbackPage();

      expect(await screen.findByText('HR Workplace Performance Assessment')).toBeInTheDocument();

      const select = await screen.findByLabelText(/Target Employee/i);
      const options = Array.from(select.querySelectorAll('option'))
        .map((o) => o.value)
        .filter(Boolean);

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

      // Verify prohibited IDs and non-engineering roles are completely absent
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
  });

  describe('2. Self-Evaluation Prevention Across Roles', () => {
    it('DEVELOPER evaluator cannot evaluate self (ENG-DEV-1 is excluded)', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'ENG-DEV-1',
        name: 'Alice Developer',
        role: ROLES.DEVELOPER,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Engineer/i);
      await waitFor(() => {
        const options = Array.from(select.querySelectorAll('option'))
          .map((o) => o.value)
          .filter(Boolean);

        expect(options).not.toContain('ENG-DEV-1');
        expect(options).toContain('ENG-LEAD-1');
        expect(options).toContain('ENG-QA-1');
        expect(options).toContain('ENG-OPS-1');
        expect(options).not.toContain('DEMO-HR');
        expect(options).not.toContain('DEMO-CEO');
        expect(options).not.toContain('DEMO-PM');
      });
    });

    it('LEAD evaluator cannot evaluate self (ENG-LEAD-1 is excluded)', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'ENG-LEAD-1',
        name: 'Bob TechLead',
        role: ROLES.LEAD,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Engineer/i);
      await waitFor(() => {
        const options = Array.from(select.querySelectorAll('option'))
          .map((o) => o.value)
          .filter(Boolean);

        expect(options).not.toContain('ENG-LEAD-1');
        expect(options).toContain('ENG-DEV-1');
        expect(options).toContain('ENG-QA-1');
        expect(options).toContain('ENG-OPS-1');
        expect(options).not.toContain('DEMO-HR');
        expect(options).not.toContain('DEMO-CEO');
        expect(options).not.toContain('DEMO-PM');
      });
    });

    it('QA evaluator cannot evaluate self (ENG-QA-1 is excluded)', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'ENG-QA-1',
        name: 'Charlie Quality',
        role: ROLES.QA,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Engineer/i);
      await waitFor(() => {
        const options = Array.from(select.querySelectorAll('option'))
          .map((o) => o.value)
          .filter(Boolean);

        expect(options).not.toContain('ENG-QA-1');
        expect(options).toContain('ENG-DEV-1');
        expect(options).toContain('ENG-LEAD-1');
        expect(options).toContain('ENG-OPS-1');
        expect(options).not.toContain('DEMO-HR');
        expect(options).not.toContain('DEMO-CEO');
        expect(options).not.toContain('DEMO-PM');
      });
    });

    it('DEVOPS evaluator cannot evaluate self (ENG-OPS-1 is excluded)', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'ENG-OPS-1',
        name: 'Dave DevOps',
        role: ROLES.DEVOPS,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Engineer/i);
      await waitFor(() => {
        const options = Array.from(select.querySelectorAll('option'))
          .map((o) => o.value)
          .filter(Boolean);

        expect(options).not.toContain('ENG-OPS-1');
        expect(options).toContain('ENG-DEV-1');
        expect(options).toContain('ENG-LEAD-1');
        expect(options).toContain('ENG-QA-1');
        expect(options).not.toContain('DEMO-HR');
        expect(options).not.toContain('DEMO-CEO');
        expect(options).not.toContain('DEMO-PM');
      });
    });

    it('CEO evaluator cannot evaluate self (DEMO-CEO is excluded) or HR or PM', async () => {
      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-CEO',
        name: 'Executive CEO',
        role: ROLES.CEO,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Engineer/i);
      await waitFor(() => {
        const options = Array.from(select.querySelectorAll('option'))
          .map((o) => o.value)
          .filter(Boolean);

        expect(options).not.toContain('DEMO-CEO');
        expect(options).not.toContain('DEMO-HR');
        expect(options).not.toContain('DEMO-PM');
        expect(options).toContain('ENG-DEV-1');
        expect(options).toContain('ENG-LEAD-1');
        expect(options).toContain('ENG-QA-1');
        expect(options).toContain('ENG-OPS-1');
      });
    });
  });

  describe('3. Boundary Resilience', () => {
    it('Empty employee list: renders dropdown with zero options without throwing', async () => {
      employeesApi.list.mockResolvedValue([]);

      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Employee/i);
      const options = Array.from(select.querySelectorAll('option'))
        .map((o) => o.value)
        .filter(Boolean);

      expect(options).toEqual([]);
    });

    it('Only non-engineering employees: renders dropdown with zero options without throwing', async () => {
      employeesApi.list.mockResolvedValue([
        { employee_id: 'DEMO-HR', name: 'HR Manager', role: 'HR' },
        { employee_id: 'DEMO-CEO', name: 'CEO', role: 'CEO' },
        { employee_id: 'DEMO-PM', name: 'PM', role: 'PM' },
        { employee_id: 'EMP-INTERN', name: 'Intern', role: 'INTERN' },
      ]);

      useAuthStore.getState().setAuth('mock-token', {
        employee_id: 'DEMO-HR',
        name: 'HR Manager',
        role: ROLES.HR,
        is_admin: false,
      });

      renderFeedbackPage();

      const select = await screen.findByLabelText(/Target Employee/i);
      const options = Array.from(select.querySelectorAll('option'))
        .map((o) => o.value)
        .filter(Boolean);

      expect(options).toEqual([]);
    });
  });
});
