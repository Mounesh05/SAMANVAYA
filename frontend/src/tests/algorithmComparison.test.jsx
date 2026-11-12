import React from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AlgorithmComparisonPanel } from '../pages/code-quality/AlgorithmComparisonPanel';
import { algorithmsApi } from '../api/algorithms.api';
import apiClient from '../api/client';
import { useAuthStore } from '../store/useAuthStore';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { server } from './mocks/server';
import { CodeQualityPage } from '../pages/code-quality/CodeQualityPage';
import { codeQualityApi } from '../api/codeQuality.api';

vi.mock('../api/algorithms.api', () => ({
  algorithmsApi: {
    getAvailability: vi.fn(), startRun: vi.fn(), getRun: vi.fn(),
    getHistory: vi.fn(), submitFeedback: vi.fn(), getExplanation: vi.fn(),
    inspectStructure: vi.fn(), getCompatibleHistory: vi.fn(), reevaluate: vi.fn(),
  },
}));

let client;
function renderPanel() {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><AlgorithmComparisonPanel /></QueryClientProvider>);
}
function change(label, value) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}
function fillForm() {
  change('Benchmark project ID', ' project-1 ');
  for (let index = 1; index <= 2; index += 1) {
    change(`Candidate ${index} name`, `sort-${index}`);
    change(`Candidate ${index} entrypoint`, 'sort_numbers');
    change(`Candidate ${index} source`, 'def sort_numbers(values):\n    return sorted(values)\n');
  }
}
const completedRun = {
  run_id: 'run-1', status: 'completed', error: null,
  request: { language: 'javascript', objective: 'time', repetitions: 5, seed: 42 },
  results: [{ candidate: 'sort-1', cases: [{ size: 100, distribution: 'random', correct: false,
    timings_seconds: [0.3, 0.1, 0.2], memory_bytes: 128, memory_metric: 'node_heap_delta_bytes', error: 'Incorrect order' }] }],
  recommendation: { status: 'insufficient_evidence', winner: null, reason: 'Correctness failed',
    rankings: [{ candidate: 'sort-1', eligible: false, median_seconds: 0.2, peak_memory_bytes: null, reason: 'Incorrect output' }],
    limitations: ['Node measurements are noisy'] },
  historical_evidence: [{ run_id: 'older-run', created_at: '2026-01-01', winner: 'sort-2', reason: 'Prior measurement', environment_match: false, requires_fresh_benchmark: true, source_hashes: { 'sort-2': 'historical-source-hash' } }],
    environment: { docker_version: 'test-docker' }, tools: { node: 'test-node' },
};

beforeEach(() => {
  vi.resetAllMocks();
  useAuthStore.setState({ user: { role: 'DEVELOPER' } });
  algorithmsApi.getAvailability.mockResolvedValue({ available: true, error: null, environment: {} });
  algorithmsApi.startRun.mockResolvedValue({ run_id: 'run-1', status: 'pending' });
  algorithmsApi.getRun.mockResolvedValue({ run_id: 'run-1', status: 'pending' });
  algorithmsApi.getHistory.mockResolvedValue({ history: [] });
  algorithmsApi.inspectStructure.mockResolvedValue({ structural_analysis: { total: { loops: 1 } }, execution_performed: false, environment: { parser: 'host-ast' } });
  algorithmsApi.getCompatibleHistory.mockResolvedValue({ history: [], historical_only: true, limitations: ['Historical evidence requires a fresh benchmark'] });
  algorithmsApi.submitFeedback.mockImplementation((_id, data) => Promise.resolve(data));
  algorithmsApi.getExplanation.mockResolvedValue({ status: 'unavailable', explanation: null, error: 'No model configured', citations: [] });
});
afterEach(() => {
  cleanup();
  client?.clear();
  vi.useRealTimers();
  useAuthStore.setState({ user: null });
  localStorage.removeItem('samanvaya_token');
});

async function ready() {
  renderPanel();
  await screen.findByText('Benchmark worker available.');
}
function submit() {
  fireEvent.click(screen.getByRole('button', { name: 'Run sorting benchmark' }));
}

