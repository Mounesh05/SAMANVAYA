import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { qaApi } from '../../api/qa.api';
import { sprintsApi } from '../../api/sprints.api';
import { storiesApi } from '../../api/stories.api';
import { TestsPage } from './TestsPage';

vi.mock('../../api/qa.api', () => ({
  qaApi: {
    getProjects: vi.fn(),
    getSuites: vi.fn(),
    getCases: vi.fn(),
    getExecutions: vi.fn(),
    createCase: vi.fn(),
    createExecution: vi.fn(),
    updateCase: vi.fn(),
    cloneCase: vi.fn(),
    createSuite: vi.fn(),
    updateSuite: vi.fn(),
    createDefect: vi.fn(),
  },
}));
vi.mock('../../api/sprints.api', () => ({
  sprintsApi: { listByProject: vi.fn() },
}));
vi.mock('../../api/stories.api', () => ({
  storiesApi: { listBySprint: vi.fn() },
}));

const existingCase = {
  id: 'QAC-1',
  project_id: 'PRJ-1',
  suite_id: 'QAS-1',
  story_id: 'STY-1',
  task_id: 'TSK-1',
  title: 'Create a CampusConnect event',
  description: 'Validate the event creation API.',
  objective: 'A valid event is persisted.',
  preconditions: 'A user is authenticated.',
  expected_result: 'The event is created.',
  priority: 'high',
  test_type: 'functional',
  steps: [{ step_number: 1, instruction: 'Submit event', expected_result: '201 response' }],
};

function renderTestsPage(initialEntries = ['/tests']) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={initialEntries}>
        <TestsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TestsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    qaApi.getProjects.mockResolvedValue([{ id: 'PRJ-1', name: 'CampusConnect' }]);
    qaApi.getSuites.mockResolvedValue([{ id: 'QAS-1', name: 'Event API', status: 'active' }]);
    qaApi.getCases.mockResolvedValue([existingCase]);
    qaApi.getExecutions.mockResolvedValue([]);
    qaApi.createCase.mockResolvedValue({ ...existingCase, id: 'QAC-2' });
    qaApi.createExecution.mockResolvedValue({
      id: 'QAE-1',
      status: 'PASSED',
      actual_result: 'Event returned successfully',
      executed_at: '2026-01-01T10:00:00Z',
      executed_by: 'DEMO-QA',
    });
    sprintsApi.listByProject.mockResolvedValue([{ id: 'SPR-1', name: 'Sprint 1' }]);
    storiesApi.listBySprint.mockResolvedValue([{ id: 'STY-1', title: 'Create event' }]);
  });

  it('creates a project test case with parsed ordered steps', async () => {
    const user = userEvent.setup();
    renderTestsPage();

    await user.click(await screen.findByRole('button', { name: 'New Test Case' }));
    await user.type(screen.getByLabelText(/^Title/), 'Reject an invalid event');
    await user.type(screen.getByLabelText(/^Expected overall result/), 'Validation error is returned.');
    await user.type(
      screen.getByLabelText(/Ordered test steps/),
      'Submit an event without a title => 422 response',
    );
    await user.click(screen.getByRole('button', { name: 'Create Test Case' }));

    await waitFor(() => {
      expect(qaApi.createCase).toHaveBeenCalledWith(expect.objectContaining({
        project_id: 'PRJ-1',
        title: 'Reject an invalid event',
        story_id: null,
        steps: [{
          step_number: 1,
          instruction: 'Submit an event without a title',
          expected_result: '422 response',
        }],
      }));
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Test case created.');
  });

  it('records explicit per-step and overall execution outcomes', async () => {
    const user = userEvent.setup();
    renderTestsPage();

    const row = (await screen.findByText('QAC-1')).closest('tr');
    await user.click(within(row).getByRole('button', { name: 'Execute' }));
    await user.type(screen.getByLabelText(/^Actual step result/), '201 response with event ID');
    await user.selectOptions(screen.getByLabelText('Step outcome'), 'PASSED');
    await user.selectOptions(screen.getByLabelText('Overall execution result'), 'PASSED');
    await user.type(screen.getByLabelText(/^Actual overall result/), 'Event returned successfully');
    await user.click(screen.getByRole('button', { name: 'Save Execution' }));

    await waitFor(() => {
      expect(qaApi.createExecution).toHaveBeenCalledWith('QAC-1', expect.objectContaining({
        test_case_id: 'QAC-1',
        status: 'PASSED',
        actual_result: 'Event returned successfully',
        step_results: [{
          step_number: 1,
          actual_result: '201 response with event ID',
          status: 'PASSED',
          comments: '',
        }],
      }));
    });
    expect(await screen.findByText('Execution saved to history.')).toBeInTheDocument();
    expect(await screen.findByText('Execution history')).toBeInTheDocument();
  });

  it('opens a retest link after asynchronously loading its case and retains the defect link', async () => {
    const user = userEvent.setup();
    renderTestsPage(['/tests?caseId=QAC-1&defectId=QAD-1']);

    expect(await screen.findByRole('heading', { name: 'Execute QAC-1' })).toBeInTheDocument();
    await user.type(screen.getByLabelText(/^Actual step result/), 'Event created on retest');
    await user.selectOptions(screen.getByLabelText(/^Step outcome/), 'PASSED');
    await user.selectOptions(screen.getByLabelText('Overall execution result'), 'PASSED');
    await user.type(screen.getByLabelText(/^Actual overall result/), 'Event created and returned.');
    await user.click(screen.getByRole('button', { name: 'Save Execution' }));

    await waitFor(() => {
      expect(qaApi.createExecution).toHaveBeenCalledWith('QAC-1', expect.objectContaining({
        test_case_id: 'QAC-1',
        defect_id: 'QAD-1',
        status: 'PASSED',
      }));
    });
  });
});
