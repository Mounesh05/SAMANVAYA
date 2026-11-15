import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { RoleGuard } from '../auth/RoleGuard';
import { AssignedFeedbackPage } from '../pages/feedback/AssignedFeedbackPage';
import { GovernedPerformancePage } from '../pages/performance/GovernedPerformancePage';
import { ScoreCard } from '../components/common/ScoreCard';
import { mockScoringApi, renderScoring } from '../test/scoringFixtures';
import { performanceApi } from '../api/performance.api';

beforeEach(mockScoringApi);

describe('testing history integration boundaries', () => {
  it('does not fetch assigned observations through a forbidden feedback route', () => {
    renderScoring(<RoleGuard page="feedback"><AssignedFeedbackPage /></RoleGuard>, { role: 'DEVELOPER', id: 'D' });
    expect(performanceApi.getAssignments).not.toHaveBeenCalled();
    expect(screen.queryByText('Assigned observations')).not.toBeInTheDocument();
  });

  it('retains the assigned-review workflow for an authorized reviewer', async () => {
    renderScoring(<RoleGuard page="feedback"><AssignedFeedbackPage /></RoleGuard>, { role: 'LEAD', id: 'L' });
    expect(await screen.findByText(/No active assigned reviews/)).toBeVisible();
    expect(performanceApi.getAssignments).toHaveBeenCalledTimes(1);
  });

  it('does not broaden PM individual performance access through the restored view', async () => {
    renderScoring(<GovernedPerformancePage />, { role: 'PM', id: 'M', path: '/performance/assessments?developer=D' });
    await screen.findByText(/Legacy record/);
    expect([...screen.getByLabelText('Employee').options].map((option) => option.value)).toEqual(['M']);
    await waitFor(() => expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('M'));
    expect(performanceApi.getDeveloperDashboard).not.toHaveBeenCalledWith('D');
  });

  it('uses authoritative assessment metadata rather than a legacy numerical value', () => {
    renderScoring(<ScoreCard score={85.4} scoring={{ state: 'APPROVED', approved_score: 73 }} />);
    expect(screen.getByText('Approved assessment')).toBeVisible();
    expect(screen.getByText('73.0')).toBeVisible();
    expect(screen.queryByText('85.4')).not.toBeInTheDocument();
  });
});