describe('Numeric sorting benchmark', () => {
  it('starts with empty editors and validates required fields, names, bounded sizes, and memory limit', async () => {
    await ready();
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('');
    expect(screen.getByLabelText('Candidate 2 source')).toHaveValue('');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a project ID');
    change('Benchmark project ID', 'project-1');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('both candidates');
    fillForm();
    change('Candidate 2 name', 'sort-1');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('names must be unique');
    change('Candidate 2 name', 'sort-2');
    for (const invalid of ['-1', '1.5', '100,', '1e3', '10001', '9007199254740992']) {
      change('Input sizes', invalid);
      submit();
      expect(screen.getByRole('alert')).toHaveTextContent('integers in 0..10000');
    }
    change('Input sizes', '100, 100');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('Sizes must be unique');
    change('Input sizes', '100, 1000');
    change('Memory limit in bytes (optional)', '-1');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('Memory limit must be a positive integer');
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it('allows developers and submits the exact reproducible payload', async () => {
    await ready();
    fillForm();
    submit();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalledWith({
      project_id: 'project-1', language: 'python',
      candidates: [1, 2].map((index) => ({ name: `sort-${index}`, entrypoint: 'sort_numbers', source: 'def sort_numbers(values):\n    return sorted(values)\n' })),
      sizes: [0, 1, 100, 1000], distributions: ['random', 'sorted', 'reversed', 'duplicates'],
      repetitions: 5, seed: 42, objective: 'time', memory_limit_bytes: null,
    }));
    await screen.findByText('Status: pending');
    expect(algorithmsApi.getRun).toHaveBeenCalledWith('run-1');
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
  });

  it('restricts memory objective to Python and sends an optional byte limit', async () => {
    await ready();
    fillForm();
    change('Benchmark objective', 'memory');
    change('Memory limit in bytes (optional)', '1048576');
    change('Benchmark language', 'typescript');
    expect(screen.getByLabelText('Memory limit in bytes (optional)')).toBeDisabled();
    expect(screen.getByLabelText('Memory limit in bytes (optional)')).toHaveValue('');
    expect(screen.getByLabelText('Benchmark objective')).toHaveValue('time');
    expect(screen.queryByRole('option', { name: 'memory' })).not.toBeInTheDocument();
    change('Benchmark language', 'python');
    change('Benchmark objective', 'memory');
    change('Memory limit in bytes (optional)', '1048576');
    submit();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalledWith(expect.objectContaining({ objective: 'memory', memory_limit_bytes: 1048576 })));
  });

  it('keeps history usable when unavailable and loads full evidence with feedback and opt-in explanation', async () => {
    algorithmsApi.getAvailability.mockResolvedValue({ available: false, error: 'Worker offline' });
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ run_id: 'run-1', status: 'completed' }] });
    algorithmsApi.getRun.mockResolvedValue(completedRun);
    renderPanel();
    await screen.findByText(/Worker offline/);
    expect(screen.getByRole('button', { name: 'Run sorting benchmark' })).toBeDisabled();
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'run-1' }));
    await screen.findByText('Status: completed');
    expect(algorithmsApi.getHistory).toHaveBeenCalledWith('project-1', 10);
    expect(screen.getByText('Fail')).toBeInTheDocument();
    expect(screen.getByText('0.200000 s')).toBeInTheDocument();
    expect(screen.getByText('0.3, 0.1, 0.2')).toBeInTheDocument();
    expect(screen.getByText(/Node heap delta \(not peak\)/)).toBeInTheDocument();
    expect(screen.getByText('Insufficient evidence')).toBeInTheDocument();
    expect(screen.getByText('Node measurements are noisy')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'older-run' })).toBeInTheDocument();
    expect(screen.getByText(/Environment: Differs from current run/)).toBeInTheDocument();
    expect(screen.getByText(/Historical context only, separate from/)).toBeInTheDocument();
    expect(screen.getByText(/historical-source-hash/)).toBeInTheDocument();
    expect(screen.getByText(/test-docker/)).toBeInTheDocument();
    expect(screen.getByText('No eligible candidates to rank.')).toBeInTheDocument();
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Accept recommendation' }));
    expect(screen.getByText('Enter a reason for your decision.')).toHaveAttribute('role', 'alert');
    change('Feedback reason', ' Measured result reviewed ');
    fireEvent.click(screen.getByRole('button', { name: 'Reject recommendation' }));
    await waitFor(() => expect(algorithmsApi.submitFeedback).toHaveBeenCalledWith('run-1', { decision: 'rejected', reason: 'Measured result reviewed' }));
    fireEvent.click(screen.getByRole('button', { name: 'Request explanation' }));
    await screen.findByText('Explanation status: unavailable');
    expect(algorithmsApi.getExplanation).toHaveBeenCalledWith('run-1');
  });

  it.each(['completed', 'failed', 'unavailable'])('polls pending/running and stops at %s', async (status) => {
    vi.useFakeTimers();
    algorithmsApi.getRun.mockResolvedValueOnce({ run_id: 'run-1', status: 'pending' })
      .mockResolvedValueOnce({ run_id: 'run-1', status: 'running' })
      .mockResolvedValue({ run_id: 'run-1', status, error: status === 'completed' ? null : 'Worker could not execute' });
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ run_id: 'run-1', status: 'pending' }] });
    renderPanel();
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    fireEvent.click(screen.getByRole('button', { name: 'run-1' }));
    await act(async () => { await vi.advanceTimersByTimeAsync(50); });
    expect(screen.getByText('Status: pending')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(screen.getByText('Status: running')).toBeInTheDocument();
    await act(async () => { await vi.advanceTimersByTimeAsync(2100); });
    expect(screen.getByText(`Status: ${status}`)).toBeInTheDocument();
    const calls = algorithmsApi.getRun.mock.calls.length;
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(algorithmsApi.getRun).toHaveBeenCalledTimes(calls);
    if (status !== 'completed') expect(screen.getByRole('alert')).toHaveTextContent('Worker could not execute');
  });

  it('reports probe, submission and run fetch errors with manual recovery', async () => {
    algorithmsApi.getAvailability.mockRejectedValueOnce(new Error('Probe denied'));
    renderPanel();
    await screen.findByText(/Probe denied/);
    fireEvent.click(screen.getByRole('button', { name: 'Recheck availability' }));
    await screen.findByText('Benchmark worker available.');
    fillForm();
    algorithmsApi.startRun.mockRejectedValueOnce(new Error('Request denied'));
    submit();
    await screen.findByText('Request denied');
    algorithmsApi.getRun.mockRejectedValueOnce(new Error('Run fetch failed'));
    submit();
    await screen.findByText('Run fetch failed');
    fireEvent.click(screen.getByRole('button', { name: 'Retry loading run' }));
    await screen.findByText('Status: pending');
  });

  it('does not allow non-engineering roles to submit but keeps the panel visible', async () => {
    useAuthStore.setState({ user: { role: 'HR' } });
    await ready();
    expect(screen.getByRole('button', { name: 'Run sorting benchmark' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Load project history' })).toBeInTheDocument();
  });

  it('validates identifiers, UTF-8 source and API bounds before sending source', async () => {
    await ready();
    fillForm();
    for (const entrypoint of ['sort(values)', 'module.sort', '$sort', 'class', 'a'.repeat(129)]) {
      change('Candidate 1 entrypoint', entrypoint);
      submit();
      expect(screen.getByRole('alert')).toHaveTextContent('simple function identifiers');
    }
    change('Candidate 1 entrypoint', 'sort_numbers');
    change('Candidate 1 source', 'é'.repeat(100001));
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('200000 UTF-8 bytes');
    fillForm();
    change('Input sizes', Array.from({ length: 17 }, (_, index) => index).join(','));
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('at most 16 sizes');
    change('Input sizes', '0, 1, 10000');
    change('Memory limit in bytes (optional)', '536870913');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('up to 536870912 bytes');
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it.each(['javascript', 'typescript'])('submits %s without unsupported memory constraints or rewriting the sources', async (language) => {
    await ready();
    fillForm();
    change('Memory limit in bytes (optional)', '1024');
    change('Benchmark language', language);
    for (let index = 1; index <= 2; index += 1) {
      change(`Candidate ${index} entrypoint`, '$sort');
      change(`Candidate ${index} source`, 'function $sort(values) { return values.sort((a, b) => a - b); }');
    }
    submit();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalledWith(expect.objectContaining({ language, objective: 'time', memory_limit_bytes: null })));
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('function $sort(values) { return values.sort((a, b) => a - b); }');
    expect(screen.getByText(/never automatically rewrite or apply source changes/)).toBeInTheDocument();
    expect(screen.getByText(/Unsupported contracts: async functions/)).toBeInTheDocument();
  });

  it('shows the server ranking score separately from medians and excluded diagnostics', async () => {
    algorithmsApi.getRun.mockResolvedValue({
      ...completedRun,
      recommendation: { status: 'recommended', winner: 'sort-2', reason: 'Only passing candidate', limitations: [], rankings: [
        { candidate: 'sort-2', eligible: true, timing_score_seconds: 0.125, median_seconds: 0.2, peak_memory_bytes: null, reason: 'Complete evidence' },
        { candidate: 'sort-1', eligible: false, timing_score_seconds: 0.001, median_seconds: 0.001, reason: 'Incorrect output' },
      ] },
    });
    await ready();
    fillForm();
    submit();
    await screen.findByText('Recommended: sort-2');
    const rankings = screen.getByRole('list', { name: 'Eligible measurement rankings' });
    expect(within(rankings).getAllByRole('listitem')).toHaveLength(1);
    expect(rankings).not.toHaveTextContent('sort-1');
    expect(screen.getByText(/sort-2 — Eligible; timing score: 0.125000 s; median summary: 0.200000 s/)).toBeInTheDocument();
    expect(screen.getByText('sort-1 — Ineligible. Incorrect output')).toBeInTheDocument();
    expect(screen.queryByText(/0.00100000 s/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('def sort_numbers(values):\n    return sorted(values)\n');
  });

  it.each([
    ['HR', false, 'completed', false],
    ['ADMIN', false, 'completed', false],
    ['HR', true, 'completed', true],
    ['DEVELOPER', false, 'failed', false],
    ['DEVELOPER', false, 'unavailable', false],
    ['DEVELOPER', false, 'running', false],
  ])('gates review actions for role %s, admin %s, status %s', async (role, is_admin, status, canReview) => {
    useAuthStore.setState({ user: { role, is_admin } });
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ run_id: 'run-1', status }] });
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun, status });
    await ready();
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'run-1' }));
    await screen.findByText(`Status: ${status}`);
    expect(Boolean(screen.queryByRole('button', { name: 'Request explanation' }))).toBe(canReview);
    expect(Boolean(screen.queryByRole('button', { name: 'Accept recommendation' }))).toBe(canReview);
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
  });

  it('does not trust stale successful availability after a failed recheck', async () => {
    await ready();
    fillForm();
    algorithmsApi.getAvailability.mockRejectedValueOnce(new Error('Daemon probe failed'));
    fireEvent.click(screen.getByRole('button', { name: 'Recheck availability' }));
    await screen.findByText(/Daemon probe failed/);
    expect(screen.queryByText('Benchmark worker available.')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Run sorting benchmark' })).toBeDisabled();
    fireEvent.submit(screen.getByRole('form', { name: 'Numeric sorting benchmark form' }));
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it('keeps the benchmark and existing quality analysis flow independent on the quality screen', async () => {
    // Permissions come from /api/auth/me; QA holds TRIGGER_CODE_ANALYSIS.
    useAuthStore.setState({ user: { role: 'QA', permissions: ['TRIGGER_CODE_ANALYSIS'] } });
    const analyze = vi.spyOn(codeQualityApi, 'startAnalysis').mockResolvedValue({});
    client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<MemoryRouter><QueryClientProvider client={client}><CodeQualityPage /></QueryClientProvider></MemoryRouter>);
    await screen.findByText('Benchmark worker available.');
    expect(screen.getByText('Analysis History')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Start Analysis Run' }));
    change(/Repository or Project ID/, 'real-repository');
    fireEvent.change(screen.getByPlaceholderText('Paste real changed repository paths, one per line'), { target: { value: 'src/real.py' } });
    fireEvent.click(screen.getByRole('button', { name: 'Run Analysis' }));
    await waitFor(() => expect(analyze).toHaveBeenCalledWith(expect.objectContaining({ repository_id: 'real-repository', changed_files: ['src/real.py'], analysis_level: 'standard', use_ai: true })));
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('');
  });

  it('renders untrusted explanation text without interpreting HTML', async () => {
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ run_id: 'run-1', status: 'completed' }] });
    algorithmsApi.getRun.mockResolvedValue(completedRun);
    algorithmsApi.getExplanation.mockResolvedValue({ status: 'generated', explanation: '<img src=x onerror=alert(1)>', citations: ['run-1'] });
    await ready();
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'run-1' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Request explanation' }));
    expect(await screen.findByText('<img src=x onerror=alert(1)>')).toBeInTheDocument();
    expect(screen.queryByRole('img')).not.toBeInTheDocument();
    expect(screen.getByText('Citations: run-1')).toBeInTheDocument();
  });
});

