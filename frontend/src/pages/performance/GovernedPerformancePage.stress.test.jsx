import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { GovernedPerformancePage as PerformancePage } from './GovernedPerformancePage';
import { employeesApi } from '../../api/employees.api';
import { performanceApi } from '../../api/performance.api';
import { mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);
describe('performance scope and unknown states', () => {
  it.each(['DEVELOPER', 'QA', 'DEVOPS', 'LEAD', 'PM', 'HR', 'CEO'])('keeps %s usable without a numeric approval claim', async (role) => {
    const id = { DEVELOPER: 'D', QA: 'Q', DEVOPS: 'V', LEAD: 'L', PM: 'M', HR: 'H', CEO: 'C' }[role];
    renderScoring(<PerformancePage />, { role, id });
    expect(await screen.findByText(/Legacy record — unverified methodology/)).toBeInTheDocument();
    expect(performanceApi.evaluateDeveloper).not.toHaveBeenCalled();
  });
  it('shows a real empty state without querying an empty employee identity', async () => {
    employeesApi.list.mockResolvedValue([]);
    renderScoring(<PerformancePage />);
    expect(await screen.findByText('No engineering history available in this scope')).toBeInTheDocument();
    expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalled();
  });
  it('waits for eligible employee data before querying an adversarial URL identity', async () => {
    let resolve;
    employeesApi.list.mockReturnValue(new Promise((done) => { resolve = done; }));
    renderScoring(<PerformancePage />, { role: 'HR', path: '/performance?developer=FOREIGN' });
    expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalled();
    resolve([{ employee_id: 'D', role: 'DEVELOPER', name: 'Scoped employee' }]);
    await waitFor(() => expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('D'));
    expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalledWith('FOREIGN');
  });
});
