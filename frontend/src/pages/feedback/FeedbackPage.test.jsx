import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import { FeedbackPage } from './FeedbackPage';
import { mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);
describe('assigned feedback entry', () => {
  it('does not offer an arbitrary employee or default numerical rating', async () => {
    renderScoring(<FeedbackPage />);
    expect(await screen.findByText(/No active assigned reviews/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Target Employee/i)).not.toBeInTheDocument();
    expect(screen.queryByRole('slider')).not.toBeInTheDocument();
  });
  it('explains the HR workplace boundary', async () => {
    renderScoring(<FeedbackPage />, { role: 'HR' });
    expect(await screen.findByText(/HR assignments cover workplace observations only/)).toBeInTheDocument();
  });
});