describe('Generic function benchmark', () => {
  async function genericForm() {
    await ready();
    change('Benchmark mode', 'generic');
    change('Benchmark project ID', ' project-1 ');
    fireEvent.click(screen.getByRole('button', { name: 'Remove candidate 2' }));
    change('Candidate 1 name', ' arbitrary-label ');
    change('Candidate 1 entrypoint', 'total');
    change('Candidate 1 source', 'def total(values):\n    return sum(values)\n');
    return JSON.parse(screen.getByLabelText('Contract and datasets JSON').value);
  }
  function runGeneric() {
    fireEvent.click(screen.getByRole('button', { name: 'Run generic benchmark' }));
  }

  it('submits a single arbitrary function with the sum contract, custom datasets and resources without rewriting source', async () => {
    const payload = await genericForm();
    const resources = { timeout_seconds: 12, memory_bytes: 67108864, cpus: 0.5, pids: 16 };
    change('Resources JSON (optional)', JSON.stringify(resources));
    expect(screen.queryByLabelText('Input sizes')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove candidate 1' })).toBeDisabled();
    runGeneric();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalledWith({
      project_id: 'project-1', language: 'python',
      candidates: [{ name: 'arbitrary-label', entrypoint: 'total', source: 'def total(values):\n    return sum(values)\n' }],
      ...payload, resources, repetitions: 5, seed: 42, objective: 'time', memory_limit_bytes: null,
    }));
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue('def total(values):\n    return sum(values)\n');
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
  });

  it.each([
    ['{', 'valid JSON'],
    ['null', 'containing only contract and datasets'],
    [JSON.stringify({ contract: null, datasets: [] }), 'non-null object'],
  ])('blocks malformed generic payload %s without falling back to sorting', async (text, message) => {
    await genericForm();
    change('Contract and datasets JSON', text);
    runGeneric();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it('validates dataset bounds, expected-value presence and output argument selection', async () => {
    const payload = await genericForm();
    const invalid = [
      [{ ...payload, datasets: [] }, '1..32 datasets'],
      [{ ...payload, datasets: Array.from({ length: 33 }, (_, id) => ({ id: String(id), args: [], expected: 0 })) }, '1..32 datasets'],
      [{ ...payload, datasets: [{ id: 'missing', args: [[]] }] }, 'explicit expected'],
      [{ ...payload, datasets: [payload.datasets[0], payload.datasets[0]] }, 'ids must be unique'],
      [{ ...payload, contract: { ...payload.contract, output: { source: 'argument', index: 1 } } }, 'index must exist'],
      [{ ...payload, contract: { ...payload.contract, output: null } }, 'Output must select'],
      [{ ...payload, contract: { ...payload.contract, correctness: 'none' } }, 'Remove expected values'],
    ];
    for (const [value, message] of invalid) {
      change('Contract and datasets JSON', JSON.stringify(value));
      runGeneric();
      expect(screen.getByRole('alert')).toHaveTextContent(message);
    }
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it.each([
    ['{', 'valid JSON'], ['null', 'must be an object'],
    ['{"timeout_seconds":121}', 'timeout_seconds'], ['{"memory_bytes":67108863}', 'memory_bytes'],
    ['{"cpus":0.09}', 'cpus'], ['{"pids":15}', 'pids'], ['{"pids":16.5}', 'pids'],
    ['{"unknown":1}', 'Unsupported resource'], ['{"constructor":1}', 'Unsupported resource'],
  ])('rejects invalid resources %s', async (text, message) => {
    await genericForm();
    change('Resources JSON (optional)', text);
    runGeneric();
    expect(screen.getByRole('alert')).toHaveTextContent(message);
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });

  it('supports argument output, empty output schema and explicit null expected', async () => {
    const payload = await genericForm();
    payload.contract.output = { source: 'argument', index: 0 };
    payload.contract.mutation = 'allowed';
    payload.contract.output_schema = {};
    payload.datasets = [{ id: 'null-value', args: [null], expected: null }];
    payload.contract.input_schema = { type: 'array' };
    change('Contract and datasets JSON', JSON.stringify(payload));
    runGeneric();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalledWith(expect.objectContaining(payload)));
    expect(algorithmsApi.startRun.mock.calls[0][0]).not.toHaveProperty('resources');
  });

  it('shows unverified measurements without pass/fail or eligibility and displays provenance and parent structural evidence', async () => {
    const payload = await genericForm();
    payload.contract.correctness = 'none';
    payload.datasets = [{ id: 'custom-case', args: [[5, 8]], dimensions: { count: 2 } }];
    change('Contract and datasets JSON', JSON.stringify(payload));
    algorithmsApi.getRun.mockResolvedValue({
      ...completedRun,
      request: { ...completedRun.request, ...payload, resources: { cpus: 0.5 } },
      results: [{ candidate: 'arbitrary-label', structure: { origin: 'worker-fallback' }, cases: [{
        case_id: 'custom-case', dimensions: { count: 2 }, correct: null, validation_status: 'unverified',
        timings_seconds: [0.02, 0.04, 0.03], memory_bytes: -32, memory_metric: 'node_heap_delta_bytes', error: null,
      }] }],
      structural_analysis: { 'arbitrary-label': { origin: 'parent-module', loops: 1 } },
      recommendation: { status: 'insufficient_evidence', winner: null, reason: 'Unverified evidence',
        rankings: [{ candidate: 'arbitrary-label', eligible: false, reason: 'Correctness not verified' }], limitations: [] },
      historical_evidence: [],
    });
    runGeneric();
    const table = await screen.findByRole('table', { name: 'Measured cases for arbitrary-label' });
    expect(within(table).getByText('Unverified')).toBeInTheDocument();
    expect(within(table).getByText('unverified')).toBeInTheDocument();
    expect(within(table).queryByText(/^(Pass|Fail)$/)).not.toBeInTheDocument();
    expect(within(table).getByText('custom-case')).toBeInTheDocument();
    expect(within(table).getByText('{"count":2}')).toBeInTheDocument();
    expect(within(table).getByText('0.0300000 s')).toBeInTheDocument();
    expect(within(table).getByText('-32')).toBeInTheDocument();
    expect(within(table).queryByRole('columnheader', { name: 'Size' })).not.toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Eligible measurement rankings' })).toBeEmptyDOMElement();
    expect(screen.getByText('Insufficient evidence')).toBeInTheDocument();
    expect(screen.queryByText(/^Recommended:/)).not.toBeInTheDocument();
    const provenance = screen.getByText('Request provenance: contract, datasets and resources').closest('details');
    expect(provenance).toHaveTextContent('sum-numbers');
    expect(provenance).toHaveTextContent('custom-case');
    expect(provenance).toHaveTextContent('"cpus": 0.5');
    expect(screen.getByText(/"origin": "parent-module"/)).toBeInTheDocument();
    expect(screen.queryByText(/"origin": "worker-fallback"/)).not.toBeInTheDocument();
    expect(screen.getByText(/not an asymptotic proof/)).toBeInTheDocument();
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
  });

  it.each([undefined, null])('renders worker structural evidence when the parent report is %s', async (parentReport) => {
    const payload = await genericForm();
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun, request: payload,
      results: [{ candidate: 'arbitrary-label', cases: [], structure: { origin: 'js-worker', loops: 2 } }],
      structural_analysis: { 'arbitrary-label': parentReport },
    });
    runGeneric();
    expect(await screen.findByText(/"origin": "js-worker"/)).toBeInTheDocument();
    expect(screen.getByText('Structural evidence for arbitrary-label')).toBeInTheDocument();
  });

  it('requests a generic explanation only on click without changing source, measurements or rankings', async () => {
    const payload = await genericForm();
    payload.contract.correctness = 'none';
    payload.datasets = [{ id: 'unchecked', args: [[1, 2]] }];
    change('Contract and datasets JSON', JSON.stringify(payload));
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun, request: payload,
      results: [{ candidate: 'arbitrary-label', cases: [{ case_id: 'unchecked', correct: null,
        validation_status: 'unverified', timings_seconds: [0.01] }] }],
    });
    algorithmsApi.getExplanation.mockResolvedValue({ status: 'completed',
      explanation: 'The measured case is unverified; no correctness-backed winner is established.',
      citations: ['results[0].cases[0]'],
    });
    runGeneric();
    const table = await screen.findByRole('table', { name: 'Measured cases for arbitrary-label' });
    const measurements = table.textContent;
    const rankings = screen.getByRole('list', { name: 'Eligible measurement rankings' }).textContent;
    const source = screen.getByLabelText('Candidate 1 source').value;
    expect(algorithmsApi.startRun).toHaveBeenCalledWith(expect.objectContaining(payload));
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
    expect(screen.getByText(/summarize existing facts only/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Request explanation' }));
    await screen.findByText('Explanation status: completed');
    expect(algorithmsApi.getExplanation).toHaveBeenCalledExactlyOnceWith('run-1');
    expect(screen.getByText('Citations: results[0].cases[0]')).toBeInTheDocument();
    expect(table.textContent).toBe(measurements);
    expect(screen.getByRole('list', { name: 'Eligible measurement rankings' }).textContent).toBe(rankings);
    expect(screen.getByLabelText('Candidate 1 source')).toHaveValue(source);
    expect(screen.queryByText(/^Recommended:/)).not.toBeInTheDocument();
    expect(algorithmsApi.startRun).toHaveBeenCalledTimes(1);
    expect(algorithmsApi.getCompatibleHistory).not.toHaveBeenCalled();
  });

  it('bounds candidate controls, validates all names and restores sorting without sending generic fields', async () => {
    await genericForm();
    for (let index = 2; index <= 5; index += 1) {
      fireEvent.click(screen.getByRole('button', { name: 'Add candidate' }));
      change(`Candidate ${index} name`, 'arbitrary-label');
      change(`Candidate ${index} entrypoint`, 'total');
      change(`Candidate ${index} source`, 'def total(values): return sum(values)');
    }
    expect(screen.getByRole('button', { name: 'Add candidate' })).toBeDisabled();
    runGeneric();
    expect(screen.getByRole('alert')).toHaveTextContent('names must be unique');
    for (let index = 5; index >= 2; index -= 1) fireEvent.click(screen.getByRole('button', { name: `Remove candidate ${index}` }));
    change('Contract and datasets JSON', '{');
    change('Benchmark mode', 'sorting');
    expect(screen.getByLabelText('Candidate 2 source')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Remove candidate 2' })).toBeDisabled();
    expect(screen.queryByLabelText('Contract and datasets JSON')).not.toBeInTheDocument();
    fillForm();
    submit();
    await waitFor(() => expect(algorithmsApi.startRun).toHaveBeenCalled());
    const request = algorithmsApi.startRun.mock.calls[0][0];
    expect(request).not.toHaveProperty('contract');
    expect(request).not.toHaveProperty('datasets');
    expect(request).toMatchObject({ sizes: [0, 1, 100, 1000], distributions: ['random', 'sorted', 'reversed', 'duplicates'] });
  });
});

describe('Structure-only inspection', () => {
  function singleCandidate() {
    change('Benchmark mode', 'generic');
    fireEvent.click(screen.getByRole('button', { name: 'Remove candidate 2' }));
    change('Benchmark project ID', ' project-1 ');
    change('Candidate 1 name', ' total ');
    change('Candidate 1 entrypoint', 'total');
    change('Candidate 1 source', 'def total(values): return sum(values)');
  }
  function inspect() {
    fireEvent.click(screen.getByRole('button', { name: 'Inspect structure (no execution)' }));
  }

  it.each(['offline', 'probe-error', 'pending'])('inspects Python with one candidate and no datasets while availability is %s', async (availability) => {
    if (availability === 'offline') algorithmsApi.getAvailability.mockResolvedValue({ available: false, error: 'Benchmarks disabled' });
    if (availability === 'probe-error') algorithmsApi.getAvailability.mockRejectedValue(new Error('Docker unavailable'));
    if (availability === 'pending') algorithmsApi.getAvailability.mockReturnValue(new Promise(() => {}));
    renderPanel();
    singleCandidate();
    change('Contract and datasets JSON', '{invalid JSON');
    change('Memory limit in bytes (optional)', 'invalid benchmark-only limit');
    const resources = { timeout_seconds: 20, cpus: 0.25, memory_bytes: 67108864, pids: 16 };
    change('Resources JSON (optional)', JSON.stringify(resources));
    expect(screen.getByRole('button', { name: 'Inspect structure (no execution)' })).toBeEnabled();
    inspect();
    await waitFor(() => expect(algorithmsApi.inspectStructure).toHaveBeenCalledWith({
      project_id: 'project-1', language: 'python',
      candidates: [{ name: 'total', entrypoint: 'total', source: 'def total(values): return sum(values)' }], resources,
    }));
    const results = await screen.findByRole('region', { name: 'Structure-only inspection results' });
    expect(results).toHaveTextContent('Execution performed: false');
    expect(results).toHaveTextContent('"loops": 1');
    expect(results).toHaveTextContent('host-ast');
    expect(results).toHaveTextContent('Separate from benchmark measurements');
    expect(screen.queryByRole('region', { name: 'Benchmark run details' })).not.toBeInTheDocument();
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
    expect(algorithmsApi.getHistory).not.toHaveBeenCalled();
    expect(algorithmsApi.getCompatibleHistory).not.toHaveBeenCalled();
  });

  it('shares project, candidate and resource validation without requiring valid sorting inputs', async () => {
    await ready();
    inspect();
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a project ID');
    fillForm();
    change('Candidate 1 entrypoint', 'not.a.function');
    inspect();
    expect(screen.getByRole('alert')).toHaveTextContent('simple function identifiers');
    change('Candidate 1 entrypoint', 'sort_numbers');
    change('Candidate 1 source', ' ');
    inspect();
    expect(screen.getByRole('alert')).toHaveTextContent('name, source, and entrypoint');
    fillForm();
    change('Candidate 2 name', 'sort-1');
    inspect();
    expect(screen.getByRole('alert')).toHaveTextContent('names must be unique');
    fillForm();
    change('Resources JSON (optional)', '{"pids":1}');
    inspect();
    expect(screen.getByRole('alert')).toHaveTextContent('Resource pids');
    expect(algorithmsApi.inspectStructure).not.toHaveBeenCalled();
    change('Resources JSON (optional)', '');
    change('Input sizes', 'invalid sorting sizes');
    inspect();
    await waitFor(() => expect(algorithmsApi.inspectStructure).toHaveBeenCalledTimes(1));
    expect(algorithmsApi.inspectStructure.mock.calls[0][0]).not.toHaveProperty('resources');
    expect(algorithmsApi.inspectStructure.mock.calls[0][0]).not.toHaveProperty('sizes');
  });

  it('keeps inspection role-gated and reports service errors with explicit retry', async () => {
    await ready();
    singleCandidate();
    algorithmsApi.inspectStructure.mockRejectedValueOnce(new Error('AST parse failed'));
    inspect();
    await screen.findByText('AST parse failed');
    inspect();
    await screen.findByRole('region', { name: 'Structure-only inspection results' });
    expect(algorithmsApi.inspectStructure).toHaveBeenCalledTimes(2);
    act(() => useAuthStore.setState({ user: { role: 'HR' } }));
    expect(screen.getByRole('button', { name: 'Inspect structure (no execution)' })).toBeDisabled();
    inspect();
    expect(algorithmsApi.inspectStructure).toHaveBeenCalledTimes(2);
  });

  it.each(['javascript', 'typescript'])('requires enabled workers for %s inspection but never starts a benchmark', async (language) => {
    algorithmsApi.getAvailability.mockResolvedValueOnce({ available: false, error: 'Docker disabled' });
    renderPanel();
    await screen.findByText(/Docker disabled/);
    singleCandidate();
    change('Benchmark language', language);
    change('Candidate 1 source', 'function total(values) { return values.length; }');
    expect(screen.getByRole('button', { name: 'Inspect structure (no execution)' })).toBeDisabled();
    expect(screen.getByText(/JS\/TS parsing requires enabled Docker workers/)).toBeInTheDocument();
    expect(algorithmsApi.inspectStructure).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Recheck availability' }));
    await screen.findByText('Benchmark worker available.');
    inspect();
    await waitFor(() => expect(algorithmsApi.inspectStructure).toHaveBeenCalledWith(expect.objectContaining({ language })));
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
  });
});

describe('Explicit compatible history', () => {
  async function selectSavedRun() {
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ run_id: 'run-1', status: 'completed' }] });
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun,
      request: { ...completedRun.request, contract: { kind: 'function', name: 'custom', version: '1' } },
      historical_evidence: [{ run_id: 'automatic-reference-must-not-render' }],
    });
    await ready();
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    fireEvent.click(await screen.findByRole('button', { name: 'run-1' }));
    await screen.findByText('Status: completed');
  }

  it('loads references only on click, shows historical/match flags and limitations, and navigates without reranking', async () => {
    useAuthStore.setState({ user: { role: 'HR' } });
    await selectSavedRun();
    expect(algorithmsApi.getCompatibleHistory).not.toHaveBeenCalled();
    expect(screen.queryByText('automatic-reference-must-not-render')).not.toBeInTheDocument();
    expect(screen.getByText(/RAG deferred: generic runs/)).toBeInTheDocument();
    const eligibleBefore = screen.getByRole('list', { name: 'Eligible measurement rankings' }).textContent;
    algorithmsApi.getCompatibleHistory.mockResolvedValue({ historical_only: true, limitations: ['Workload identity is not proof of performance'], history: [
      { run_id: 'compatible-old', status: 'completed', created_at: '2026-01-01', historical_only: true, workload_match: true, environment_match: false,
        request: { language: 'python', candidates: [{ name: 'old', source_hash: 'stored-hash' }] },
        recommendation: { winner: 'old', status: 'recommended' }, results: [] },
      { run_id: 'compatible-other', status: 'completed', historical_only: true, workload_match: false, environment_match: true },
    ] });
    fireEvent.click(screen.getByRole('button', { name: 'Load compatible history' }));
    const ref = await screen.findByRole('button', { name: 'compatible-old' });
    expect(algorithmsApi.getCompatibleHistory).toHaveBeenCalledExactlyOnceWith('run-1');
    const section = screen.getByRole('region', { name: 'Compatible historical runs' });
    expect(section).toHaveTextContent('Historical only: true · Workload match: true · Environment match: false');
    expect(section).toHaveTextContent('Historical only: true · Workload match: false · Environment match: true');
    expect(section).toHaveTextContent('Workload identity is not proof of performance');
    expect(screen.getByRole('list', { name: 'Eligible measurement rankings' }).textContent).toBe(eligibleBefore);
    expect(screen.getByText('Insufficient evidence')).toBeInTheDocument();
    expect(screen.queryByText('Recommended: old')).not.toBeInTheDocument();
    algorithmsApi.getRun.mockResolvedValue({ run_id: 'compatible-old', status: 'completed', results: [] });
    fireEvent.click(ref);
    await screen.findByRole('heading', { name: 'Run compatible-old' });
    expect(algorithmsApi.getRun).toHaveBeenLastCalledWith('compatible-old');
    expect(algorithmsApi.getCompatibleHistory).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('Workload identity is not proof of performance')).not.toBeInTheDocument();
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
    expect(algorithmsApi.getExplanation).not.toHaveBeenCalled();
  });

  it('handles errors and empty compatible history with an explicit retry', async () => {
    await selectSavedRun();
    algorithmsApi.getCompatibleHistory.mockRejectedValueOnce(new Error('History access denied'));
    fireEvent.click(screen.getByRole('button', { name: 'Load compatible history' }));
    await screen.findByText('History access denied');
    expect(algorithmsApi.getCompatibleHistory).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: 'Load compatible history' }));
    await screen.findByText('No compatible historical runs found.');
    expect(algorithmsApi.getCompatibleHistory).toHaveBeenCalledTimes(2);
    expect(screen.getByText('Historical evidence requires a fresh benchmark')).toBeInTheDocument();
  });
});

