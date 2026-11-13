import { withPermissions } from '../../tests/utils/roleUser';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { FeedbackPage } from './FeedbackPage';
import { employeesApi } from '../../api/employees.api';
import { feedbackApi } from '../../api/feedback.api';
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

const mockEmployees = [
  { employee_id: 'DEMO-HR', name: 'HR Manager', role: 'HR', designation: 'HR Lead' },
  { employee_id: 'DEMO-CEO', name: 'Executive CEO', role: 'CEO', designation: 'Chief Executive' },
  { employee_id: 'DEMO-PM', name: 'Product Manager', role: 'PM', designation: 'Senior PM' },
  { employee_id: 'DEMO-DEV1', name: 'Alice Developer', role: 'DEVELOPER', designation: 'Fullstack Dev' },
  { employee_id: 'DEMO-LEAD1', name: 'Bob Lead', role: 'LEAD', designation: 'Tech Lead' },
  { employee_id: 'DEMO-QA1', name: 'Charlie QA', role: 'QA', designation: 'Quality Analyst' },
  { employee_id: 'DEMO-OPS1', name: 'Dave DevOps', role: 'DEVOPS', designation: 'Site Reliability' },
];

function renderPage() {
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

describe('FeedbackPage Employee Evaluation Dropdown Filtering', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.getState().logout();
    employeesApi.list.mockResolvedValue(mockEmployees);
  });

  it('as HR user, restricts target dropdown to engineering contributors and excludes HR, CEO, PM, and self', async () => {
    useAuthStore.getState().setAuth('mock-token', withPermissions({
      employee_id: 'DEMO-HR',
      name: 'HR Manager',
      role: ROLES.HR,
      is_admin: false,
    }));

    renderPage();

    expect(await screen.findByText('HR Workplace Performance Assessment')).toBeInTheDocument();

    const select = await screen.findByLabelText(/Target Employee/i);
    const options = Array.from(select.querySelectorAll('option'))
      .map((o) => o.value)
      .filter(Boolean);

    // Engineering contributors must be present
    expect(options).toEqual(['DEMO-DEV1', 'DEMO-LEAD1', 'DEMO-QA1', 'DEMO-OPS1']);

    // Non-engineering roles, HR, CEO, and self must NOT be present
    expect(options).not.toContain('DEMO-HR');
    expect(options).not.toContain('DEMO-CEO');
    expect(options).not.toContain('DEMO-PM');
    expect(options).toHaveLength(4);
  });

  it('as engineering Lead, excludes self, non-engineering PM, HR, and CEO', async () => {
    useAuthStore.getState().setAuth('mock-token', withPermissions({
      employee_id: 'DEMO-LEAD1',
      name: 'Bob Lead',
      role: ROLES.LEAD,
      is_admin: false,
    }));

    renderPage();

    expect(await screen.findByText('Role-Specific Human Feedback')).toBeInTheDocument();

    const select = await screen.findByLabelText(/Target Engineer/i);
    const options = Array.from(select.querySelectorAll('option'))
      .map((o) => o.value)
      .filter(Boolean);

    // Engineering contributors excluding self (DEMO-LEAD1)
    expect(options).toEqual(['DEMO-DEV1', 'DEMO-QA1', 'DEMO-OPS1']);
    expect(options).not.toContain('DEMO-LEAD1');
    expect(options).not.toContain('DEMO-HR');
    expect(options).not.toContain('DEMO-CEO');
    expect(options).not.toContain('DEMO-PM');
    expect(options).toHaveLength(3);
  });
});
