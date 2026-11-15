import { describe, expect, it, vi } from 'vitest';
import apiClient from './client';
import { prWorkflowsApi } from './prWorkflows.api';

vi.mock('./client', () => ({ default: { get: vi.fn(), post: vi.fn() } }));

describe('manual PR workflow API versioning', () => {
  it('uses the separate v1 routes and forwards cancellation for reads', () => {
    const signal = new AbortController().signal;
    prWorkflowsApi.projects(signal);
    prWorkflowsApi.status('a'.repeat(64), signal);
    prWorkflowsApi.report('a'.repeat(64), signal);
    const body = { project_id: 'P1', pr_number: 7 };
    prWorkflowsApi.start(body);
    expect(apiClient.get).toHaveBeenCalledWith('/ai/workflows/v1/projects', { signal });
    expect(apiClient.get).toHaveBeenCalledWith(`/ai/workflows/v1/jobs/${'a'.repeat(64)}`, { signal });
    expect(apiClient.get).toHaveBeenCalledWith(`/ai/workflows/v1/jobs/${'a'.repeat(64)}/report`, { signal });
    expect(apiClient.post).toHaveBeenCalledWith('/ai/workflows/v1/pr-analysis', body);
  });
});