describe('Algorithms API adapter', () => {
  it('posts a new policy for exactly one saved run using the authenticated adapter', async () => {
    const { algorithmsApi: actualApi } = await vi.importActual('../api/algorithms.api');
    localStorage.setItem('samanvaya_token', 'revision-token');
    const policy = { id: 'strict', version: '1' };
    let captured;
    server.use(http.post('*/api/algorithms/runs/saved-1/reevaluate', async ({ request }) => {
      captured = { token: request.headers.get('Authorization'), body: await request.json() };
      return HttpResponse.json({ revision_number: 2 });
    }));
    expect(await actualApi.reevaluate('saved-1', policy)).toEqual({ revision_number: 2 });
    expect(captured).toEqual({ token: 'Bearer revision-token', body: { decision_policy: policy } });
  });
  it('authenticates structure inspection and explicit compatible-history access through the real client', async () => {
    const { algorithmsApi: actualApi } = await vi.importActual('../api/algorithms.api');
    localStorage.setItem('samanvaya_token', 'structure-test-token');
    const payload = { project_id: 'p', language: 'python', candidates: [{ name: 'total', entrypoint: 'total', source: 'def total(values): return sum(values)' }], resources: { cpus: 0.5 } };
    const structure = { structural_analysis: { total: { loops: 0 } }, execution_performed: false, environment: {} };
    const history = { history: [], historical_only: true, limitations: ['Historical only'] };
    const requests = [];
    server.use(
      http.post('*/api/algorithms/structure', async ({ request }) => {
        requests.push({ token: request.headers.get('Authorization'), body: await request.json() });
        return HttpResponse.json(structure);
      }),
      http.get('*/api/algorithms/runs/saved-run/compatible-history', ({ request }) => {
        requests.push({ token: request.headers.get('Authorization') });
        return HttpResponse.json(history);
      }),
    );
    await expect(actualApi.inspectStructure(payload)).resolves.toEqual(structure);
    await expect(actualApi.getCompatibleHistory('saved-run')).resolves.toEqual(history);
    expect(requests).toEqual([
      { token: 'Bearer structure-test-token', body: payload },
      { token: 'Bearer structure-test-token' },
    ]);
  });

  it('attaches the bearer token and unwraps an async 202 response through the real client', async () => {
    const { algorithmsApi: actualApi } = await vi.importActual('../api/algorithms.api');
    const payload = {
      project_id: 'project-1',
      contract: { kind: 'function', name: 'custom', version: '1', input_schema: { type: 'array' }, output_schema: {}, correctness: 'none' },
      datasets: [{ id: 'custom-input', args: [{ values: [1, 2] }, null], dimensions: { count: 2 } }],
      resources: { timeout_seconds: 30, cpus: 0.5, memory_bytes: 67108864, pids: 16 },
    };
    localStorage.setItem('samanvaya_token', 'benchmark-test-token');
    const requests = [];
    server.use(
      http.post('*/api/algorithms/runs', async ({ request }) => {
        requests.push({ token: request.headers.get('Authorization'), body: await request.json() });
        return HttpResponse.json({ run_id: 'async-run', status: 'pending' }, { status: 202 });
      }),
      http.get('*/api/algorithms/runs/async-run', ({ request }) => {
        requests.push({ token: request.headers.get('Authorization') });
        return HttpResponse.json({ run_id: 'async-run', status: 'running' });
      }),
    );
    await expect(actualApi.startRun(payload)).resolves.toEqual({ run_id: 'async-run', status: 'pending' });
    await expect(actualApi.getRun('async-run')).resolves.toEqual({ run_id: 'async-run', status: 'running' });
    expect(requests).toEqual([
      { token: 'Bearer benchmark-test-token', body: payload },
      { token: 'Bearer benchmark-test-token' },
    ]);
  });
  it('uses the authenticated client with encoded identifiers and the expected endpoints', async () => {
    const { algorithmsApi: actualApi } = await vi.importActual('../api/algorithms.api');
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({});
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({});
    await actualApi.getAvailability();
    await actualApi.inspectStructure({ project_id: 'p', language: 'python', candidates: [] });
    await actualApi.getCompatibleHistory('run/1');
    await actualApi.startRun({ project_id: 'p' });
    await actualApi.getRun('run/1');
    await actualApi.getHistory('project/a');
    await actualApi.submitFeedback('run/1', { decision: 'accepted', reason: 'Reviewed' });
    await actualApi.getExplanation('run/1');
    expect(get).toHaveBeenCalledWith('/algorithms/availability');
    expect(get).toHaveBeenCalledWith('/algorithms/runs/run%2F1/compatible-history');
    expect(post).toHaveBeenCalledWith('/algorithms/structure', { project_id: 'p', language: 'python', candidates: [] });
    expect(get).toHaveBeenCalledWith('/algorithms/runs/run%2F1');
    expect(get).toHaveBeenCalledWith('/algorithms/projects/project%2Fa/history', { params: { limit: 10 } });
    expect(post).toHaveBeenCalledWith('/algorithms/runs', { project_id: 'p' });
    expect(post).toHaveBeenCalledWith('/algorithms/runs/run%2F1/feedback', { decision: 'accepted', reason: 'Reviewed' });
    expect(post).toHaveBeenCalledWith('/algorithms/runs/run%2F1/explanation');
  });
});

