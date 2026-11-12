import React from 'react';
import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { PerformancePage } from './PerformancePage';
import { performanceApi } from '../../api/performance.api';
import { mockScoringApi, renderScoring } from '../../test/scoringFixtures';

beforeEach(mockScoringApi);
describe('performance record migration', () => {
  it('labels historical results and removes retired numerical evaluation controls', async () => {
    renderScoring(<PerformancePage />, { role: 'HR' });
    expect(await screen.findByText(/Legacy record — unverified methodology/)).toBeInTheDocument();
    expect(screen.queryByText(/Approved Performance$/)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /recalculate|calculate contribution/i })).not.toBeInTheDocument();
    expect(screen.queryByText('85%')).not.toBeInTheDocument();
    expect(performanceApi.evaluateDeveloper).not.toHaveBeenCalled();
  });
  it('supports all five engineering subject roles, including PM, with unavailable rubrics explicit', async () => {
    renderScoring(<PerformancePage />, { role: 'CEO' });
    const select = await screen.findByLabelText('Employee');
    expect([...select.options].map((o) => o.value)).toEqual(['D', 'Q', 'V', 'L', 'M']);
    fireEvent.change(select, { target: { value: 'M' } });
    await waitFor(() => expect(performanceApi.getDeveloperDashboard).toHaveBeenCalledWith('M'));
  });
  it('does not misdescribe a scope denial as an AI outage', async () => {
    performanceApi.getDeveloperDashboard.mockRejectedValue({ response: { status: 403 } });
    renderScoring(<PerformancePage />);
    expect(await screen.findByText(/current account cannot access/)).toBeInTheDocument();
    expect(screen.queryByText(/start Ollama/i)).not.toBeInTheDocument();
  });
});
