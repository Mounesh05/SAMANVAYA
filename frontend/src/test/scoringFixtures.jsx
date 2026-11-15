import React from 'react';
import { vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { performanceApi } from '../api/performance.api';
import { employeesApi } from '../api/employees.api';
import { useAuthStore } from '../store/useAuthStore';
import { withPermissions } from '../tests/utils/roleUser';

export const employees = [['D', 'DEVELOPER'], ['Q', 'QA'], ['V', 'DEVOPS'], ['L', 'LEAD'], ['M', 'PM'], ['H', 'HR'], ['C', 'CEO']]
  .map(([employee_id, role]) => ({ employee_id, role, name: `Employee ${employee_id}`, project_ids: ['P'], team_id: 'T' }));
export const assignment = { assignment_id: 'AS-1', employee_id: 'D', role: 'LEAD', dimensions: ['collaboration'],
  period_start: '2026-07-01T00:00:00Z', period_end: '2026-10-01T00:00:00Z' };

export function mockScoringApi() {
  useAuthStore.getState().logout();
  vi.restoreAllMocks();
  const defaults = { getReadiness: { roles: [{ role: 'DEVELOPER', status: 'PENDING_CALIBRATION' }], unresolved_decisions: ['Representative work and policy sign-off'] },
    getAssessments: [], getAssignments: [], getHumanReview: null, getAssessmentHistory: { current: {}, history: [] },
    replayAssessment: { revision: 1, status: 'REPRODUCED' }, appealAssessment: { state: 'DISPUTED' },
    submitHumanReview: { status: 'RECORDED_UNVERIFIED' }, reviseHumanReview: { status: 'RECORDED_UNVERIFIED' },
    evaluateDeveloper: {}, evaluateBulk: {} };
  for (const [method, result] of Object.entries(defaults)) vi.spyOn(performanceApi, method).mockResolvedValue(result);
  vi.spyOn(performanceApi, 'getDeveloperDashboard').mockImplementation(async (id) => ({ current_performance: {
    developer_id: id, developer_name: `Employee ${id}`, overall_score: 85.4, grade: 'B+',
    scoring: { mode: 'LEGACY_READ_ONLY', status: 'LEGACY_UNVERIFIABLE' }, ai_evaluation: { confidence_score: null } }, historical_trend: [] }));
  vi.spyOn(employeesApi, 'list').mockResolvedValue(employees);
}

export function renderScoring(ui, { role = 'LEAD', id = 'R', path = '/performance' } = {}) {
  useAuthStore.getState().setAuth('synthetic-ui-token', withPermissions({ employee_id: id, name: 'Synthetic reviewer', role, project_ids: ['P'], team_id: 'T' }));
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></QueryClientProvider>);
}