function policyDecision() {
  return {
    engine_version: 'deterministic-decision-v1', policy_id: 'strict', policy_version: '1', revision_number: 2, revision_id: 'DEC-2',
    task_suitability: { status: 'NO_ELIGIBLE_IMPLEMENTATION', eligible_candidates: [] },
    candidates: [{ candidate: 'sort-1', task_eligibility: 'INELIGIBLE', correctness: 'PASS', missing_required_dataset_ids: [],
      datasets: [{ dataset_id: 'small', eligibility: 'INELIGIBLE', correctness: 'PASS', evidence_reference: 'run-1/results/sort-1/datasets/small',
        timing: { status: 'AVAILABLE', count: 5, median: 0.01, minimum: 0.009, maximum: 0.02, variability_ratio: 1.1 },
        memory: { status: 'UNAVAILABLE', bytes: null, metric: 'memray_peak_tracked_allocations_bytes' } }],
      constraint_evaluations: [{ constraint_id: 'latency', status: 'FAIL', classification: 'MANDATORY', dataset_id: 'small', source_reference: 'project:spec/1', observed_maximum: 0.02, threshold: 0.01 }] }],
    dataset_comparisons: [{ dataset_id: 'small', status: 'NO_ELIGIBLE_IMPLEMENTATION', winner: null, reason: 'Maximum invocation exceeds requirement.' }],
    unknown_requirements: [{ id: 'memory-budget', description: 'Budget unknown' }],
    missing_evidence: [{ candidate: 'sort-1', dataset_id: 'small', measurement: 'memory', status: 'UNAVAILABLE', evidence_reference: 'run-1/evidence' }],
    limitations: ['Tested correctness only; no universal equivalence.'],
    policy_snapshot: { id: 'strict', version: '1', constraints: [] }, identities: { evidence: 'typed-evidence-fingerprint' }, policy_fingerprint: 'policy-fingerprint',
  };
}

