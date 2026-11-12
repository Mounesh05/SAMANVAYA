import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { FeedbackPage } from './FeedbackPage';
import { performanceApi } from '../../api/performance.api';
import { mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);
describe('server-assigned observation boundaries', () => {
  it.each(['DEVELOPER', 'QA', 'DEVOPS', 'LEAD', 'PM', 'HR', 'CEO'])('%s cannot invent a review target or write a numerical assessment', async (role) => {
    renderScoring(<FeedbackPage />, { role });
    expect(await screen.findByText(/No active assigned reviews/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Record observations' })).not.toBeInTheDocument();
    expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument();
    expect(performanceApi.submitHumanReview).not.toHaveBeenCalled();
  });
  it('reports expired or revoked scope without showing a cached observation form', async () => {
    performanceApi.getAssignments.mockRejectedValue({ response: { status: 403 } });
    renderScoring(<FeedbackPage />);
    expect(await screen.findByRole('alert')).toHaveTextContent(/current account cannot access/);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });
});
