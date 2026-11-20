import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it, vi } from 'vitest';
import { CicdLogsPage } from './CicdLogsPage';
import { cicdLogsApi } from '../../api/cicdLogs.api';

vi.mock('../../api/cicdLogs.api', () => ({ cicdLogsApi: { analyzeLog: vi.fn() } }));

function show() {
  const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  render(<QueryClientProvider client={client}><MemoryRouter><CicdLogsPage /></MemoryRouter></QueryClientProvider>);
  fireEvent.click(screen.getByRole('button', { name: 'Diagnose Log with AI' }));
}

it('shows invalid model output as failed without hiding the deterministic result', async () => {
  cicdLogsApi.analyzeLog.mockResolvedValue({ log_type: 'build', risk_score: 10, risk_level: 'LOW',
    ai_status: 'failed', ai_errors: ['INVALID_MODEL_RESPONSE'], root_cause: null });
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('AI analysis failed');
  expect(screen.getByRole('alert')).toHaveTextContent('INVALID_MODEL_RESPONSE');
  expect(screen.getByText(/10/)).toBeInTheDocument();
  expect(screen.getByText(/Deterministic log risk/)).toBeInTheDocument();
});

it('shows request failures instead of retaining an apparent successful diagnosis', async () => {
  cicdLogsApi.analyzeLog.mockRejectedValue(new Error('Service unavailable'));
  show();
  expect(await screen.findByRole('alert')).toHaveTextContent('Service unavailable');
});

it('labels successful model interpretation as advisory', async () => {
  cicdLogsApi.analyzeLog.mockResolvedValue({ log_type: 'build', risk_score: 10, risk_level: 'LOW',
    ai_status: 'completed', root_cause: 'Synthetic compilation failure', fix_recommendations: ['Declare the missing name'] });
  show();
  expect(await screen.findByText(/AI-assisted advisory interpretation/)).toBeInTheDocument();
  expect(screen.getByText('Declare the missing name')).toBeInTheDocument();
});