describe('Authoritative deterministic benchmark decisions', () => {
  it('submits an explicit policy and suppresses a disqualified legacy aggregate winner', async () => {
    const decision = policyDecision();
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun, decision, decision_revisions: [decision],
      recommendation: { status: 'recommended', winner: 'disqualified-legacy', reason: 'Old aggregate', rankings: [], limitations: [] } });
    await ready();
    fillForm();
    const policy = { id: 'strict', version: '1', objective: 'MINIMIZE_TIME', constraints: [] };
    change('Decision policy JSON (optional)', JSON.stringify(policy));
    submit();
    const region = await screen.findByRole('region', { name: 'Deterministic decision' });
    expect(algorithmsApi.startRun.mock.calls[0][0].decision_policy).toEqual(policy);
    expect(region).toHaveTextContent('NO_ELIGIBLE_IMPLEMENTATION');
    expect(region).toHaveTextContent('Tested correctness: PASS');
    expect(region).toHaveTextContent('Scope: small');
    expect(region).toHaveTextContent('project:spec/1');
    expect(region).toHaveTextContent('median 0.01 s');
    expect(region).toHaveTextContent('Memory UNAVAILABLE');
    expect(region).toHaveTextContent('Budget unknown');
    expect(region).toHaveTextContent('Revision: 2 (DEC-2)');
    expect(region).toHaveTextContent('typed-evidence-fingerprint');
    expect(screen.queryByText('Recommended: disqualified-legacy')).not.toBeInTheDocument();
    expect(screen.queryByText('Old aggregate')).not.toBeInTheDocument();
  });

  it('validates policy JSON, reevaluates saved evidence and preserves the run selection', async () => {
    algorithmsApi.getRun.mockResolvedValue({ ...completedRun, decision: policyDecision() });
    algorithmsApi.reevaluate.mockResolvedValue({ revision_number: 3 });
    await ready();
    fillForm();
    change('Decision policy JSON (optional)', '{broken');
    submit();
    expect(screen.getByRole('alert')).toHaveTextContent('Decision policy must be valid JSON');
    expect(algorithmsApi.startRun).not.toHaveBeenCalled();
    change('Decision policy JSON (optional)', '');
    submit();
    await screen.findByRole('region', { name: 'Deterministic decision' });
    const policy = { id: 'revision-three', version: '1' };
    change('Reevaluation policy JSON', JSON.stringify(policy));
    fireEvent.click(screen.getByRole('button', { name: 'Reevaluate without execution' }));
    await screen.findByText('Saved decision revision 3');
    expect(algorithmsApi.reevaluate).toHaveBeenCalledExactlyOnceWith('run-1', policy);
    expect(algorithmsApi.startRun).toHaveBeenCalledTimes(1);
  });

  it('uses structured decision status in project history instead of a legacy winner', async () => {
    algorithmsApi.getHistory.mockResolvedValue({ history: [{ ...completedRun, decision: policyDecision(),
      recommendation: { winner: 'unsafe-winner', reason: 'unsafe summary' } }] });
    await ready();
    change('Benchmark project ID', 'project-1');
    fireEvent.click(screen.getByRole('button', { name: 'Load project history' }));
    await screen.findByText(/Decision: NO_ELIGIBLE_IMPLEMENTATION/);
    expect(screen.queryByText(/Winner: unsafe-winner/)).not.toBeInTheDocument();
    expect(screen.queryByText(/unsafe summary/)).not.toBeInTheDocument();
  });
});
